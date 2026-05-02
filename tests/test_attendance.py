# tests/test_attendance.py
#
# Tests for the _build_attendees function in services.py, which transforms raw
# PCO check-in API data into grouped attendee records.
#
# get_person_details is mocked in all tests because it makes real HTTP requests.
# The mock returns a minimal dict so the code paths that use person details still
# execute, just without hitting the network.

from unittest.mock import patch

from planning_center_reports.services import _build_attendees

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_checkin(person_id, first, last, location_id, ep_id):
    """Build a minimal PCO check-in object for testing."""
    return {
        "attributes": {"first_name": first, "last_name": last},
        "relationships": {
            "locations":    {"data": [{"id": location_id}]},
            "person":       {"data": {"id": person_id}},
            "event_period": {"data": {"id": ep_id}},
        },
    }


def _make_included(location_id="loc1", location_name="Ruta 1"):
    """Build a minimal included array with one Location and no Person objects."""
    return [
        {"type": "Location", "id": location_id, "attributes": {"name": location_name}},
    ]


EMPTY_PERSON = {"phone": "", "address": "", "birthday": "", "grade": "", "created_at": ""}


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestBuildAttendeesBasic:
    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_single_checkin_produces_one_record(self, _mock):
        checkins = [_make_checkin("p1", "Ana", "Lopez", "loc1", "ep1")]
        included = _make_included()
        grouped, loc_lookup = _build_attendees(checkins, included, total_weeks=1)
        assert "Ruta 1" in grouped
        assert len(grouped["Ruta 1"]) == 1

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_record_has_expected_fields(self, _mock):
        checkins = [_make_checkin("p1", "Ana", "Lopez", "loc1", "ep1")]
        included = _make_included()
        grouped, _ = _build_attendees(checkins, included, total_weeks=5)
        record = grouped["Ruta 1"][0]
        assert record["first_name"] == "Ana"
        assert record["last_name"]  == "Lopez"
        assert record["person_id"]  == "p1"

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_location_lookup_populated(self, _mock):
        checkins = [_make_checkin("p1", "Ana", "Lopez", "loc1", "ep1")]
        included = _make_included()
        _, loc_lookup = _build_attendees(checkins, included)
        assert loc_lookup["loc1"] == "Ruta 1"


class TestDeduplication:
    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_same_person_across_weeks_deduped(self, _mock):
        """A person who checked in on two different Sundays should appear once."""
        checkins = [
            _make_checkin("p1", "Ana", "Lopez", "loc1", "ep1"),
            _make_checkin("p1", "Ana", "Lopez", "loc1", "ep2"),
        ]
        included = _make_included()
        grouped, _ = _build_attendees(checkins, included, total_weeks=2)
        assert len(grouped["Ruta 1"]) == 1

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_two_different_people_both_appear(self, _mock):
        checkins = [
            _make_checkin("p1", "Ana",   "Lopez",  "loc1", "ep1"),
            _make_checkin("p2", "Pedro", "Garcia", "loc1", "ep1"),
        ]
        included = _make_included()
        grouped, _ = _build_attendees(checkins, included)
        assert len(grouped["Ruta 1"]) == 2

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_same_person_different_locations_appear_separately(self, _mock):
        """The same person on two different bus routes should produce two records."""
        included = [
            {"type": "Location", "id": "loc1", "attributes": {"name": "Ruta 1"}},
            {"type": "Location", "id": "loc2", "attributes": {"name": "Ruta 2"}},
        ]
        checkins = [
            _make_checkin("p1", "Ana", "Lopez", "loc1", "ep1"),
            _make_checkin("p1", "Ana", "Lopez", "loc2", "ep1"),
        ]
        grouped, _ = _build_attendees(checkins, included)
        assert len(grouped["Ruta 1"]) == 1
        assert len(grouped["Ruta 2"]) == 1


class TestAttendanceCounting:
    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_attended_all_weeks(self, _mock):
        """Person present for all 3 event periods → attendance = "3/3"."""
        checkins = [
            _make_checkin("p1", "Ana", "Lopez", "loc1", "ep1"),
            _make_checkin("p1", "Ana", "Lopez", "loc1", "ep2"),
            _make_checkin("p1", "Ana", "Lopez", "loc1", "ep3"),
        ]
        included = _make_included()
        grouped, _ = _build_attendees(checkins, included, total_weeks=3)
        assert grouped["Ruta 1"][0]["attendance"] == "3/3"

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_attended_partial_weeks(self, _mock):
        """Person present for 2 of 5 event periods → attendance = "2/5"."""
        checkins = [
            _make_checkin("p1", "Ana", "Lopez", "loc1", "ep1"),
            _make_checkin("p1", "Ana", "Lopez", "loc1", "ep3"),
        ]
        included = _make_included()
        grouped, _ = _build_attendees(checkins, included, total_weeks=5)
        assert grouped["Ruta 1"][0]["attendance"] == "2/5"

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_checkin_without_person_has_empty_attendance(self, _mock):
        """A check-in with no associated person record should have no attendance string."""
        checkin = {
            "attributes": {"first_name": "Guest", "last_name": "Visitor"},
            "relationships": {
                "locations":    {"data": [{"id": "loc1"}]},
                "person":       {"data": None},
                "event_period": {"data": {"id": "ep1"}},
            },
        }
        included = _make_included()
        grouped, _ = _build_attendees([checkin], included)
        assert grouped["Ruta 1"][0]["attendance"] == ""


class TestLocationGrouping:
    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_attendees_split_by_location(self, _mock):
        included = [
            {"type": "Location", "id": "loc1", "attributes": {"name": "Ruta 1"}},
            {"type": "Location", "id": "loc2", "attributes": {"name": "Ruta 2"}},
        ]
        checkins = [
            _make_checkin("p1", "Ana",   "Lopez",  "loc1", "ep1"),
            _make_checkin("p2", "Pedro", "Garcia", "loc2", "ep1"),
        ]
        grouped, _ = _build_attendees(checkins, included)
        assert "Ruta 1" in grouped
        assert "Ruta 2" in grouped
        assert grouped["Ruta 1"][0]["first_name"] == "Ana"
        assert grouped["Ruta 2"][0]["first_name"] == "Pedro"
