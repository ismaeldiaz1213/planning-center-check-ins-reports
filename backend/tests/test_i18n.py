# tests/test_i18n.py
#
# The language catalogs must stay interchangeable: same keys, same
# {placeholders}, same shape of cover page. Otherwise a string added in one
# language crashes (or silently goes missing) for churches using the other.

import string
from datetime import date, datetime

import pytest

from planning_center_reports.i18n import CATALOGS, catalog

ES = catalog("es")
OTHERS = [c for code, c in CATALOGS.items() if code != "es"]


def _fields(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


@pytest.mark.parametrize("other", OTHERS, ids=lambda c: c.code)
class TestCatalogParity:
    def test_same_text_keys(self, other):
        assert set(other.text) == set(ES.text)

    def test_same_placeholders(self, other):
        for key, template in ES.text.items():
            if key.startswith("date."):
                continue        # date formats legitimately use different parts
            assert _fields(other.text[key]) == _fields(template), key

    def test_same_months_and_grades(self, other):
        assert set(other.months) == set(other.months_abbr) == set(range(1, 13))
        assert set(other.grades) == set(ES.grades)

    def test_cover_has_the_same_shape(self, other):
        assert set(other.cover) == set(ES.cover)
        assert len(other.cover["steps"]) == len(ES.cover["steps"])
        assert len(other.cover["quick"]) == len(ES.cover["quick"])
        for key in ("help_line", "page_abbr", "footer_video", "footer_feedback"):
            assert _fields(other.cover[key]) == _fields(ES.cover[key]), key


class TestCatalog:
    def test_unknown_language_is_an_error(self):
        with pytest.raises(ValueError, match="unknown language"):
            catalog("fr")

    def test_dates(self):
        d = date(2026, 8, 23)
        assert ES.short_date(d) == "Ago 23" and ES.long_date(d) == "23 ago 2026"
        assert catalog("en").short_date(d) == "Aug 23" and catalog("en").long_date(d) == "Aug 23, 2026"
        assert ES.short_date(None) == "" and ES.long_date(None) == ""
        assert ES.generated(datetime(2026, 3, 15, 10, 5)) == "Generado el 15 de marzo de 2026 a las 10:05"

    def test_grade_labels(self):
        assert ES.grade(4) == "4°" and catalog("en").grade(4) == "4th"
        assert ES.grade(None) == "" and ES.grade(99) == ""
