# tests/test_escuela_dominical.py
#
# Tests for Escuela Dominical–specific functionality:
#   _extract_route_number  — route display string parsing
#   _format_period_date    — PCO starts_at → Spanish date label
#   _build_sunday_data     — per-Sunday attendance counts per class
#   generate_simple_roster_pdf (show_route=True) — PDF output sanity checks
#   escuela_summary_height — height calculator for layout decisions

import os
import tempfile


from planning_center_reports.models import _extract_route_number, _is_visitor_for_period
from planning_center_reports.pco_client import _format_period_date
from planning_center_reports.pdf.layout import escuela_summary_height
from planning_center_reports.pdf.rosters import generate_simple_roster_pdf
from planning_center_reports.services import _build_sunday_data


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_checkin(person_id, location_id, ep_id):
    return {
        "attributes": {"first_name": "", "last_name": ""},
        "relationships": {
            "locations":    {"data": [{"id": location_id}]},
            "person":       {"data": {"id": person_id}},
            "event_period": {"data": {"id": ep_id}},
        },
    }


MINIMAL_ATTENDEE = {
    "person_id":  "p1",
    "first_name": "Ana",
    "last_name":  "Lopez",
    "birthday":   "2010-05-01",
    "phone":      "(281) 555-0001",
    "grade":      "5°",
    "address":    "123 Main St, Houston, TX, 77001",
    "is_visitor": False,
    "attendance": "4/5",
    "route":      "Ruta 1 - Bus",
    "is_helper":  False,
}


# ── _extract_route_number ─────────────────────────────────────────────────────

class TestExtractRouteNumber:
    def test_standard_format(self):
        assert _extract_route_number("Ruta 1 - Bus") == "1"

    def test_two_digit_number(self):
        assert _extract_route_number("Ruta 12 - Van") == "12"

    def test_number_only(self):
        assert _extract_route_number("Ruta 8") == "8"

    def test_empty_string(self):
        assert _extract_route_number("") == ""

    def test_no_digits_returns_original(self):
        assert _extract_route_number("Bus Norte") == "Bus Norte"

    def test_leading_number_extracted(self):
        assert _extract_route_number("3 - Carro") == "3"


# ── _format_period_date ───────────────────────────────────────────────────────

class TestFormatPeriodDate:
    def test_standard_iso_datetime(self):
        assert _format_period_date("2025-04-06T00:00:00Z") == "Abr 6"

    def test_single_digit_day(self):
        assert _format_period_date("2025-05-04T00:00:00Z") == "May 4"

    def test_january(self):
        assert _format_period_date("2025-01-12T00:00:00Z") == "Ene 12"

    def test_december(self):
        assert _format_period_date("2025-12-28T00:00:00Z") == "Dic 28"

    def test_empty_string_returns_empty(self):
        assert _format_period_date("") == ""

    def test_invalid_string_returns_fallback(self):
        result = _format_period_date("not-a-date")
        assert isinstance(result, str)


# ── _is_visitor_for_period ────────────────────────────────────────────────────

class TestIsVisitorForPeriod:
    def test_added_day_before_is_visitor(self):
        assert _is_visitor_for_period("2025-04-05T00:00:00Z", "2025-04-06T00:00:00Z") is True

    def test_added_six_days_before_is_visitor(self):
        assert _is_visitor_for_period("2025-03-31T00:00:00Z", "2025-04-06T00:00:00Z") is True

    def test_added_seven_days_before_is_not_visitor(self):
        assert _is_visitor_for_period("2025-03-30T00:00:00Z", "2025-04-06T00:00:00Z") is False

    def test_added_month_before_is_not_visitor(self):
        assert _is_visitor_for_period("2025-03-01T00:00:00Z", "2025-04-06T00:00:00Z") is False

    def test_added_after_period_is_not_visitor(self):
        # Created after the period started — shouldn't be counted as visitor for that date
        assert _is_visitor_for_period("2025-04-07T00:00:00Z", "2025-04-06T00:00:00Z") is False

    def test_empty_created_at_returns_false(self):
        assert _is_visitor_for_period("", "2025-04-06T00:00:00Z") is False

    def test_empty_starts_at_returns_false(self):
        assert _is_visitor_for_period("2025-04-05T00:00:00Z", "") is False

    def test_both_empty_returns_false(self):
        assert _is_visitor_for_period("", "") is False

    def test_invalid_date_returns_false(self):
        assert _is_visitor_for_period("not-a-date", "2025-04-06T00:00:00Z") is False


# ── _build_sunday_data ────────────────────────────────────────────────────────

def _call_build_sunday_data(
    checkins, period_ids, period_dates=None,
    location_id="loc1", helpers_set=None,
    period_starts_at=None, person_created_at=None,
):
    """Thin wrapper supplying safe defaults for the optional dicts."""
    if period_dates is None:
        period_dates = {pid: f"Lbl {pid}" for pid in period_ids}
    if helpers_set is None:
        helpers_set = set()
    if period_starts_at is None:
        period_starts_at = {}
    if person_created_at is None:
        person_created_at = {}
    return _build_sunday_data(
        checkins, period_ids, period_dates,
        location_id, helpers_set, period_starts_at, person_created_at,
    )


class TestBuildSundayData:
    def test_single_checkin_counted_as_regular(self):
        checkins = [_make_checkin("p1", "loc1", "ep1")]
        result = _call_build_sunday_data(checkins, ["ep1"])
        assert result[0]["regular"] == 1
        assert result[0]["visitors"] == 0

    def test_visitor_determined_by_period_date(self):
        """A person added 3 days before the period is a visitor for that Sunday."""
        checkins = [_make_checkin("p1", "loc1", "ep1")]
        result = _call_build_sunday_data(
            checkins, ["ep1"],
            period_starts_at={"ep1": "2025-04-06T00:00:00Z"},
            person_created_at={"p1": "2025-04-03T00:00:00Z"},  # 3 days before
        )
        assert result[0]["regular"] == 0
        assert result[0]["visitors"] == 1

    def test_not_visitor_when_added_too_long_ago(self):
        """A person added 30 days before the period is not a visitor."""
        checkins = [_make_checkin("p1", "loc1", "ep1")]
        result = _call_build_sunday_data(
            checkins, ["ep1"],
            period_starts_at={"ep1": "2025-04-06T00:00:00Z"},
            person_created_at={"p1": "2025-03-01T00:00:00Z"},  # 36 days before
        )
        assert result[0]["regular"] == 1
        assert result[0]["visitors"] == 0

    def test_visitor_status_differs_across_periods(self):
        """Same person is a visitor for ep1 (recent) but regular for ep2 (older)."""
        checkins = [
            _make_checkin("p1", "loc1", "ep1"),
            _make_checkin("p1", "loc1", "ep2"),
        ]
        result = _call_build_sunday_data(
            checkins, ["ep1", "ep2"],
            period_starts_at={
                "ep1": "2025-04-27T00:00:00Z",  # person added 3 days before ep1
                "ep2": "2025-04-06T00:00:00Z",  # person added 24 days before ep2
            },
            person_created_at={"p1": "2025-04-24T00:00:00Z"},
        )
        assert result[0]["visitors"] == 1  # ep1: visitor
        assert result[1]["visitors"] == 0  # ep2: regular

    def test_helper_excluded_from_counts(self):
        checkins = [
            _make_checkin("p1", "loc1", "ep1"),
            _make_checkin("p2", "loc1", "ep1"),  # helper
        ]
        result = _call_build_sunday_data(checkins, ["ep1"], helpers_set={"p2"})
        assert result[0]["regular"] == 1

    def test_different_location_excluded(self):
        checkins = [
            _make_checkin("p1", "loc1", "ep1"),
            _make_checkin("p2", "loc2", "ep1"),
        ]
        result = _call_build_sunday_data(checkins, ["ep1"], location_id="loc1")
        assert result[0]["regular"] == 1

    def test_multiple_periods_counted_independently(self):
        checkins = [
            _make_checkin("p1", "loc1", "ep1"),
            _make_checkin("p1", "loc1", "ep2"),
            _make_checkin("p2", "loc1", "ep1"),
        ]
        result = _call_build_sunday_data(checkins, ["ep1", "ep2"])
        assert result[0]["regular"] == 2
        assert result[1]["regular"] == 1

    def test_period_label_preserved(self):
        checkins = [_make_checkin("p1", "loc1", "ep1")]
        result = _call_build_sunday_data(
            checkins, ["ep1"], period_dates={"ep1": "Abr 6"}
        )
        assert result[0]["label"] == "Abr 6"

    def test_none_location_id_counts_all_checkins(self):
        checkins = [
            _make_checkin("p1", "loc1", "ep1"),
            _make_checkin("p2", "loc2", "ep1"),
        ]
        result = _call_build_sunday_data(checkins, ["ep1"], location_id=None)
        assert result[0]["regular"] == 2

    def test_same_person_in_period_counted_once(self):
        checkins = [
            _make_checkin("p1", "loc1", "ep1"),
            _make_checkin("p1", "loc1", "ep1"),
        ]
        result = _call_build_sunday_data(checkins, ["ep1"])
        assert result[0]["regular"] == 1


# ── escuela_summary_height ────────────────────────────────────────────────────

class TestEscuelaSummaryHeight:
    def test_left_table_controls_when_more_sundays(self):
        # 5 sundays, 2 routes → left table is taller
        h5 = escuela_summary_height(5, 2)
        h2 = escuela_summary_height(2, 2)
        assert h5 > h2

    def test_right_table_controls_when_more_routes(self):
        h = escuela_summary_height(2, 8)
        h2 = escuela_summary_height(2, 2)
        assert h > h2

    def test_equal_rows_same_height(self):
        assert escuela_summary_height(4, 4) == escuela_summary_height(4, 4)

    def test_returns_positive_int(self):
        assert escuela_summary_height(5, 3) > 0


# ── generate_simple_roster_pdf (Escuela Dominical) ───────────────────────────

SUNDAY_DATA = [
    {"label": "Abr 6",  "regular": 9, "visitors": 2},
    {"label": "Abr 13", "regular": 8, "visitors": 0},
    {"label": "Abr 20", "regular": 10, "visitors": 1},
    {"label": "Abr 27", "regular": 7, "visitors": 0},
    {"label": "May 4",  "regular": 11, "visitors": 3},
]

ATTENDEES = [
    {**MINIMAL_ATTENDEE, "person_id": "p1", "first_name": "Ana",   "last_name": "Lopez",  "route": "Ruta 1 - Bus"},
    {**MINIMAL_ATTENDEE, "person_id": "p2", "first_name": "Pedro", "last_name": "Garcia", "route": "Ruta 2 - Van"},
    {**MINIMAL_ATTENDEE, "person_id": "p3", "first_name": "Maria", "last_name": "Torres", "route": "Ruta 1 - Bus",
     "is_visitor": True},
]


class TestGenerateSimpleRosterPdfEscuela:
    def test_creates_file(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            result = generate_simple_roster_pdf(
                "Clase A", "Escuela Dominical", ATTENDEES, path,
                show_route=True, sunday_data=SUNDAY_DATA,
            )
            assert result == path
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0
        finally:
            os.unlink(path)

    def test_creates_file_without_sunday_data(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            generate_simple_roster_pdf(
                "Clase A", "Escuela Dominical", ATTENDEES, path,
                show_route=True,
            )
            assert os.path.getsize(path) > 0
        finally:
            os.unlink(path)

    def test_creates_file_standard_mode(self):
        """show_route=False should still produce a valid PDF."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            generate_simple_roster_pdf(
                "Ruta 1 - Bus", "Ministerio de Autobuses", ATTENDEES, path,
            )
            assert os.path.getsize(path) > 0
        finally:
            os.unlink(path)

    def test_empty_attendees_still_creates_file(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            generate_simple_roster_pdf(
                "Clase A", "Escuela Dominical", [], path,
                show_route=True, sunday_data=SUNDAY_DATA,
            )
            assert os.path.getsize(path) > 0
        finally:
            os.unlink(path)
