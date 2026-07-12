# tests/test_pco_client_checkins.py
#
# Tests for get_checkins_for_event_periods and _fetch_checkins_page in pco_client.py.
#
# All tests mock requests.get — no real HTTP calls are made.

from unittest.mock import MagicMock, patch

import pytest
import requests

from planning_center_reports.pco_client import (
    _fetch_checkins_page,
    get_checkins_for_event_periods,
    _MAX_PAGES_PER_PERIOD,
    PaginationCircuitBreakerError,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_response(data, included=None, next_url=None, status=200):
    """Return a mock requests.Response with the given JSON body."""
    resp = MagicMock()
    resp.status_code = status
    resp.ok = status < 400
    resp.text = ""
    resp.json.return_value = {
        "data": data,
        "included": included or [],
        "links": {"next": next_url} if next_url else {},
    }
    resp.raise_for_status.return_value = None
    return resp


def _make_checkin(person_id="p1", location_id="loc1"):
    return {
        "attributes": {"first_name": "Test", "last_name": "User"},
        "relationships": {
            "locations": {"data": [{"id": location_id}]},
            "person":    {"data": {"id": person_id}},
            "event_period": {"data": {"id": "ep1"}},
        },
    }


# ── _fetch_checkins_page ───────────────────────────────────────────────────────

class TestFetchCheckinsPage:
    @patch("planning_center_reports.pco_client.requests.get")
    def test_returns_parsed_json_on_success(self, mock_get):
        mock_get.return_value = _make_response([_make_checkin()])
        body = _fetch_checkins_page("https://api.planningcenteronline.com/check-ins/v2/...", {}, 1)
        assert "data" in body
        assert len(body["data"]) == 1

    @patch("planning_center_reports.pco_client.requests.get")
    def test_raises_on_http_error(self, mock_get):
        resp = MagicMock()
        resp.status_code = 500
        resp.ok = False
        resp.text = "Internal Server Error"
        resp.raise_for_status.side_effect = requests.HTTPError("Server Error")
        mock_get.return_value = resp
        with pytest.raises(requests.HTTPError):
            _fetch_checkins_page("https://example.com", {}, 1)

    @patch("planning_center_reports.pco_client.requests.get")
    def test_logs_status_code_on_http_error(self, mock_get, capsys):
        """Non-OK responses should print the status code before re-raising."""
        resp = MagicMock()
        resp.status_code = 404
        resp.ok = False
        resp.text = "Not Found"
        resp.raise_for_status.side_effect = requests.HTTPError("Not Found")
        mock_get.return_value = resp
        with pytest.raises(requests.HTTPError):
            _fetch_checkins_page("https://example.com", {}, 1)
        captured = capsys.readouterr()
        assert "404" in captured.out

    @patch("planning_center_reports.pco_client.time.sleep", return_value=None)
    @patch("planning_center_reports.pco_client.requests.get")
    def test_retries_on_connection_error(self, mock_get, _sleep):
        """Should retry and succeed on the second attempt."""
        good_resp = _make_response([_make_checkin()])
        mock_get.side_effect = [requests.exceptions.ConnectionError("timeout"), good_resp]
        body = _fetch_checkins_page("https://example.com", {}, 1)
        assert len(body["data"]) == 1
        assert mock_get.call_count == 2

    @patch("planning_center_reports.pco_client.time.sleep", return_value=None)
    @patch("planning_center_reports.pco_client.requests.get")
    def test_raises_after_max_retries(self, mock_get, _sleep):
        mock_get.side_effect = requests.exceptions.ConnectionError("timeout")
        with pytest.raises(Exception, match="Failed to fetch check-ins page 1 after 7 retries"):
            _fetch_checkins_page("https://example.com", {}, 1)
        assert mock_get.call_count == 7

    @patch("planning_center_reports.pco_client.time.sleep", return_value=None)
    @patch("planning_center_reports.pco_client.requests.get")
    def test_retries_on_rate_limit(self, mock_get, _sleep):
        """429 response should trigger a retry, then succeed."""
        rate_limited = _make_response([], status=429)
        good_resp = _make_response([_make_checkin()])
        mock_get.side_effect = [rate_limited, good_resp]
        body = _fetch_checkins_page("https://example.com", {}, 1)
        assert len(body["data"]) == 1


# ── get_checkins_for_event_periods ─────────────────────────────────────────────

class TestGetCheckinsForEventPeriods:
    @patch("planning_center_reports.pco_client.requests.get")
    def test_fetches_per_period_using_nested_url(self, mock_get):
        """Must use the events/{event_id}/event_periods/{period_id}/check_ins nested URL."""
        mock_get.return_value = _make_response([])
        get_checkins_for_event_periods("event123", ["ep1", "ep2"])
        urls = [c.args[0] for c in mock_get.call_args_list]
        assert all("events/event123/event_periods" in url for url in urls)
        assert any("ep1" in url for url in urls)
        assert any("ep2" in url for url in urls)

    @patch("planning_center_reports.pco_client.requests.get")
    def test_fetches_each_period_separately(self, mock_get):
        """One HTTP call per period (when each fits on one page)."""
        mock_get.return_value = _make_response([])
        get_checkins_for_event_periods("event123", ["ep1", "ep2", "ep3"])
        assert mock_get.call_count == 3
        urls = [c.args[0] for c in mock_get.call_args_list]
        assert any("ep1" in u for u in urls)
        assert any("ep2" in u for u in urls)
        assert any("ep3" in u for u in urls)

    @patch("planning_center_reports.pco_client.requests.get")
    def test_aggregates_checkins_across_periods(self, mock_get):
        """Check-ins from all periods should be combined."""
        mock_get.side_effect = [
            _make_response([_make_checkin("p1"), _make_checkin("p2")]),
            _make_response([_make_checkin("p3")]),
        ]
        checkins, _ = get_checkins_for_event_periods("event123", ["ep1", "ep2"])
        assert len(checkins) == 3

    @patch("planning_center_reports.pco_client.requests.get")
    def test_aggregates_included_across_periods(self, mock_get):
        """Included sideload records from all periods should be combined."""
        loc1 = {"type": "Location", "id": "loc1", "attributes": {"name": "Ruta 1"}}
        loc2 = {"type": "Location", "id": "loc2", "attributes": {"name": "Ruta 2"}}
        mock_get.side_effect = [
            _make_response([], included=[loc1]),
            _make_response([], included=[loc2]),
        ]
        _, included = get_checkins_for_event_periods("event123", ["ep1", "ep2"])
        assert len(included) == 2

    @patch("planning_center_reports.pco_client.requests.get")
    def test_handles_empty_period_list(self, mock_get):
        checkins, included = get_checkins_for_event_periods("event123", [])
        assert checkins == []
        assert included == []
        mock_get.assert_not_called()

    @patch("planning_center_reports.pco_client.requests.get")
    def test_paginates_within_a_period(self, mock_get):
        """When a period has multiple pages, all pages must be fetched."""
        page2_url = "https://api.planningcenteronline.com/check-ins/v2/events/event123/event_periods/ep1/check_ins?page=2"
        mock_get.side_effect = [
            _make_response([_make_checkin("p1")], next_url=page2_url),
            _make_response([_make_checkin("p2")]),  # page 2 — no next link
        ]
        checkins, _ = get_checkins_for_event_periods("event123", ["ep1"])
        assert len(checkins) == 2
        assert mock_get.call_count == 2

    @patch("planning_center_reports.pco_client.requests.get")
    def test_stops_pagination_when_next_same_as_current(self, mock_get):
        """Guard against infinite loop when next URL equals current URL."""
        same_url = "https://api.planningcenteronline.com/check-ins/v2/events/event123/event_periods/ep1/check_ins"
        mock_get.return_value = _make_response([_make_checkin()], next_url=same_url)
        checkins, _ = get_checkins_for_event_periods("event123", ["ep1"])
        # Should only fetch once and then stop
        assert mock_get.call_count == 1
        assert len(checkins) == 1

    @patch("planning_center_reports.pco_client.requests.get")
    def test_uses_correct_query_params(self, mock_get):
        """First page should sideload locations+person and use per_page=100."""
        mock_get.return_value = _make_response([])
        get_checkins_for_event_periods("event123", ["ep1"])
        _, kwargs = mock_get.call_args
        params = kwargs.get("params", {})
        assert params.get("include") == "locations,person"
        assert params.get("per_page") == 100

    @patch("planning_center_reports.pco_client.requests.get")
    def test_circuit_breaker_raises_after_max_pages(self, mock_get):
        """If a period exceeds _MAX_PAGES_PER_PERIOD pages, raise immediately."""
        # Each call returns a unique next_url so the same-URL guard never fires first
        call_count = 0

        def always_has_next(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_response(
                [_make_checkin()],
                next_url=f"https://api.planningcenteronline.com/page/{call_count + 1}",
            )

        mock_get.side_effect = always_has_next
        with pytest.raises(PaginationCircuitBreakerError, match="exceeded"):
            get_checkins_for_event_periods("event123", ["ep1"])
        assert mock_get.call_count == _MAX_PAGES_PER_PERIOD

    @patch("planning_center_reports.pco_client.requests.get")
    def test_multi_period_with_pagination(self, mock_get):
        """Two periods, each with 2 pages — total 4 HTTP calls."""
        page2 = "https://api.planningcenteronline.com/page2"
        mock_get.side_effect = [
            _make_response([_make_checkin("p1")], next_url=page2),
            _make_response([_make_checkin("p2")]),   # ep1 page 2
            _make_response([_make_checkin("p3")], next_url=page2),
            _make_response([_make_checkin("p4")]),   # ep2 page 2
        ]
        checkins, _ = get_checkins_for_event_periods("event123", ["ep1", "ep2"])
        assert len(checkins) == 4
        assert mock_get.call_count == 4
