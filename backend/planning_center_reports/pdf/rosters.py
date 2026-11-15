# planning_center_reports/pdf/rosters.py
#
# Roster.pdf — one per class or bus route. Layout, top to bottom:
#
#   header           location, report, history range
#   Lista            everyone seen in the active window, with attendance dots,
#                    date added, and a parent line under each kid
#   Maestros         people Planning Center tags as Volunteer
#   Hace tiempo      seen since the history start but not lately — call list
#   Resumen          a few numbers, attendance per Sunday, and riders per
#                    route (reports with attendance_summary)
#
# The data comes ready-made from roster_data.LocationRoster; this module only
# chooses rows, cells and colours. Drawing primitives live in layout.py, and
# every printed word comes from the church's text catalog (ctx.texts).

from __future__ import annotations

from collections import Counter

from planning_center_reports.config import ACCENT_OK, ACCENT_WARN
from planning_center_reports.i18n import Catalog
from planning_center_reports.models import (
    _fmt_birthday,
    _is_bad_address,
    _is_minor,
    _resolve_grade,
)
from planning_center_reports.pdf.context import RenderContext
from planning_center_reports.pdf.layout import (
    Cell,
    Column,
    Page,
    Row,
    draw_feedback_card,
    draw_note,
    draw_resumen,
    draw_section,
    draw_table,
)
from planning_center_reports.roster_data import LocationRoster, Member


def short_route(route: str) -> str:
    """"Ruta 1 - Bus" → "1 Bus", "Ruta 12" → "12"."""
    if not route:
        return ""
    text = route.strip()
    if text.lower().startswith("ruta "):
        text = text[5:]
    return text.replace(" - ", " ")


def _short_address(address: str) -> str:
    """Drop the state and ZIP — everyone on a roster lives in the same area."""
    parts = [p.strip() for p in (address or "").split(",") if p.strip()]
    while parts and (parts[-1].replace("-", "").isdigit() or len(parts[-1]) == 2):
        parts.pop()
    return ", ".join(parts)


def _same_place(a: str, b: str) -> bool:
    """Compare addresses ignoring punctuation and unit markers ("#803" == "803")."""
    def norm(s: str) -> str:
        s = s.lower().replace("apto", "").replace("apt", "")
        return "".join(ch for ch in s if ch.isalnum())
    return norm(a) == norm(b)


def _guardian_line(m: Member, texts: Catalog) -> list[tuple[str, str]] | None:
    g = m.guardian
    if not g:
        return None
    parts = [(texts.t("roster.guardian"), g.get("name", "")), ("", g.get("phone", ""))]
    addr = _short_address(g.get("address", ""))
    if addr and not _same_place(addr, _short_address(m.address)):
        parts.append(("", addr))
    return parts


def _grade_label(m: Member, texts: Catalog) -> str:
    """The grade to print: the church's label for Planning Center's grade number
    (or the ready-made text on mock data), replaced by an age label for toddlers."""
    grade = texts.grade(m.grade_num) if m.grade_num is not None else m.grade
    return _resolve_grade(grade, m.birthday, texts)


TABLE_WIDTH = 720      # hidden columns are named in reports.HIDEABLE


def _fit(keyed: list[tuple[str, Column]], hide) -> list[Column]:
    """Drop hidden columns; the last one left takes whatever width remains
    (with nothing hidden that is the address column, exactly as before)."""
    cols = [col for key, col in keyed if key not in hide]
    cols[-1] = Column(cols[-1].header, TABLE_WIDTH - sum(c.width for c in cols[:-1]), cols[-1].align)
    return cols


def _keep(keyed: list[tuple[str, Cell]], hide) -> list[Cell]:
    return [cell for key, cell in keyed if key not in hide]


def _main_columns(show_route: bool, texts: Catalog, hide=()) -> list[Column]:
    t = texts.t
    keyed = [
        ("", Column("", 14)),
        ("", Column(t("col.first_name"), 96)),
        ("", Column(t("col.last_name"), 100)),
        ("birthday", Column(t("col.birthday"), 62)),
        ("phone", Column(t("col.phone"), 82)),
        ("grade", Column(t("col.grade"), 42)),
    ]
    if show_route:
        keyed.append(("", Column(t("col.route"), 46)))
    keyed += [("attendance", Column(t("col.attendance"), 50)), ("added", Column(t("col.added"), 54)),
              ("address", Column(t("col.address"), 0))]
    return _fit(keyed, hide)


def _main_row(roster: LocationRoster, m: Member, show_route: bool, texts: Catalog, hide=()) -> Row:
    bday  = _fmt_birthday(m.birthday)
    grade = _grade_label(m, texts)
    keyed = [
        ("", Cell()),
        ("", Cell(m.first_name, warn=not m.first_name, style="bold")),
        ("", Cell(m.last_name, warn=not m.last_name)),
        ("birthday", Cell(bday, warn=not bday)),
        ("phone", Cell(m.phone, warn=not m.phone and not m.guardian)),
        ("grade", Cell(grade, warn=_is_minor(m.birthday) and not grade)),
    ]
    if show_route:
        keyed.append(("", Cell(short_route(m.route), style="muted")))
    keyed.append(("attendance", Cell(style="meter", meter=(m.attended, m.window))))
    if roster.is_recent(m):
        keyed.append(("added", Cell(texts.short_date(m.date_added), style="chip", color=ACCENT_OK)))
    else:
        keyed.append(("added", Cell(texts.short_date(m.date_added), style="muted")))
    keyed.append(("address", Cell(_short_address(m.address), warn=_is_bad_address(m.address))))
    return Row(cells=_keep(keyed, hide), marker=m.is_new,
               sub=None if "parents" in hide else _guardian_line(m, texts))


def _resumen(page: Page, roster: LocationRoster, show_route: bool, attendance_summary: bool) -> None:
    """Numbers at the bottom: averages, attendance per Sunday, riders per route."""
    texts = page.ctx.texts
    t = texts.t
    avg = roster.average_attendance
    stats = [
        (t("summary.average"), f"{avg:.0f}"),
        (t("summary.added", weeks=len(roster.sundays)), str(roster.added_recently)),
        (t("summary.new"), str(roster.new_this_week)),
    ]
    tables = [(
        [Column(t("col.sunday"), 70), Column(t("col.regulars"), 62, "center"),
         Column(t("col.new"), 52, "center"), Column(t("col.total"), 46, "center")],
        [Row(cells=[Cell(texts.short_date(s.day), style="bold"), Cell(str(s.regular)),
                    Cell(str(s.visitors)), Cell(str(s.total), style="bold")]) for s in roster.sundays],
    )]
    routed = Counter(short_route(m.route) for m in roster.active if m.route)
    if attendance_summary and show_route and routed:
        tables.append((
            [Column(t("col.route"), 90), Column(t("col.riders"), 90, "center")],
            [Row(cells=[Cell(t("roster.route_row", route=r), style="bold"), Cell(str(n))])
             for r, n in sorted(routed.items(), key=lambda kv: (-kv[1], kv[0]))],
        ))
    draw_resumen(page, stats, tables)


def generate_roster_pdf(roster: LocationRoster, subtitle: str, filename: str, ctx: RenderContext,
                        show_route: bool = False, attendance_summary: bool = False,
                        hide: tuple[str, ...] = ()) -> str:
    """Write Roster.pdf for one location and return `filename`.

    `hide` lists the columns and sections (see HIDEABLE) this church leaves off.
    """
    hide = frozenset(hide)
    texts = ctx.texts
    t = texts.t
    weeks = len(roster.sundays)
    since = texts.long_date(roster.history_start)
    meta = [t("roster.history", date=since, sundays=roster.history_sundays)]
    page = Page(filename, ctx, roster.location, subtitle, meta)

    # ── Lista ──
    draw_section(page, t("roster.list"), len(roster.active),
                 note=t("roster.list.note", weeks=weeks), keep_with=40)
    draw_table(page, _main_columns(show_route, texts, hide),
               [_main_row(roster, m, show_route, texts, hide) for m in roster.active],
               empty_text=t("roster.list.empty"))

    # ── Maestros y ayudantes ──
    if roster.workers and "workers" not in hide:
        draw_section(page, t("roster.workers"), len(roster.workers),
                     note=t("roster.workers.note"), keep_with=40)
        draw_table(page, [col for key, col in [
            ("", Column("", 14)), ("", Column(t("col.first_name"), 120)), ("", Column(t("col.last_name"), 130)),
            ("phone", Column(t("col.phone"), 100)), ("attendance", Column(t("col.attendance"), 70)),
            ("", Column(t("col.last_seen"), 70)),
        ] if key not in hide], [
            Row(cells=_keep([
                ("", Cell()), ("", Cell(m.first_name, style="bold")), ("", Cell(m.last_name)),
                ("phone", Cell(m.phone, warn=not m.phone)),
                ("attendance", Cell(style="meter", meter=(m.attended, m.window))),
                ("", Cell(texts.short_date(m.last_seen), style="muted")),
            ], hide)) for m in roster.workers
        ])

    # ── Hace tiempo que no viene ──
    if roster.inactive and "inactive" not in hide:
        draw_section(page, t("roster.inactive"), len(roster.inactive), accent=ACCENT_WARN,
                     note=t("roster.inactive.note", date=since, weeks=weeks), keep_with=40)
        keyed = [("", Column("", 14)), ("", Column(t("col.first_name"), 96)), ("", Column(t("col.last_name"), 100)),
                 ("phone", Column(t("col.phone"), 82))]
        if show_route:
            keyed.append(("", Column(t("col.route"), 46)))
        keyed += [("", Column(t("col.last_seen"), 58)), ("", Column(t("col.weeks"), 50, "center")),
                  ("", Column(t("col.times"), 42, "center")), ("address", Column(t("col.address"), 0))]
        cols = _fit(keyed, hide)
        rows = []
        for m in roster.inactive:
            cells = [("", Cell()), ("", Cell(m.first_name, style="bold")), ("", Cell(m.last_name)),
                     ("phone", Cell(m.phone, warn=not m.phone and not m.guardian))]
            if show_route:
                cells.append(("", Cell(short_route(m.route), style="muted")))
            cells += [
                ("", Cell(texts.short_date(m.last_seen))),
                ("", Cell(str(m.weeks_absent))),
                ("", Cell(str(m.times_total), style="muted")),
                ("address", Cell(_short_address(m.address), warn=_is_bad_address(m.address))),
            ]
            rows.append(Row(cells=_keep(cells, hide),
                            sub=None if "parents" in hide else _guardian_line(m, texts)))
        draw_table(page, cols, rows, gap_after=0)
        draw_note(page, t("roster.inactive.legend"))

    if "summary" not in hide:
        _resumen(page, roster, show_route, attendance_summary)
    draw_feedback_card(page)
    page.save()
    return filename
