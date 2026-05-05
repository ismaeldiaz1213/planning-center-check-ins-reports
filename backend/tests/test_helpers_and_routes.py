# tests/test_helpers_and_routes.py
#
# Tests for helpers identification and route mapping in services.py.
# These tests mock the PCO API calls to verify the business logic without
# needing real credentials or network access.

from unittest.mock import patch

from planning_center_reports.services import _build_attendees, _get_route_mapping


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


def _make_location_included(location_id="loc1", name="Ruta 1 - Bus"):
    """Build a Location included object."""
    return {"type": "Location", "id": location_id, "attributes": {"name": name}}


def _make_person_included(person_id="p1", birthday="2000-01-01"):
    """Build a Person included object with a birthday."""
    return {
        "type": "Person",
        "id": person_id,
        "attributes": {"birthdate": birthday},
    }


EMPTY_PERSON = {"phone": "", "address": "", "birthday": "", "grade": "", "created_at": ""}


# ── Tests for _build_attendees with helpers_set ────────────────────────────────

class TestBuildAttendeesWithHelpers:
    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_helper_marked_correctly(self, _mock):
        """A person in helpers_set should have is_helper=True."""
        checkins = [_make_checkin("p1", "Ana", "Lopez", "loc1", "ep1")]
        included = [_make_location_included()]
        helpers_set = {"p1"}

        grouped, _ = _build_attendees(checkins, included, helpers_set=helpers_set)
        assert grouped["Ruta 1 - Bus"][0]["is_helper"] is True

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_non_helper_marked_correctly(self, _mock):
        """A person NOT in helpers_set should have is_helper=False."""
        checkins = [_make_checkin("p1", "Ana", "Lopez", "loc1", "ep1")]
        included = [_make_location_included()]
        helpers_set = set()

        grouped, _ = _build_attendees(checkins, included, helpers_set=helpers_set)
        assert grouped["Ruta 1 - Bus"][0]["is_helper"] is False

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_multiple_helpers_marked(self, _mock):
        """Multiple helpers should all be marked correctly."""
        checkins = [
            _make_checkin("p1", "Ana", "Lopez", "loc1", "ep1"),
            _make_checkin("p2", "Pedro", "Garcia", "loc1", "ep1"),
            _make_checkin("p3", "Maria", "Torres", "loc1", "ep1"),
        ]
        included = [_make_location_included()]
        helpers_set = {"p1", "p3"}

        grouped, _ = _build_attendees(checkins, included, helpers_set=helpers_set)
        assert grouped["Ruta 1 - Bus"][0]["is_helper"] is True   # p1
        assert grouped["Ruta 1 - Bus"][1]["is_helper"] is False  # p2
        assert grouped["Ruta 1 - Bus"][2]["is_helper"] is True   # p3


# ── Tests for _build_attendees with route_map ──────────────────────────────────

class TestBuildAttendeesWithRoutes:
    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_route_assigned_correctly(self, _mock):
        """A person in route_map should have their route assigned."""
        checkins = [_make_checkin("p1", "Ana", "Lopez", "loc1", "ep1")]
        included = [_make_location_included()]
        route_map = {"p1": "Ruta 1 - Bus"}

        grouped, _ = _build_attendees(checkins, included, route_map=route_map)
        assert grouped["Ruta 1 - Bus"][0]["route"] == "Ruta 1 - Bus"

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_no_route_when_not_in_map(self, _mock):
        """A person NOT in route_map should have empty route."""
        checkins = [_make_checkin("p1", "Ana", "Lopez", "loc1", "ep1")]
        included = [_make_location_included()]
        route_map = {}

        grouped, _ = _build_attendees(checkins, included, route_map=route_map)
        assert grouped["Ruta 1 - Bus"][0]["route"] == ""

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_route_persists_across_locations(self, _mock):
        """Route mapping should work across different check-in locations."""
        checkins = [
            _make_checkin("p1", "Ana", "Lopez", "loc1", "ep1"),
            _make_checkin("p2", "Pedro", "Garcia", "loc2", "ep1"),
        ]
        included = [
            _make_location_included("loc1", "Escuela Dominical - Clase A"),
            _make_location_included("loc2", "Escuela Dominical - Clase B"),
        ]
        route_map = {
            "p1": "Ruta 1 - Bus",
            "p2": "Ruta 2 - Bus",
        }

        grouped, _ = _build_attendees(checkins, included, route_map=route_map)
        assert grouped["Escuela Dominical - Clase A"][0]["route"] == "Ruta 1 - Bus"
        assert grouped["Escuela Dominical - Clase B"][0]["route"] == "Ruta 2 - Bus"


# ── Tests for _build_attendees with both helpers and routes ─────────────────────

class TestBuildAttendeesWithBothHelpersAndRoutes:
    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_helper_in_route_map_gets_blank_route(self, _mock):
        """A helper in route_map should still have route='' — route is suppressed for helpers."""
        checkins = [_make_checkin("p1", "Ana", "Lopez", "loc1", "ep1")]
        included = [_make_location_included()]
        helpers_set = {"p1"}
        route_map = {"p1": "Ruta 1 - Bus"}

        grouped, _ = _build_attendees(
            checkins, included,
            helpers_set=helpers_set,
            route_map=route_map
        )
        record = grouped["Ruta 1 - Bus"][0]
        assert record["is_helper"] is True
        assert record["route"] == ""

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_mixed_helpers_and_routes(self, _mock):
        """Test a group with mixed helper/non-helper and route assignments."""
        checkins = [
            _make_checkin("p1", "Ana", "Lopez", "loc1", "ep1"),      # helper, in route_map → blank
            _make_checkin("p2", "Pedro", "Garcia", "loc1", "ep1"),    # helper, not in route_map → blank
            _make_checkin("p3", "Maria", "Torres", "loc1", "ep1"),    # not helper, routed → gets route
            _make_checkin("p4", "John", "Doe", "loc1", "ep1"),        # not helper, no route → blank
        ]
        included = [_make_location_included()]
        helpers_set = {"p1", "p2"}
        route_map = {"p1": "Ruta 1 - Bus", "p3": "Ruta 2 - Bus"}

        grouped, _ = _build_attendees(
            checkins, included,
            helpers_set=helpers_set,
            route_map=route_map
        )
        records = {r["person_id"]: r for r in grouped["Ruta 1 - Bus"]}

        assert records["p1"]["is_helper"] is True
        assert records["p1"]["route"] == ""       # suppressed — helper

        assert records["p2"]["is_helper"] is True
        assert records["p2"]["route"] == ""       # suppressed — helper

        assert records["p3"]["is_helper"] is False
        assert records["p3"]["route"] == "Ruta 2 - Bus"

        assert records["p4"]["is_helper"] is False
        assert records["p4"]["route"] == ""


# ── Tests for _get_route_mapping ───────────────────────────────────────────────

class TestGetRouteMapping:
    @patch("planning_center_reports.services.get_checkins_for_event_periods")
    @patch("planning_center_reports.services.get_recent_event_periods")
    @patch("planning_center_reports.services.get_event_id")
    def test_route_mapping_extracts_first_location(
        self,
        mock_get_event_id,
        mock_get_periods,
        mock_get_checkins,
    ):
        """_get_route_mapping should extract person → first route they attended."""
        mock_get_event_id.return_value = "event1"
        mock_get_periods.return_value = (["ep1", "ep2"], {"ep1": "Abr 6", "ep2": "Abr 13"}, {})

        checkins = [
            _make_checkin("p1", "Ana", "Lopez", "loc1", "ep1"),
            _make_checkin("p2", "Pedro", "Garcia", "loc2", "ep1"),
        ]
        included = [
            _make_location_included("loc1", "Ruta 1 - Bus"),
            _make_location_included("loc2", "Ruta 2 - Van"),
        ]
        mock_get_checkins.return_value = (checkins, included)

        route_map = _get_route_mapping(weeks=5)

        assert route_map["p1"] == "Ruta 1 - Bus"
        assert route_map["p2"] == "Ruta 2 - Van"

    @patch("planning_center_reports.services.get_checkins_for_event_periods")
    @patch("planning_center_reports.services.get_recent_event_periods")
    @patch("planning_center_reports.services.get_event_id")
    def test_route_mapping_deduplicates_by_person(
        self,
        mock_get_event_id,
        mock_get_periods,
        mock_get_checkins,
    ):
        """A person appearing in multiple periods should map to only one route."""
        mock_get_event_id.return_value = "event1"
        mock_get_periods.return_value = (["ep1", "ep2"], {"ep1": "Abr 6", "ep2": "Abr 13"}, {})

        # p1 checks in to loc1 multiple times
        checkins = [
            _make_checkin("p1", "Ana", "Lopez", "loc1", "ep1"),
            _make_checkin("p1", "Ana", "Lopez", "loc1", "ep2"),
        ]
        included = [_make_location_included("loc1", "Ruta 1 - Bus")]
        mock_get_checkins.return_value = (checkins, included)

        route_map = _get_route_mapping(weeks=5)

        assert len(route_map) == 1
        assert route_map["p1"] == "Ruta 1 - Bus"

    @patch("planning_center_reports.services.get_event_id")
    def test_route_mapping_handles_missing_event(self, mock_get_event_id):
        """_get_route_mapping should gracefully handle missing Rutas event."""
        mock_get_event_id.side_effect = Exception("Event not found")

        route_map = _get_route_mapping(weeks=5)

        assert route_map == {}


# ── Helper route suppression in _build_attendees ───────────────────────────────

class TestHelperRouteSupression:
    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_helper_does_not_get_route(self, _mock):
        """A person in both helpers_set and route_map should have route=''."""
        checkins = [_make_checkin("p1", "Ana", "Lopez", "loc1", "ep1")]
        included = [_make_location_included()]
        helpers_set = {"p1"}
        route_map   = {"p1": "Ruta 1 - Bus"}

        grouped, _ = _build_attendees(
            checkins, included, helpers_set=helpers_set, route_map=route_map
        )
        assert grouped["Ruta 1 - Bus"][0]["route"] == ""

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_non_helper_gets_route(self, _mock):
        """A person in route_map but NOT in helpers_set should keep their route."""
        checkins = [_make_checkin("p1", "Ana", "Lopez", "loc1", "ep1")]
        included = [_make_location_included()]
        helpers_set = set()
        route_map   = {"p1": "Ruta 1 - Bus"}

        grouped, _ = _build_attendees(
            checkins, included, helpers_set=helpers_set, route_map=route_map
        )
        assert grouped["Ruta 1 - Bus"][0]["route"] == "Ruta 1 - Bus"

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_helper_remains_on_roster(self, _mock):
        """Helpers must appear in grouped output — they are not filtered out."""
        checkins = [
            _make_checkin("p1", "Ana",   "Lopez",  "loc1", "ep1"),  # regular
            _make_checkin("p2", "Pedro", "Garcia", "loc1", "ep1"),  # helper
        ]
        included = [_make_location_included()]
        helpers_set = {"p2"}

        grouped, _ = _build_attendees(checkins, included, helpers_set=helpers_set)
        ids = {r["person_id"] for r in grouped["Ruta 1 - Bus"]}
        assert "p1" in ids
        assert "p2" in ids
