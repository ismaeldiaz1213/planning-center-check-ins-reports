#!/usr/bin/env python3
"""
demo_run.py — called by api.py when DEMO_MODE=true instead of main.py.

Simulates a realistic roster job for any configured report using mock data.
Generates real PDFs and saves them to backend/previews/; skips Google Drive.

Which log lines appear, whether the Ruta column is drawn, and whether attendance
summary tables are included all come from the report's spec in reports.yaml —
so a newly configured report gets a working demo with no changes here.

Usage (for manual testing):
    python demo_run.py rutas
    python demo_run.py escuela-b primavera
"""
import sys
import time
from pathlib import Path

import planning_center_reports.config as _cfg
from planning_center_reports.mock_data import MOCK_ATTENDEES, MOCK_SUNDAY_DATA
from planning_center_reports.pdf.rosters import generate_address_pdf, generate_simple_roster_pdf
from planning_center_reports.reports import OUTPUT_FILENAMES, ReportConfigError, get_report


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

    if spec.helpers_event:
        _log(f"Fetching helpers ({spec.helpers_event})...")
        time.sleep(0.5)
        _log("  Found 1 helper")
        time.sleep(0.3)

    if spec.route_source_event:
        _log(f"  Building route mappings from {spec.route_source_event} check-ins...")
        time.sleep(0.4)
        _log(f"  Mapped {len(MOCK_ATTENDEES)} people to routes.")
        time.sleep(0.2)

    for loc in locations:
        # For the bus-route demo each location shows only its own riders;
        # class-style reports show the whole mock roster.
        attendees = [a for a in MOCK_ATTENDEES if a.get("route") == loc]
        if not attendees:
            attendees = MOCK_ATTENDEES

        _log(f"Processing {loc} ({len(attendees)} attendees)...")
        time.sleep(0.3)
        slug = loc.replace(" ", "_").replace("/", "-").replace('"', "")

        for kind in spec.outputs:
            filename = OUTPUT_FILENAMES[kind]
            path = str(out_dir / f"demo_{slug}_{filename}")
            if kind == "address":
                generate_address_pdf(loc, attendees, path)
            else:
                generate_simple_roster_pdf(
                    loc, spec.pdf_subtitle, attendees, path,
                    show_route=spec.show_route,
                    sunday_data=MOCK_SUNDAY_DATA if spec.attendance_summary else None,
                )
            _log(f"  ✓ {filename} saved")

        _log("  [DEMO MODE] Skipping Google Drive upload")
        time.sleep(0.2)

    elapsed = time.time() - t_start
    _log(f"\nDone in {elapsed:.1f}s")
    _log("[DEMO MODE] No data was sent to Google Drive.")


if __name__ == "__main__":
    main()
