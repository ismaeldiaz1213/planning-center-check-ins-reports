# tests/test_formatting.py
#
# Tests for date/display formatting helpers in models.py.
# These are all pure functions with no external dependencies.

from datetime import datetime

from planning_center_reports.models import _fecha_es, _fmt_birthday


class TestFmtBirthday:
    def test_standard_iso_date(self):
        assert _fmt_birthday("2020-05-21") == "05/21/2020"

    def test_zero_padded_month_and_day(self):
        assert _fmt_birthday("1985-01-09") == "01/09/1985"

    def test_empty_string_returns_empty(self):
        assert _fmt_birthday("") == ""

    def test_none_returns_empty(self):
        assert _fmt_birthday(None) == ""

    def test_malformed_returns_original(self):
        # Not a valid ISO date — return the raw value unchanged
        assert _fmt_birthday("not-a-date") == "not-a-date"


class TestFechaEs:
    def test_contains_day(self):
        dt = datetime(2026, 3, 15, 10, 30)
        assert "15" in _fecha_es(dt)

    def test_spanish_month_name(self):
        dt = datetime(2026, 3, 15, 10, 30)
        assert "marzo" in _fecha_es(dt)

    def test_contains_year(self):
        dt = datetime(2026, 3, 15, 10, 30)
        assert "2026" in _fecha_es(dt)

    def test_contains_time(self):
        dt = datetime(2026, 3, 15, 10, 5)
        assert "10:05" in _fecha_es(dt)

    def test_all_spanish_months(self):
        months = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        ]
        for i, month in enumerate(months, start=1):
            dt = datetime(2026, i, 1)
            assert month in _fecha_es(dt), f"Month {i} should render as '{month}'"

    def test_no_arg_returns_string(self):
        # Without an explicit datetime it uses now() — just check the return type
        result = _fecha_es()
        assert isinstance(result, str)
        assert "Generado el" in result
