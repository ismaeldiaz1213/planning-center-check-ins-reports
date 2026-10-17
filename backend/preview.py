#!/usr/bin/env python3
# preview.py
#
# Generate sample PDFs locally for layout and theme testing.
# No Planning Center or Google Drive credentials needed — everything is drawn
# from planning_center_reports/mock_data.py.
#
# Usage:
#   python preview.py                    # all themes, every PDF type
#   python preview.py --theme primavera  # one specific theme
#   python preview.py --type roster      # Roster.pdf (bus route layout)
#   python preview.py --type escuela     # Roster.pdf with the Ruta column
#   python preview.py --type voluntarios # Voluntarios.pdf
#   python preview.py --type instrucciones  # Instrucciones.pdf (theme-independent)
#   python preview.py --report escuela-b # exactly what one configured report emits
#   python preview.py --open             # open PDFs in your viewer after generating
#
# Output folder: ./previews/

import argparse
import os
import subprocess

import planning_center_reports.config as config
from planning_center_reports.config import RUTAS_SUBTITLE
from planning_center_reports.mock_data import mock_roster, mock_volunteers
from planning_center_reports.pdf.instructions import build_instructions_pdf
from planning_center_reports.pdf.rosters import generate_roster_pdf
from planning_center_reports.pdf.volunteers import generate_volunteer_pdf
from planning_center_reports.reports import ReportConfigError, get_report

THEMES_AVAILABLE = [None, "primavera", "verano", "otono", "invierno"]
THEME_LABELS = {
    None:        "default (azul)",
    "primavera": "Campaña de Primavera",
    "verano":    "Campaña de Verano",
    "otono":     "Campaña de Otoño",
    "invierno":  "Campaña de Invierno",
}


def main():
    parser = argparse.ArgumentParser(description="Generate PDF previews with mock data.")
    parser.add_argument(
        "--theme",
        choices=["default", "primavera", "verano", "otono", "invierno"],
        default=None,
        help="Generate only this theme (default: all themes)",
    )
    parser.add_argument(
        "--type",
        choices=["roster", "escuela", "voluntarios", "instrucciones", "all"],
        default="all",
        help="Which PDF to generate (default: all)",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Preview exactly what one configured report emits (by id or PCO event name). "
             "Overrides --type. e.g. --report escuela-b",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open generated PDFs in your default viewer after generating",
    )
    args = parser.parse_args()

    out_dir = os.path.join(os.path.dirname(__file__), "previews")
    os.makedirs(out_dir, exist_ok=True)

    themes_to_run = (
        [None if args.theme == "default" else args.theme]
        if args.theme
        else THEMES_AVAILABLE
    )

    spec = None
    if args.report:
        try:
            spec = get_report(args.report)
        except ReportConfigError as exc:
            parser.error(str(exc))

    generated = []

    def emit(path: str) -> None:
        print(f"  ✓ {os.path.basename(path)}")
        generated.append(path)

    for theme_key in themes_to_run:
        # Set the active theme on the shared config module — all PDF functions
        # pick it up automatically via config.T().
        config._theme = config.THEMES[theme_key]
        slug = theme_key or "default"
        print(f"\n── {THEME_LABELS[theme_key]} ──")

        if spec:
            # Mirror the real pipeline: same subtitle and optional features as
            # the configured report, driven by mock data.
            location = spec.demo_locations[0] if spec.demo_locations else spec.label
            path = os.path.join(out_dir, f"{slug}_{spec.id}_Roster.pdf")
            generate_roster_pdf(mock_roster(location, spec.show_route), spec.pdf_subtitle, path,
                                show_route=spec.show_route, attendance_summary=spec.attendance_summary)
            emit(path)
            if spec.volunteer_report:
                path = os.path.join(out_dir, f"{slug}_{spec.id}_Voluntarios.pdf")
                emit(generate_volunteer_pdf(mock_volunteers(), spec.label, path))
            continue

        if args.type in ("roster", "all"):
            path = os.path.join(out_dir, f"{slug}_Roster.pdf")
            emit(generate_roster_pdf(mock_roster("Ruta 1 - Bus", show_route=False), RUTAS_SUBTITLE, path))

        if args.type in ("escuela", "all"):
            path = os.path.join(out_dir, f"{slug}_Escuela-Roster.pdf")
            emit(generate_roster_pdf(mock_roster("Clase Primaria"), "Escuela Dominical", path,
                                     show_route=True, attendance_summary=True))

        if args.type in ("voluntarios", "all"):
            path = os.path.join(out_dir, f"{slug}_Voluntarios.pdf")
            emit(generate_volunteer_pdf(mock_volunteers(), "Escuela Dominical", path))

    if args.type in ("instrucciones", "all") and not spec:
        print("\n── Instrucciones ──")
        emit(build_instructions_pdf(os.path.join(out_dir, "Instrucciones.pdf")))

    print(f"\nAll previews saved to: {out_dir}/")

    if args.open:
        print("Opening PDFs...")
        for path in generated:
            try:
                subprocess.Popen(["xdg-open", path])
            except OSError:
                print(f"  Could not open {path} — open it manually.")


if __name__ == "__main__":
    main()
