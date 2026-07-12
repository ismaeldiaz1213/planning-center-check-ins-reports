# tests/test_location_filter.py
#
# Tests for the location_filter parameter added to _build_attendees and for
# the --dry-run / --location CLI flags added to cli.py.
#
# get_person_details is mocked in all tests because it makes real HTTP requests.

import sys
from unittest.mock import patch

import pytest

from planning_center_reports.services import _build_attendees, _filter_locations


# ── Shared fixtures ────────────────────────────────────────────────────────────

EMPTY_PERSON = {"phone": "", "address": "", "birthday": "", "grade": "", "created_at": ""}


def _make_checkin(person_id, first, last, location_id, ep_id="ep1"):
    return {
        "attributes": {"first_name": first, "last_name": last},
        "relationships": {
            "locations":    {"data": [{"id": location_id}]},
            "person":       {"data": {"id": person_id}},
            "event_period": {"data": {"id": ep_id}},
        },
    }


def _make_included(*locations):
    """locations: list of (id, name) tuples."""
    return [
        {"type": "Location", "id": loc_id, "attributes": {"name": loc_name}}
        for loc_id, loc_name in locations
    ]


# Two-location fixture: Ruta 1 - Bus and Ruta 8 - Bus
def _two_route_data():
    checkins = [
        _make_checkin("p1", "Ana",    "Lopez", "loc1"),
        _make_checkin("p2", "Carlos", "Ruiz",  "loc8"),
        _make_checkin("p3", "Maria",  "Gomez", "loc8"),
    ]
    included = _make_included(("loc1", "Ruta 1 - Bus"), ("loc8", "Ruta 8 - Bus"))
    return checkins, included


# ── _build_attendees: location_filter behaviour ────────────────────────────────

class TestLocationFilter:
    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_no_filter_returns_all_locations(self, _mock):
        checkins, included = _two_route_data()
        grouped, _ = _build_attendees(checkins, included, location_filter=None)
        assert "Ruta 1 - Bus" in grouped
        assert "Ruta 8 - Bus" in grouped

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_filter_returns_only_matching_location(self, _mock):
        checkins, included = _two_route_data()
        grouped, _ = _build_attendees(checkins, included, location_filter="Ruta 8")
        assert "Ruta 8 - Bus" in grouped
        assert "Ruta 1 - Bus" not in grouped

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_filter_is_case_insensitive(self, _mock):
        checkins, included = _two_route_data()
        grouped, _ = _build_attendees(checkins, included, location_filter="ruta 8")
        assert "Ruta 8 - Bus" in grouped

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_filter_is_substring_match(self, _mock):
        checkins, included = _two_route_data()
        grouped, _ = _build_attendees(checkins, included, location_filter="Bus")
        # "Bus" appears in both — both should match
        assert "Ruta 1 - Bus" in grouped
        assert "Ruta 8 - Bus" in grouped

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_filter_no_match_returns_empty_grouped(self, _mock):
        checkins, included = _two_route_data()
        grouped, _ = _build_attendees(checkins, included, location_filter="Nursery")
        assert grouped == {}

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_location_lookup_still_contains_all_locations_when_filtered(self, _mock):
        """location_lookup must always list ALL locations so the 'no match' error
        message can show the user what's available."""
        checkins, included = _two_route_data()
        _, location_lookup = _build_attendees(checkins, included, location_filter="Ruta 8")
        assert "Ruta 1 - Bus" in location_lookup.values()
        assert "Ruta 8 - Bus" in location_lookup.values()

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_filter_skips_person_detail_fetch_for_excluded_locations(self, mock_get):
        """The expensive get_person_details call must NOT be made for people
        in locations that don't match the filter."""
        checkins, included = _two_route_data()
        # p1 is in Ruta 1 (excluded), p2 and p3 are in Ruta 8 (included)
        _build_attendees(checkins, included, location_filter="Ruta 8")
        # Only 2 calls expected (p2 and p3), not 3
        assert mock_get.call_count == 2

    @patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON)
    def test_filtered_attendees_are_correct(self, _mock):
        checkins, included = _two_route_data()
        grouped, _ = _build_attendees(checkins, included, location_filter="Ruta 8")
        names = {r["first_name"] for r in grouped["Ruta 8 - Bus"]}
        assert names == {"Carlos", "Maria"}


# ── _filter_locations helper ───────────────────────────────────────────────────

class TestFilterLocations:
    def test_returns_all_when_no_filter(self):
        grouped = {"Ruta 1": [], "Ruta 8": []}
        assert _filter_locations(grouped, None) is grouped

    def test_returns_matching_subset(self):
        grouped = {"Ruta 1 - Bus": [1], "Ruta 8 - Bus": [2], "Nursery": [3]}
        result = _filter_locations(grouped, "Ruta 8")
        assert list(result.keys()) == ["Ruta 8 - Bus"]

    def test_exits_when_no_match(self):
        grouped = {"Ruta 1 - Bus": [], "Nursery": []}
        with pytest.raises(SystemExit):
            _filter_locations(grouped, "Kinder")

    def test_case_insensitive_match(self):
        grouped = {"Ruta 8 - Bus": []}
        result = _filter_locations(grouped, "ruta 8")
        assert "Ruta 8 - Bus" in result


# ── CLI: --dry-run and --location flags ───────────────────────────────────────

class TestCLIFlags:
    @patch("planning_center_reports.cli.run_rutas")
    def test_dry_run_flag_passed_to_run_rutas(self, mock_run, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "--dry-run", "Rutas"])
        from planning_center_reports.cli import main
        main()
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["dry_run"] is True

    @patch("planning_center_reports.cli.run_rutas")
    def test_location_flag_passed_to_run_rutas(self, mock_run, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "--location", "Ruta 8", "Rutas"])
        from planning_center_reports.cli import main
        main()
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["location_filter"] == "Ruta 8"

    @patch("planning_center_reports.cli.run_rutas")
    def test_output_dir_flag_passed_to_run_rutas(self, mock_run, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "--dry-run", "--output-dir", "/tmp/test", "Rutas"])
        from planning_center_reports.cli import main
        main()
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["output_dir"] == "/tmp/test"

    @patch("planning_center_reports.cli.run_escuela_dominical")
    def test_dry_run_flag_passed_to_run_escuela(self, mock_run, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "--dry-run", "Escuela Dominical"])
        from planning_center_reports.cli import main
        main()
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["dry_run"] is True

    @patch("planning_center_reports.cli.run_rutas")
    def test_no_dry_run_by_default(self, mock_run, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "Rutas"])
        from planning_center_reports.cli import main
        main()
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["dry_run"] is False

    @patch("planning_center_reports.cli.run_rutas")
    def test_no_location_filter_by_default(self, mock_run, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "Rutas"])
        from planning_center_reports.cli import main
        main()
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["location_filter"] is None
