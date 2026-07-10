# planning_center_reports/cli.py
#
# Command-line entrypoint. Parses arguments, applies the requested theme to
# config._theme, then delegates to the appropriate service function.
#
# main() is called from the project-root main.py so that the Docker container's
# ENTRYPOINT ("python main.py") continues to work without any changes to the
# Dockerfile or Cloud Run job definitions.

import sys
import argparse

import planning_center_reports.config as config
from planning_center_reports.services import run_rutas, run_escuela_dominical


def main():
    """Parse CLI arguments and run the requested roster generation pipeline."""
    parser = argparse.ArgumentParser(
        description="Generate PCO check-in rosters and upload to Google Drive."
    )
    parser.add_argument(
        "event_name",
        help="PCO event name: 'Rutas' or 'Escuela Dominical'",
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=5,
        help="Number of recent weeks to include (default: 5)",
    )
    parser.add_argument(
        "--theme",
        choices=["primavera", "verano", "otono", "invierno"],
        default=None,
        help="Optional campaign theme: primavera, verano, otono, invierno",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch real PCO data and generate PDFs but skip Google Drive upload. "
             "Saves PDFs to --output-dir instead.",
    )
    parser.add_argument(
        "--output-dir",
        default="./out",
        help="Directory to save PDFs when --dry-run is set (default: ./out)",
    )
    parser.add_argument(
        "--location",
        default=None,
        help="Only process locations whose name contains this string (case-insensitive). "
             "e.g. --location 'Ruta 1' or --location 'Nursery'",
    )
    args = parser.parse_args()

    # Apply theme globally before any PDF generation begins.
    # All PDF functions read config._theme via config.T(), so setting it here
    # is sufficient — no need to pass it through the call stack.
    config._theme = config.THEMES[args.theme]
    if args.theme:
        print(f"Theme: {config._theme['campaign']}", flush=True)

    if args.dry_run:
        print(f"[dry-run] No files will be uploaded. PDFs will be saved to {args.output_dir}", flush=True)

    if args.event_name == "Rutas":
        run_rutas(weeks=args.weeks, dry_run=args.dry_run, output_dir=args.output_dir, location_filter=args.location)
    elif args.event_name == "Escuela Dominical":
        run_escuela_dominical(weeks=args.weeks, dry_run=args.dry_run, output_dir=args.output_dir, location_filter=args.location)
    else:
        print(
            f"Unknown event '{args.event_name}'. Supported: 'Rutas', 'Escuela Dominical'",
            flush=True,
        )
        sys.exit(1)

    print("\nDone.", flush=True)
