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
# chooses rows, cells and colours. Drawing primitives live in layout.py.

from __future__ import annotations

from collections import Counter

from planning_center_reports.config import ACCENT_OK, ACCENT_WARN, MESES_ABREV
from planning_center_reports.models import (
    _fmt_birthday,
    _is_bad_address,
    _is_minor,
    _resolve_grade,
)
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
from planning_center_reports.roster_data import LocationRoster, Member, short_date


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


def _long_date(d) -> str:
    return f"{d.day} {MESES_ABREV[d.month].lower()} {d.year}" if d else ""


def _same_place(a: str, b: str) -> bool:
    """Compare addresses ignoring punctuation and unit markers ("#803" == "803")."""
    def norm(s: str) -> str:
        s = s.lower().replace("apto", "").replace("apt", "")
        return "".join(ch for ch in s if ch.isalnum())
    return norm(a) == norm(b)


def _guardian_line(m: Member) -> list[tuple[str, str]] | None:
    g = m.guardian
    if not g:
        return None
    parts = [("Padre/Tutor:", g.get("name", "")), ("", g.get("phone", ""))]
    addr = _short_address(g.get("address", ""))
    if addr and not _same_place(addr, _short_address(m.address)):
        parts.append(("", addr))
    return parts


def _main_columns(show_route: bool) -> list[Column]:
    cols = [
        Column("", 14),
        Column("Nombre", 96),
        Column("Apellido", 100),
        Column("Cumpleaños", 62),
        Column("Teléfono", 82),
        Column("Grado", 42),
    ]
    if show_route:
        cols.append(Column("Ruta", 46))
    cols += [Column("Asistencia", 50), Column("Agregado", 54)]
    cols.append(Column("Dirección", 720 - sum(c.width for c in cols)))
    return cols


def _main_row(roster: LocationRoster, m: Member, show_route: bool) -> Row:
    bday  = _fmt_birthday(m.birthday)
    grade = _resolve_grade(m.grade, m.birthday)
    cells = [
        Cell(),
        Cell(m.first_name, warn=not m.first_name, style="bold"),
        Cell(m.last_name, warn=not m.last_name),
        Cell(bday, warn=not bday),
        Cell(m.phone, warn=not m.phone and not m.guardian),
        Cell(grade, warn=_is_minor(m.birthday) and not grade),
    ]
    if show_route:
        cells.append(Cell(short_route(m.route), style="muted"))
    cells.append(Cell(style="meter", meter=(m.attended, m.window)))
    if roster.is_recent(m):
        cells.append(Cell(short_date(m.date_added), style="chip", color=ACCENT_OK))
    else:
        cells.append(Cell(short_date(m.date_added), style="muted"))
    cells.append(Cell(_short_address(m.address), warn=_is_bad_address(m.address)))
    return Row(cells=cells, marker=m.is_new, sub=_guardian_line(m))


def _resumen(page: Page, roster: LocationRoster, show_route: bool, attendance_summary: bool) -> None:
    """Numbers at the bottom: averages, attendance per Sunday, riders per route."""
    avg = roster.average_attendance
    stats = [
        ("Promedio por domingo", f"{avg:.0f}"),
        (f"Agregados en {len(roster.sundays)} semanas", str(roster.added_recently)),
        ("Nuevos este domingo", str(roster.new_this_week)),
    ]
    tables = [(
        [Column("Domingo", 70), Column("Regulares", 62, "center"),
         Column("Nuevos", 52, "center"), Column("Total", 46, "center")],
        [Row(cells=[Cell(s.label, style="bold"), Cell(str(s.regular)), Cell(str(s.visitors)),
                    Cell(str(s.total), style="bold")]) for s in roster.sundays],
    )]
    routed = Counter(short_route(m.route) for m in roster.active if m.route)
    if attendance_summary and show_route and routed:
        tables.append((
            [Column("Ruta", 90), Column("Niños en la lista", 90, "center")],
            [Row(cells=[Cell(f"Ruta {r}", style="bold"), Cell(str(n))])
             for r, n in sorted(routed.items(), key=lambda kv: (-kv[1], kv[0]))],
        ))
    draw_resumen(page, stats, tables)


def generate_roster_pdf(roster: LocationRoster, subtitle: str, filename: str,
                        show_route: bool = False, attendance_summary: bool = False) -> str:
    """Write Roster.pdf for one location and return `filename`."""
    weeks = len(roster.sundays)
    meta = [f"Historial desde {_long_date(roster.history_start)} · {roster.history_sundays} domingos"]
    page = Page(filename, roster.location, subtitle, meta)

    # ── Lista ──
    draw_section(page, "Lista", len(roster.active),
                 note=f"Vinieron en los últimos {weeks} domingos · un punto por domingo · "
                      "Agregado = primer domingo en esta clase",
                 keep_with=40)
    draw_table(page, _main_columns(show_route),
               [_main_row(roster, m, show_route) for m in roster.active],
               empty_text="Nadie ha venido en las últimas semanas.")

    # ── Maestros y ayudantes ──
    if roster.workers:
        draw_section(page, "Maestros y ayudantes", len(roster.workers),
                     note="Registrados como voluntarios en Planning Center", keep_with=40)
        draw_table(page, [
            Column("", 14), Column("Nombre", 120), Column("Apellido", 130),
            Column("Teléfono", 100), Column("Asistencia", 70), Column("Última vez", 70),
        ], [
            Row(cells=[
                Cell(), Cell(m.first_name, style="bold"), Cell(m.last_name),
                Cell(m.phone, warn=not m.phone), Cell(style="meter", meter=(m.attended, m.window)),
                Cell(short_date(m.last_seen), style="muted"),
            ]) for m in roster.workers
        ])

    # ── Hace tiempo que no viene ──
    if roster.inactive:
        draw_section(page, "Hace tiempo que no viene", len(roster.inactive), accent=ACCENT_WARN,
                     note=f"Vinieron desde {_long_date(roster.history_start)} pero no en los últimos "
                          f"{weeks} domingos · buena lista para llamar",
                     keep_with=40)
        cols = [Column("", 14), Column("Nombre", 96), Column("Apellido", 100), Column("Teléfono", 82)]
        if show_route:
            cols.append(Column("Ruta", 46))
        cols += [Column("Última vez", 58), Column("Semanas", 50, "center"), Column("Veces", 42, "center")]
        cols.append(Column("Dirección", 720 - sum(c.width for c in cols)))
        rows = []
        for m in roster.inactive:
            cells = [Cell(), Cell(m.first_name, style="bold"), Cell(m.last_name),
                     Cell(m.phone, warn=not m.phone and not m.guardian)]
            if show_route:
                cells.append(Cell(short_route(m.route), style="muted"))
            cells += [
                Cell(short_date(m.last_seen)),
                Cell(str(m.weeks_absent)),
                Cell(str(m.times_total), style="muted"),
                Cell(_short_address(m.address), warn=_is_bad_address(m.address)),
            ]
            rows.append(Row(cells=cells, sub=_guardian_line(m)))
        draw_table(page, cols, rows, gap_after=0)
        draw_note(page, "Semanas = domingos desde la última vez · Veces = domingos que vino desde el inicio")

    _resumen(page, roster, show_route, attendance_summary)
    draw_feedback_card(page)
    page.save()
    return filename
