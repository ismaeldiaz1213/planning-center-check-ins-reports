# tests/test_pco_client.py
#
# Request pacing, period discovery, sideloaded person details and the batched
# guardian lookup in pco_client.py. All HTTP is mocked.

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests

from planning_center_reports import pco_client
from planning_center_reports.pco_client import (
    OAuthBearer,
    PcoClient,
    PersonalAccessToken,
    person_details,
)


@pytest.fixture
def client():
    """A fresh client per test: its own pacing window, counters and cache."""
    return PcoClient(PersonalAccessToken("test-app-id", "test-secret"))


def _resp(body=None, status=200, headers=None):
    r = MagicMock()
    r.status_code = status
    r.ok = status < 400
    r.headers = headers or {}
    r.json.return_value = body or {"data": []}
    r.raise_for_status.return_value = None
    return r


# ── Pacing ────────────────────────────────────────────────────────────────────

class TestPacing:
    @patch("planning_center_reports.pco_client.time.sleep")
    @patch("planning_center_reports.pco_client.requests.get")
    def test_honours_retry_after_on_429(self, mock_get, mock_sleep, client):
        mock_get.side_effect = [_resp(status=429, headers={"Retry-After": "7"}), _resp()]
        assert client._get("https://x", label="t").status_code == 200
        mock_sleep.assert_called_once_with(7)

    @patch("planning_center_reports.pco_client.time.sleep")
    @patch("planning_center_reports.pco_client.requests.get")
    def test_falls_back_to_exponential_backoff_without_retry_after(self, mock_get, mock_sleep, client):
        mock_get.side_effect = [_resp(status=429), _resp(status=429), _resp()]
        client._get("https://x")
        assert [c.args[0] for c in mock_sleep.call_args_list] == [1, 2]

    @patch("planning_center_reports.pco_client.time.sleep")
    def test_throttle_waits_once_the_window_is_full(self, mock_sleep, client):
        for _ in range(client.rate_max):
            client._throttle()
        mock_sleep.assert_not_called()
        client._throttle()
        mock_sleep.assert_called_once()
        assert 0 < mock_sleep.call_args.args[0] <= client.rate_window_s

    @patch("planning_center_reports.pco_client.time.sleep")
    @patch("planning_center_reports.pco_client.requests.get")
    def test_returns_none_after_repeated_network_errors(self, mock_get, _sleep, client):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("down")
        assert client._get("https://x") is None
        assert mock_get.call_count == client.max_retries


# ── Periods since a start date ────────────────────────────────────────────────

def _period(pid, dt):
    return {"id": pid, "attributes": {"starts_at": dt.strftime("%Y-%m-%dT%H:%M:%SZ")}}


class TestEventPeriodsSince:
    @patch("planning_center_reports.pco_client.requests.get")
    def test_keeps_past_periods_on_or_after_the_start_oldest_first(self, mock_get, client):
        now = datetime.now(UTC)
        sundays = [now - timedelta(weeks=w, hours=1) for w in range(5)]
        future = _period("future", now + timedelta(days=3))
        body = {"data": [future] + [_period(f"p{w}", d) for w, d in enumerate(sundays)], "links": {}}
        mock_get.return_value = _resp(body)
        since = (now - timedelta(weeks=2, days=1)).date()
        got = client.get_event_periods_since("ev", since)
        assert [p["id"] for p in got] == ["p2", "p1", "p0"]

    @patch("planning_center_reports.pco_client.requests.get")
    def test_stops_paging_once_older_than_the_start(self, mock_get, client):
        now = datetime.now(UTC)
        page1 = {"data": [_period("p0", now - timedelta(days=1))], "links": {"next": "https://next"}}
        page2 = {"data": [_period("old", now - timedelta(weeks=60))], "links": {"next": "https://more"}}
        mock_get.side_effect = [_resp(page1), _resp(page2)]
        got = client.get_event_periods_since("ev", (now - timedelta(weeks=4)).date())
        assert [p["id"] for p in got] == ["p0"]
        assert mock_get.call_count == 2

    @patch("planning_center_reports.pco_client.requests.get")
    def test_caps_the_number_of_periods(self, mock_get, client):
        now = datetime.now(UTC)
        body = {"data": [_period(f"p{w}", now - timedelta(weeks=w, hours=1)) for w in range(10)],
                "links": {}}
        mock_get.return_value = _resp(body)
        got = client.get_event_periods_since("ev", date(2000, 1, 1), max_periods=3)
        assert [p["id"] for p in got] == ["p2", "p1", "p0"]


# ── Person details from sideloads ─────────────────────────────────────────────

class TestPersonDetails:
    def test_prefers_primary_phone_and_address(self):
        attrs = {
            "birthdate": "2015-04-01", "grade": 5, "gender": "F", "created_at": "2024-01-01T00:00:00Z",
            "phone_numbers": [{"number": "111", "primary": False}, {"number": "222", "primary": True}],
            "addresses": [
                {"street_line_1": "1 Old Rd", "city": "Houston", "primary": False},
                {"street_line_1": "9 Main St", "street_line_2": "Apt 4", "city": "Houston",
                 "state": "TX", "zip": "77001", "primary": True},
            ],
        }
        d = person_details(attrs)
        assert d["phone"] == "222"
        assert d["address"] == "9 Main St, Apt 4, Houston, TX, 77001"
        assert d["grade"] == "5°"

    def test_missing_contact_lists_are_blank(self):
        d = person_details({"phone_numbers": [], "addresses": [], "grade": None})
        assert d["phone"] == "" and d["address"] == "" and d["grade"] == ""


# ── Guardians ─────────────────────────────────────────────────────────────────

def _person(pid, households=(), phones=(), addresses=(), **attrs):
    return {
        "type": "Person", "id": pid, "attributes": attrs,
        "relationships": {
            "households":    {"data": [{"type": "Household", "id": h} for h in households]},
            "phone_numbers": {"data": [{"type": "PhoneNumber", "id": p} for p in phones]},
            "addresses":     {"data": [{"type": "Address", "id": a} for a in addresses]},
        },
    }


def _household(hid, contact_id, contact_name):
    return {"type": "Household", "id": hid,
            "attributes": {"primary_contact_id": contact_id, "primary_contact_name": contact_name}}


class TestGetGuardians:
    @patch("planning_center_reports.pco_client.requests.get")
    def test_returns_the_adult_primary_contact_with_contact_details(self, mock_get, client):
        kids = {"data": [_person("k1", households=["h1"])],
                "included": [_household("h1", "mom", "Ana Lopez")], "links": {}}
        parents = {"data": [_person("mom", phones=["ph"], addresses=["ad"], name="Ana Lopez",
                                    child=False, birthdate="1985-01-01")],
                   "included": [
                       {"type": "PhoneNumber", "id": "ph", "attributes": {"number": "(281) 555-0100", "primary": True}},
                       {"type": "Address", "id": "ad", "attributes": {"street_line_1": "9 Main St", "city": "Houston",
                                                                     "primary": True}},
                   ], "links": {}}
        mock_get.side_effect = [_resp(kids), _resp(parents)]
        g = client.get_guardians(["k1"])
        assert g == {"k1": {"name": "Ana Lopez", "phone": "(281) 555-0100", "address": "9 Main St, Houston"}}

    @patch("planning_center_reports.pco_client.requests.get")
    def test_a_child_head_of_household_is_never_shown_as_the_parent(self, mock_get, client):
        """When parents don't attend, PCO can make an older sibling the primary contact."""
        kids = {"data": [_person("k1", households=["h1"])],
                "included": [_household("h1", "sib", "Older Sibling")], "links": {}}
        sibling = {"data": [_person("sib", name="Older Sibling", child=True, birthdate="2011-01-01")],
                   "included": [], "links": {}}
        mock_get.side_effect = [_resp(kids), _resp(sibling)]
        assert client.get_guardians(["k1"]) == {}

    @patch("planning_center_reports.pco_client.requests.get")
    def test_a_minor_not_flagged_as_child_is_still_excluded(self, mock_get, client):
        teen = (date.today().year - 16)
        kids = {"data": [_person("k1", households=["h1"])],
                "included": [_household("h1", "sib", "Teen")], "links": {}}
        sibling = {"data": [_person("sib", name="Teen", child=False, birthdate=f"{teen}-01-01")],
                   "included": [], "links": {}}
        mock_get.side_effect = [_resp(kids), _resp(sibling)]
        assert client.get_guardians(["k1"]) == {}

    @patch("planning_center_reports.pco_client.requests.get")
    def test_kid_who_is_their_own_primary_contact_gets_no_parent(self, mock_get, client):
        kids = {"data": [_person("k1", households=["h1"])],
                "included": [_household("h1", "k1", "The Kid")], "links": {}}
        mock_get.side_effect = [_resp(kids)]
        assert client.get_guardians(["k1"]) == {}

    @patch("planning_center_reports.pco_client.requests.get")
    def test_batches_ids_one_hundred_per_request(self, mock_get, client):
        mock_get.return_value = _resp({"data": [], "included": [], "links": {}})
        client.get_guardians([str(i) for i in range(250)])
        id_lists = [c.kwargs["params"]["where[id]"].split(",") for c in mock_get.call_args_list]
        assert [len(ids) for ids in id_lists] == [100, 100, 50]

    def test_no_children_makes_no_requests(self, client):
        with patch("planning_center_reports.pco_client.requests.get") as mock_get:
            assert client.get_guardians([]) == {}
            mock_get.assert_not_called()


# ── Request statistics (docs/benchmarks.md) ───────────────────────────────────

class TestRequestStats:
    def test_counts_every_attempt_including_retries_and_429s(self, monkeypatch, client):
        ok = MagicMock(status_code=200)
        limited = MagicMock(status_code=429, headers={"Retry-After": "3"})
        responses = iter([requests.exceptions.ConnectionError("down"), limited, ok])

        def fake_get(*_a, **_k):
            item = next(responses)
            if isinstance(item, Exception):
                raise item
            return item

        slept = []
        monkeypatch.setattr(pco_client.requests, "get", fake_get)
        monkeypatch.setattr(pco_client.time, "sleep", slept.append)

        assert client._get("https://example.invalid") is ok
        s = client.stats
        assert (s.requests, s.network_retries, s.rate_limited) == (3, 1, 1)
        assert s.backoff_wait_s == 1 + 3 == sum(slept)
        assert s.throttle_wait_s == 0

    def test_counts_time_paused_for_our_own_pace(self, monkeypatch, client):
        slept = []
        monkeypatch.setattr(pco_client.time, "sleep", slept.append)
        now = pco_client.time.monotonic()
        client._request_times.extend([now] * client.rate_max)
        client._throttle()
        assert len(slept) == 1
        assert client.stats.throttle_wait_s == pytest.approx(slept[0])
        assert 19 < slept[0] <= 20

    def test_reset_and_summary(self, client):
        client.stats.requests = 5
        assert "requests: 5" in client.stats.summary()
        client.stats.reset()
        assert client.stats.as_dict()["requests"] == 0


# ── Sign-in strategies ────────────────────────────────────────────────────────

class TestAuth:
    @patch("planning_center_reports.pco_client.requests.get")
    def test_personal_access_token_is_sent_as_basic_auth(self, mock_get, client):
        mock_get.return_value = _resp()
        client._get("https://x")
        kwargs = mock_get.call_args.kwargs
        assert (kwargs["auth"].username, kwargs["auth"].password) == ("test-app-id", "test-secret")
        assert "headers" not in kwargs

    @patch("planning_center_reports.pco_client.requests.get")
    def test_oauth_token_is_sent_as_a_bearer_header(self, mock_get):
        mock_get.return_value = _resp()
        PcoClient(OAuthBearer("tok-1"))._get("https://x")
        kwargs = mock_get.call_args.kwargs
        assert kwargs["headers"] == {"Authorization": "Bearer tok-1"}
        assert "auth" not in kwargs

    @patch("planning_center_reports.pco_client.requests.get")
    def test_expired_oauth_token_is_refreshed_once_and_the_request_retried(self, mock_get):
        mock_get.side_effect = [_resp(status=401), _resp()]
        refreshes = []
        oauth_client = PcoClient(OAuthBearer("old", refresh=lambda: refreshes.append(1) or "new"))
        assert oauth_client._get("https://x").status_code == 200
        assert len(refreshes) == 1
        assert mock_get.call_args.kwargs["headers"] == {"Authorization": "Bearer new"}
        assert oauth_client.stats.token_refreshes == 1 and oauth_client.stats.requests == 2

    @patch("planning_center_reports.pco_client.requests.get")
    def test_a_second_401_is_returned_instead_of_refreshing_forever(self, mock_get):
        mock_get.return_value = _resp(status=401)
        refreshes = []
        oauth_client = PcoClient(OAuthBearer("old", refresh=lambda: refreshes.append(1) or "new"))
        assert oauth_client._get("https://x").status_code == 401
        assert len(refreshes) == 1 and mock_get.call_count == 2

    @patch("planning_center_reports.pco_client.requests.get")
    def test_401_without_a_refresh_callback_is_returned_as_is(self, mock_get, client):
        mock_get.return_value = _resp(status=401)
        assert client._get("https://x").status_code == 401
        assert PcoClient(OAuthBearer("tok"))._get("https://x").status_code == 401
        assert mock_get.call_count == 2

    def test_a_failing_refresh_reaches_the_caller(self):
        def reconnect_needed():
            raise RuntimeError("needs_reconnect")
        with patch("planning_center_reports.pco_client.requests.get", return_value=_resp(status=401)):
            with pytest.raises(RuntimeError, match="needs_reconnect"):
                PcoClient(OAuthBearer("old", refresh=reconnect_needed))._get("https://x")


# ── Two churches in one process ───────────────────────────────────────────────

class TestClientsShareNothing:
    @patch("planning_center_reports.pco_client.requests.get")
    def test_each_client_has_its_own_pacing_counters_and_cache(self, mock_get):
        mock_get.return_value = _resp({"data": {"attributes": {"birthdate": "2015-01-01"}}, "included": []})
        a = PcoClient(PersonalAccessToken("a", "a"))
        b = PcoClient(PersonalAccessToken("b", "b"))
        a.get_person_details("7")
        assert (a.stats.requests, b.stats.requests) == (1, 0)
        assert len(a._request_times) == 1 and len(b._request_times) == 0
        assert "7" in a._person_cache and "7" not in b._person_cache
        # The same person id at another church is a different person: b must ask again.
        b.get_person_details("7")
        assert mock_get.call_count == 2
