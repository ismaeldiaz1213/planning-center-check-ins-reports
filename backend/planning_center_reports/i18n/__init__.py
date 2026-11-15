# planning_center_reports/i18n/__init__.py
#
# Every word a PDF prints, and every file or folder name a run creates, comes
# from a Catalog chosen by the church's language. The engine never hardcodes
# display text: code asks for texts.t("roster.section.list") and gets "Lista"
# for a Spanish church and "Roster" for an English one.
#
# Each language is one module (es.py, en.py) with the same names and the same
# keys; tests/test_i18n.py fails if they drift apart.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from types import ModuleType

from planning_center_reports.i18n import en, es


@dataclass(frozen=True)
class Catalog:
    code:        str
    text:        Mapping[str, str]
    months:      Mapping[int, str]
    months_abbr: Mapping[int, str]
    grades:      Mapping[int, str]      # Planning Center grade number → label
    cover:       Mapping[str, object]   # the instructions cover page

    def t(self, key: str, **values) -> str:
        """The text for `key`, with {placeholders} filled in."""
        template = self.text[key]
        return template.format(**values) if values else template

    def short_date(self, d: date | None) -> str:
        """Column-header date, e.g. "Oct 11"."""
        return self.t("date.short", mon=self.months_abbr[d.month], day=d.day) if d else ""

    def long_date(self, d: date | None) -> str:
        if not d:
            return ""
        mon = self.months_abbr[d.month]
        return self.t("date.long", mon=mon, mon_lower=mon.lower(), day=d.day, year=d.year)

    def generated(self, dt: datetime) -> str:
        """The "generated on …" line in the page header."""
        return self.t("page.generated", day=dt.day, month=self.months[dt.month], year=dt.year,
                      time=dt.strftime("%H:%M"))

    def grade(self, number: int | None) -> str:
        return self.grades.get(number, "") if number is not None else ""


def _from_module(module: ModuleType) -> Catalog:
    return Catalog(code=module.CODE, text=module.TEXT, months=module.MONTHS,
                   months_abbr=module.MONTHS_ABBR, grades=module.GRADES, cover=module.COVER)


CATALOGS: dict[str, Catalog] = {m.CODE: _from_module(m) for m in (es, en)}
LANGUAGES = tuple(CATALOGS)


def catalog(language: str) -> Catalog:
    try:
        return CATALOGS[language]
    except KeyError:
        raise ValueError(f"unknown language {language!r}; expected one of {sorted(CATALOGS)}") from None
