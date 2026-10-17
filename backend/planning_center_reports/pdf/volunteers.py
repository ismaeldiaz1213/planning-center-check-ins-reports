# planning_center_reports/pdf/volunteers.py
#
# Voluntarios.pdf — who served over the last few Sundays and when they checked in.
#
#   table     one row per volunteer, grouped by class or route: their check-in
#             time each Sunday, how many Sundays they came, their usual time
#   Resumen   volunteers per Sunday with the first and average check-in
#
# Times are reported as they are — no "early" or "late" judgement, since
# services and meetings don't always start on the minute. Staff read the numbers.

from __future__ import annotations

from planning_center_reports.pdf.layout import (
    Cell,
    Column,
    Page,
    Row,
    draw_feedback_card,
    draw_resumen,
    draw_section,
    draw_table,
)
from planning_center_reports.roster_data import Arrival, VolunteerReport


def _time_cell(a: Arrival | None) -> Cell:
    return Cell(a.clock) if a else Cell(style="dash")


def generate_volunteer_pdf(report: VolunteerReport, subtitle: str, filename: str) -> str:
    """Write Voluntarios.pdf and return `filename`."""
    n = len(report.periods)
    page = Page(filename, report.title, subtitle, [f"Últimos {n} domingos"], legend=())

    cols = [Column("", 8), Column("Nombre", 210)]
    cols += [Column(p.label, 74, "center") for p in report.periods]
    cols += [Column("Asistencia", 70, "center"), Column("Hora usual", 70, "center")]

    rows: list[Row] = []
    group = None
    for r in report.rows:
        if r.group != group:
            group = r.group
            rows.append(Row(group=group))
        rows.append(Row(cells=[
            Cell(),
            Cell(r.name, style="bold"),
            *[_time_cell(a) for a in r.arrivals],
            Cell(style="meter", meter=(len(r.present), n)),
            Cell(r.average_clock, style="muted"),
        ]))

    draw_section(page, "Voluntarios", len(report.rows),
                 note="Hora de check-in cada domingo · — = no hizo check-in", keep_with=40)
    draw_table(page, cols, rows, empty_text=(
        "Nadie fue registrado como voluntario en estos domingos. Para que aparezcan aquí, "
        "márcalos como \"Volunteer\" al hacer check-in."
    ))

    if report.rows:
        rate = report.attendance_rate
        draw_resumen(page, [
            ("Voluntarios", str(len(report.rows))),
            ("Promedio por domingo", f"{report.average_present:.0f}"),
            ("Asistencia", f"{rate:.0%}" if rate is not None else "—"),
        ], [(
            [Column("Domingo", 70), Column("Presentes", 64, "center"),
             Column("Primer check-in", 90, "center"), Column("Check-in promedio", 100, "center")],
            [Row(cells=[Cell(s.label, style="bold"), Cell(str(s.present)),
                        Cell(s.first or "—"), Cell(s.average or "—")]) for s in report.sundays],
        )])

    draw_feedback_card(page)
    page.save()
    return filename
