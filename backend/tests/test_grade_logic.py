# tests/test_grade_logic.py
#
# Tests for age and grade resolution helpers in models.py.
# Ages are computed relative to today, so we derive test birthdays from the
# current date to avoid tests breaking as time passes.

from datetime import date

from planning_center_reports.models import _age_from_birthday, _is_minor, _resolve_grade


def _birthday_for_age(years: int) -> str:
    """Return an ISO-8601 birthday string for a person who is exactly `years` old today."""
    today = date.today()
    return date(today.year - years, today.month, today.day).strftime("%Y-%m-%d")


class TestAgeFromBirthday:
    def test_known_age(self):
        assert _age_from_birthday(_birthday_for_age(10)) == 10

    def test_adult(self):
        assert _age_from_birthday(_birthday_for_age(30)) == 30

    def test_infant(self):
        assert _age_from_birthday(_birthday_for_age(1)) == 1

    def test_empty_string_returns_none(self):
        assert _age_from_birthday("") is None

    def test_none_returns_none(self):
        assert _age_from_birthday(None) is None

    def test_malformed_returns_none(self):
        assert _age_from_birthday("not-a-date") is None

    def test_invalid_date_returns_none(self):
        assert _age_from_birthday("2000-13-99") is None


class TestIsMinor:
    def test_child_is_minor(self):
        assert _is_minor(_birthday_for_age(10)) is True

    def test_teenager_is_minor(self):
        assert _is_minor(_birthday_for_age(17)) is True

    def test_adult_is_not_minor(self):
        assert _is_minor(_birthday_for_age(18)) is False

    def test_thirty_year_old_is_not_minor(self):
        assert _is_minor(_birthday_for_age(30)) is False

    def test_missing_birthday_is_not_minor(self):
        # Without a birthday we cannot determine minority — default to False
        assert _is_minor("") is False


class TestResolveGrade:
    def test_infant_returns_nursery(self):
        assert _resolve_grade("", _birthday_for_age(1)) == "Nursery"

    def test_two_year_old_returns_nursery(self):
        assert _resolve_grade("", _birthday_for_age(2)) == "Nursery"

    def test_three_year_old(self):
        assert _resolve_grade("", _birthday_for_age(3)) == "3 años"

    def test_four_year_old(self):
        assert _resolve_grade("", _birthday_for_age(4)) == "4 años"

    def test_older_child_uses_pco_grade(self):
        # Age 10 → outside the hardcoded labels; use whatever PCO says
        assert _resolve_grade("5°", _birthday_for_age(10)) == "5°"

    def test_older_child_with_no_grade_returns_empty(self):
        assert _resolve_grade("", _birthday_for_age(10)) == ""

    def test_adult_uses_pco_grade(self):
        assert _resolve_grade("12°", _birthday_for_age(25)) == "12°"

    def test_no_birthday_falls_back_to_pco_grade(self):
        assert _resolve_grade("7°", "") == "7°"

    def test_no_birthday_no_grade_returns_empty(self):
        assert _resolve_grade("", "") == ""
