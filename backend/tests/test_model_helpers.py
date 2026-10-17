# tests/test_model_helpers.py
#
# Small display helpers shared by the PDFs and the scripts:
#   _extract_route_number  — route display string parsing
#   _format_period_date    — PCO starts_at → Spanish date label
#   _is_visitor_for_period — added to PCO within the week before a Sunday

from planning_center_reports.models import _extract_route_number, _is_visitor_for_period
from planning_center_reports.pco_client import _format_period_date

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
