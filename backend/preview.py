#!/usr/bin/env python3
# preview.py
#
# Generate sample PDFs locally for layout and theme testing.
# No Planning Center or Google Drive credentials needed — the package imports
# only what it needs, so pco_client and drive_client are never loaded here.
#
# Usage:
#   python preview.py                    # all themes, both PDF types
#   python preview.py --theme primavera  # one specific theme
#   python preview.py --type roster      # only the simple roster PDF
#   python preview.py --type direcciones # only the address-grouped PDF
#   python preview.py --open             # open PDFs in your viewer after generating
#
# Output folder: ./previews/

import argparse
import os
import subprocess

import planning_center_reports.config as config
from planning_center_reports.config import RUTAS_SUBTITLE
from planning_center_reports.mock_data import MOCK_ATTENDEES, MOCK_SUNDAY_DATA
from planning_center_reports.pdf.rosters import generate_address_pdf, generate_simple_roster_pdf

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
        choices=["roster", "escuela", "direcciones", "both", "all"],
        default="all",
        help="Which PDF type to generate (default: all). "
             "'roster'=Rutas alphabetical, 'escuela'=Escuela Dominical with route column, "
             "'direcciones'=address-grouped, 'both'=roster+direcciones, 'all'=all three",
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

    generated = []

    for theme_key in themes_to_run:
        # Set the active theme on the shared config module — all PDF functions
        # pick it up automatically via config.T().
        config._theme = config.THEMES[theme_key]
        slug  = theme_key or "default"
        label = THEME_LABELS[theme_key]
        print(f"\n── {label} ──")

        if args.type in ("roster", "both", "all"):
            path = os.path.join(out_dir, f"{slug}_Roster.pdf")
            generate_simple_roster_pdf("Ruta 1 - Bus", RUTAS_SUBTITLE, MOCK_ATTENDEES, path)
            print(f"  ✓ {os.path.basename(path)}")
            generated.append(path)

        if args.type in ("escuela", "all"):
            # Escuela Dominical: helpers stay on roster (route already blank on their records)
            path = os.path.join(out_dir, f"{slug}_Escuela-Roster.pdf")
            generate_simple_roster_pdf(
                "Clase Primaria", "Escuela Dominical", MOCK_ATTENDEES, path,
                show_route=True, sunday_data=MOCK_SUNDAY_DATA,
            )
            print(f"  ✓ {os.path.basename(path)}")
            generated.append(path)

        if args.type in ("direcciones", "both", "all"):
            path = os.path.join(out_dir, f"{slug}_Direcciones-Roster.pdf")
            generate_address_pdf("Ruta 1 - Bus", MOCK_ATTENDEES, path)
            print(f"  ✓ {os.path.basename(path)}")
            generated.append(path)

    print(f"\nAll previews saved to: {out_dir}/")

    if args.open:
        print("Opening PDFs...")
        for path in generated:
            try:
                subprocess.Popen(["xdg-open", path])
            except Exception:
                print(f"  Could not open {path} — open it manually.")


if __name__ == "__main__":
    main()
