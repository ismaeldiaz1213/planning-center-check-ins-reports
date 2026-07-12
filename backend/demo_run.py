#!/usr/bin/env python3
"""
demo_run.py — called by api.py when DEMO_MODE=true instead of main.py.

Simulates a realistic Rutas/Escuela Dominical job using mock data.
Generates real PDFs and saves them to backend/previews/; skips Google Drive.

Usage (for manual testing):
    python demo_run.py Rutas
    python demo_run.py "Escuela Dominical" primavera
"""
import sys
import time
from pathlib import Path

import planning_center_reports.config as _cfg
from planning_center_reports.config import RUTAS_SUBTITLE
from planning_center_reports.mock_data import MOCK_ATTENDEES, MOCK_SUNDAY_DATA
from planning_center_reports.pdf.rosters import generate_address_pdf, generate_simple_roster_pdf


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    job_type  = sys.argv[1] if len(sys.argv) > 1 else "Rutas"
    theme_arg = sys.argv[2] if len(sys.argv) > 2 else ""
    is_escuela = "escuela" in job_type.lower()

    theme_key   = theme_arg if theme_arg in _cfg.THEMES else None
    _cfg._theme = _cfg.THEMES[theme_key]

    out_dir = Path(__file__).parent / "previews"
    out_dir.mkdir(exist_ok=True)

    t_start = time.time()

    _log(f"[DEMO MODE] Starting {job_type} job...")
    time.sleep(0.4)
    _log("Connecting to Planning Center API...")
    time.sleep(0.6)
    _log("  Fetching event periods...")
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

    if not is_escuela:
        locations = ["Ruta 1 - Bus", "Ruta 2 - Van", "Ruta 3 - Carro"]
        _log(f"Locations to process: {locations}")
        time.sleep(0.3)
        _log("Fetching helpers (Junta de Rutas)...")
        time.sleep(0.5)
        _log("  Found 1 helper")
        time.sleep(0.3)

        for loc in locations:
            attendees = [a for a in MOCK_ATTENDEES if a.get("route") == loc]
            _log(f"Processing {loc} ({len(attendees)} attendees)...")
            time.sleep(0.3)
            slug        = loc.replace(" ", "_").replace("/", "-")
            roster_path = str(out_dir / f"demo_{slug}_Roster.pdf")
            addr_path   = str(out_dir / f"demo_{slug}_Direcciones-Roster.pdf")
            generate_simple_roster_pdf(loc, RUTAS_SUBTITLE, attendees, roster_path)
            generate_address_pdf(loc, attendees, addr_path)
            _log("  [DEMO MODE] Skipping Google Drive upload")
            _log("  ✓ Roster.pdf saved")
            _log("  ✓ Direcciones-Roster.pdf saved")
            time.sleep(0.2)
    else:
        classes = ["Clase Primaria", "Clase Secundaria"]
        _log(f"Locations to process: {classes}")
        time.sleep(0.3)

        for class_name in classes:
            _log(f"Processing {class_name} ({len(MOCK_ATTENDEES)} attendees)...")
            time.sleep(0.4)
            slug = class_name.replace(" ", "_")
            path = str(out_dir / f"demo_{slug}_Escuela-Roster.pdf")
            generate_simple_roster_pdf(
                class_name, "Escuela Dominical", MOCK_ATTENDEES, path,
                show_route=True, sunday_data=MOCK_SUNDAY_DATA,
            )
            _log("  [DEMO MODE] Skipping Google Drive upload")
            _log("  ✓ Escuela-Roster.pdf saved")
            time.sleep(0.2)

    elapsed = time.time() - t_start
    _log(f"\nDone in {elapsed:.1f}s")
    _log("[DEMO MODE] No data was sent to Google Drive.")


if __name__ == "__main__":
    main()
