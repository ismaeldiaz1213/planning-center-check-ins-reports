# tests/test_pco_client.py
#
# Request pacing, period discovery, sideloaded person details and the batched
# guardian lookup in pco_client.py. All HTTP is mocked.

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock, patch

from planning_center_reports import pco_client
from planning_center_reports.pco_client import (
    _get,
    _throttle,
    get_event_periods_since,
    get_guardians,
    person_details,
)


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
    def test_honours_retry_after_on_429(self, mock_get, mock_sleep):
        mock_get.side_effect = [_resp(status=429, headers={"Retry-After": "7"}), _resp()]
        assert _get("https://x", label="t").status_code == 200
        mock_sleep.assert_called_once_with(7)

    @patch("planning_center_reports.pco_client.time.sleep")
    @patch("planning_center_reports.pco_client.requests.get")
    def test_falls_back_to_exponential_backoff_without_retry_after(self, mock_get, mock_sleep):
        mock_get.side_effect = [_resp(status=429), _resp(status=429), _resp()]
        _get("https://x")
        assert [c.args[0] for c in mock_sleep.call_args_list] == [1, 2]

    @patch("planning_center_reports.pco_client.time.sleep")
    def test_throttle_waits_once_the_window_is_full(self, mock_sleep):
        for _ in range(pco_client._RATE_MAX):
            _throttle()
        mock_sleep.assert_not_called()
        _throttle()
        mock_sleep.assert_called_once()
        assert 0 < mock_sleep.call_args.args[0] <= pco_client._RATE_WINDOW_S

    @patch("planning_center_reports.pco_client.time.sleep")
    @patch("planning_center_reports.pco_client.requests.get")
    def test_returns_none_after_repeated_network_errors(self, mock_get, _sleep):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("down")
        assert _get("https://x") is None
        assert mock_get.call_count == pco_client._MAX_RETRIES


# ── Periods since a start date ────────────────────────────────────────────────

def _period(pid, dt):
    return {"id": pid, "attributes": {"starts_at": dt.strftime("%Y-%m-%dT%H:%M:%SZ")}}


class TestEventPeriodsSince:
    @patch("planning_center_reports.pco_client.requests.get")
    def test_keeps_past_periods_on_or_after_the_start_oldest_first(self, mock_get):
        now = datetime.now(UTC)
        sundays = [now - timedelta(weeks=w, hours=1) for w in range(5)]
        future = _period("future", now + timedelta(days=3))
        body = {"data": [future] + [_period(f"p{w}", d) for w, d in enumerate(sundays)], "links": {}}
        mock_get.return_value = _resp(body)
        since = (now - timedelta(weeks=2, days=1)).date()
        got = get_event_periods_since("ev", since)
        assert [p["id"] for p in got] == ["p2", "p1", "p0"]

    @patch("planning_center_reports.pco_client.requests.get")
    def test_stops_paging_once_older_than_the_start(self, mock_get):
        now = datetime.now(UTC)
        page1 = {"data": [_period("p0", now - timedelta(days=1))], "links": {"next": "https://next"}}
        page2 = {"data": [_period("old", now - timedelta(weeks=60))], "links": {"next": "https://more"}}
        mock_get.side_effect = [_resp(page1), _resp(page2)]
        got = get_event_periods_since("ev", (now - timedelta(weeks=4)).date())
        assert [p["id"] for p in got] == ["p0"]
        assert mock_get.call_count == 2

    @patch("planning_center_reports.pco_client.requests.get")
    def test_caps_the_number_of_periods(self, mock_get):
        now = datetime.now(UTC)
        body = {"data": [_period(f"p{w}", now - timedelta(weeks=w, hours=1)) for w in range(10)],
                "links": {}}
        mock_get.return_value = _resp(body)
        got = get_event_periods_since("ev", date(2000, 1, 1), max_periods=3)
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
    def test_returns_the_adult_primary_contact_with_contact_details(self, mock_get):
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
        g = get_guardians(["k1"])
        assert g == {"k1": {"name": "Ana Lopez", "phone": "(281) 555-0100", "address": "9 Main St, Houston"}}

    @patch("planning_center_reports.pco_client.requests.get")
    def test_a_child_head_of_household_is_never_shown_as_the_parent(self, mock_get):
        """When parents don't attend, PCO can make an older sibling the primary contact."""
        kids = {"data": [_person("k1", households=["h1"])],
                "included": [_household("h1", "sib", "Older Sibling")], "links": {}}
        sibling = {"data": [_person("sib", name="Older Sibling", child=True, birthdate="2011-01-01")],
                   "included": [], "links": {}}
        mock_get.side_effect = [_resp(kids), _resp(sibling)]
        assert get_guardians(["k1"]) == {}

    @patch("planning_center_reports.pco_client.requests.get")
    def test_a_minor_not_flagged_as_child_is_still_excluded(self, mock_get):
        teen = (date.today().year - 16)
        kids = {"data": [_person("k1", households=["h1"])],
                "included": [_household("h1", "sib", "Teen")], "links": {}}
        sibling = {"data": [_person("sib", name="Teen", child=False, birthdate=f"{teen}-01-01")],
                   "included": [], "links": {}}
        mock_get.side_effect = [_resp(kids), _resp(sibling)]
        assert get_guardians(["k1"]) == {}

    @patch("planning_center_reports.pco_client.requests.get")
    def test_kid_who_is_their_own_primary_contact_gets_no_parent(self, mock_get):
        kids = {"data": [_person("k1", households=["h1"])],
                "included": [_household("h1", "k1", "The Kid")], "links": {}}
        mock_get.side_effect = [_resp(kids)]
        assert get_guardians(["k1"]) == {}

    @patch("planning_center_reports.pco_client.requests.get")
    def test_batches_ids_one_hundred_per_request(self, mock_get):
        mock_get.return_value = _resp({"data": [], "included": [], "links": {}})
        get_guardians([str(i) for i in range(250)])
        id_lists = [c.kwargs["params"]["where[id]"].split(",") for c in mock_get.call_args_list]
        assert [len(ids) for ids in id_lists] == [100, 100, 50]

    def test_no_children_makes_no_requests(self):
        with patch("planning_center_reports.pco_client.requests.get") as mock_get:
            assert get_guardians([]) == {}
            mock_get.assert_not_called()
