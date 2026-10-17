#!/usr/bin/env python3
"""
demo_run.py — called by api.py when DEMO_MODE=true instead of main.py.

Simulates a realistic roster job for any configured report using mock data.
Generates real PDFs and saves them to backend/previews/; skips Google Drive.

Which log lines appear, whether the Ruta column is drawn, and whether the
volunteer report is generated all come from the report's spec in reports.yaml —
so a newly configured report gets a working demo with no changes here.

Usage (for manual testing):
    python demo_run.py rutas
    python demo_run.py escuela-b primavera
"""
import sys
import time
from pathlib import Path

import planning_center_reports.config as _cfg
from planning_center_reports.mock_data import MOCK_ATTENDEES, mock_roster, mock_volunteers
from planning_center_reports.pdf.rosters import generate_roster_pdf
from planning_center_reports.pdf.volunteers import generate_volunteer_pdf
from planning_center_reports.reports import (
    OUTPUT_FILENAMES,
    VOLUNTEERS_FILENAME,
    ReportConfigError,
    get_report,
)


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    report_key = sys.argv[1] if len(sys.argv) > 1 else "rutas"
    theme_arg  = sys.argv[2] if len(sys.argv) > 2 else ""

    try:
        spec = get_report(report_key)
    except ReportConfigError as exc:
        _log(f"[DEMO MODE] {exc}")
        sys.exit(1)

    theme_key   = theme_arg if theme_arg in _cfg.THEMES else None
    _cfg._theme = _cfg.THEMES[theme_key]

    out_dir = Path(__file__).parent / "previews"
    out_dir.mkdir(exist_ok=True)

    t_start = time.time()

    _log(f"[DEMO MODE] Starting {spec.label} job...")
    time.sleep(0.4)
    _log("Connecting to Planning Center API...")
    time.sleep(0.6)
    _log(f"  Looking up event {spec.pco_event!r}...")
    time.sleep(0.5)
    _log("  Found 2 event periods")
    time.sleep(0.3)
    _log("Fetching check-ins for period demo-period-1...")
    time.sleep(0.4)
    _log("  Period demo-period-1 — page 1: 9 check-ins")
    time.sleep(0.3)
    _log("Fetching check-ins for period demo-period-2...")
    time.sleep(0.4)
    _log("  Period demo-period-2 — page 1: 5 check-ins")
    time.sleep(0.2)
    _log("  Total check-ins: 14")
    time.sleep(0.3)

    locations = list(spec.demo_locations) or [f"{spec.label} — Demo"]
    _log(f"Locations to process: {locations}")
    time.sleep(0.3)

    if spec.route_source_event:
        _log(f"  Building route mappings from {spec.route_source_event} check-ins...")
        time.sleep(0.4)
        _log(f"  Mapped {len(MOCK_ATTENDEES)} people to routes.")
        time.sleep(0.2)

    for loc in locations:
        roster = mock_roster(loc, spec.show_route)
        _log(f"Generating {loc} ({len(roster.active)} on the list, "
             f"{roster.new_this_week} new this week, {len(roster.inactive)} hace tiempo)...")
        time.sleep(0.3)
        slug = loc.replace(" ", "_").replace("/", "-").replace('"', "")
        filename = OUTPUT_FILENAMES["simple"]
        generate_roster_pdf(roster, spec.pdf_subtitle, str(out_dir / f"demo_{slug}_{filename}"),
                            show_route=spec.show_route, attendance_summary=spec.attendance_summary)
        _log(f"  ✓ {filename} saved")
        _log("  [DEMO MODE] Skipping Google Drive upload")
        time.sleep(0.2)

    if spec.volunteer_report:
        _log("Building volunteer arrival report...")
        generate_volunteer_pdf(mock_volunteers(), spec.label,
                               str(out_dir / f"demo_{spec.id}_{VOLUNTEERS_FILENAME}"))
        _log(f"  ✓ {VOLUNTEERS_FILENAME} saved")

    elapsed = time.time() - t_start
    _log(f"\nDone in {elapsed:.1f}s")
    _log("[DEMO MODE] No data was sent to Google Drive.")


if __name__ == "__main__":
    main()
