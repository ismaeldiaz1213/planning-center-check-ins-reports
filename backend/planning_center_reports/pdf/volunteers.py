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

from planning_center_reports.pdf.context import RenderContext
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


def generate_volunteer_pdf(report: VolunteerReport, subtitle: str, filename: str,
                           ctx: RenderContext) -> str:
    """Write Voluntarios.pdf and return `filename`."""
    texts = ctx.texts
    t = texts.t
    n = len(report.periods)
    page = Page(filename, ctx, report.title, subtitle, [t("volunteers.meta", sundays=n)], legend=())

    cols = [Column("", 8), Column(t("col.name"), 210)]
    cols += [Column(texts.short_date(p.local_date), 74, "center") for p in report.periods]
    cols += [Column(t("col.attendance"), 70, "center"), Column(t("col.usual_time"), 70, "center")]

    rows: list[Row] = []
    group: object = object()          # never equal to a real group, including None
    for r in report.rows:
        if r.group != group:
            group = r.group
            rows.append(Row(group=r.group or t("volunteers.unassigned")))
        rows.append(Row(cells=[
            Cell(),
            Cell(r.name, style="bold"),
            *[_time_cell(a) for a in r.arrivals],
            Cell(style="meter", meter=(len(r.present), n)),
            Cell(r.average_clock, style="muted"),
        ]))

    draw_section(page, t("volunteers.section"), len(report.rows),
                 note=t("volunteers.note"), keep_with=40)
    draw_table(page, cols, rows, empty_text=t("volunteers.empty"))

    if report.rows:
        rate = report.attendance_rate
        draw_resumen(page, [
            (t("summary.volunteers"), str(len(report.rows))),
            (t("summary.average"), f"{report.average_present:.0f}"),
            (t("summary.attendance"), f"{rate:.0%}" if rate is not None else "—"),
        ], [(
            [Column(t("col.sunday"), 70), Column(t("col.present"), 64, "center"),
             Column(t("col.first_checkin"), 90, "center"), Column(t("col.average_checkin"), 100, "center")],
            [Row(cells=[Cell(texts.short_date(s.day), style="bold"), Cell(str(s.present)),
                        Cell(s.first or "—"), Cell(s.average or "—")]) for s in report.sundays],
        )])

    draw_feedback_card(page)
    page.save()
    return filename
