# planning_center_reports/cli.py
#
# Command-line entrypoint. Resolves the requested report from reports.yaml,
# applies the requested theme to config._theme, then runs the shared pipeline.
#
# main() is called from the project-root main.py so that the Docker container's
# ENTRYPOINT ("python main.py") continues to work without any changes to the
# Dockerfile or Cloud Run job definitions. The positional argument accepts either
# a report id ("escuela-b") or the PCO event name ("Escuela Dominical"), so
# existing Cloud Run job arguments keep working unchanged.

import argparse
import json
import sys

import planning_center_reports.config as config
from planning_center_reports.reports import (
    ReportConfigError,
    config_path,
    enabled_reports,
    get_report,
)
from planning_center_reports.services import run_report


def _print_reports(fmt: str) -> None:
    """Print the configured reports in the requested format and return."""
    specs = enabled_reports()
    if fmt == "ids":
        for spec in specs:
            print(spec.id)
        return
    if fmt == "json":
        print(json.dumps([spec.public_dict() for spec in specs], ensure_ascii=False, indent=2))
        return

    source = config_path()
    print(f"Config: {source if source else 'built-in defaults (no reports.yaml found)'}")
    for spec in specs:
        features = [
            f"outputs={','.join(spec.outputs)}",
            f"weeks={spec.resolved_weeks()}",
        ]
        if spec.route_source_event:
            features.append(f"routes←{spec.route_source_event}")
        if spec.helpers_event:
            features.append(f"helpers←{spec.helpers_event} ({spec.helper_min_age}+)")
        if spec.attendance_summary:
            features.append("attendance-summary")
        if spec.drive_folder_prefix:
            features.append(f"drive:{spec.drive_folder_prefix}/")
        if spec.resolved_theme():
            features.append(f"theme={spec.resolved_theme()}")
        print(f"\n  {spec.icon} {spec.id}")
        print(f"     label      {spec.label}")
        print(f"     pco_event  {spec.pco_event!r}")
        print(f"     features   {'; '.join(features)}")


def main():
    """Parse CLI arguments and run the requested roster generation pipeline."""
    parser = argparse.ArgumentParser(
        description="Generate PCO check-in rosters and upload to Google Drive.",
    )
    parser.add_argument(
        "report",
        nargs="?",
        help="Report id (e.g. 'escuela-b') or PCO event name (e.g. 'Escuela Dominical'). "
             "Run --list-reports to see what is configured.",
    )
    parser.add_argument(
        "--list-reports",
        action="store_true",
        help="Print the configured reports and exit.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "ids", "json"],
        default="text",
        help="Output format for --list-reports (default: text)",
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=None,
        help="Number of recent weeks to include (default: the report's default_weeks)",
    )
    parser.add_argument(
        "--theme",
        choices=["primavera", "verano", "otono", "invierno"],
        default=None,
        help="Optional campaign theme; overrides the report's default_theme",
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

    try:
        if args.list_reports:
            _print_reports(args.format)
            return

        if not args.report:
            parser.error("a report id or PCO event name is required (see --list-reports)")

        spec = get_report(args.report)
    except ReportConfigError as exc:
        print(f"{exc}", flush=True)
        sys.exit(1)

    if not spec.enabled:
        print(f"Report '{spec.id}' is disabled in the report configuration.", flush=True)
        sys.exit(1)

    # Precedence for weeks/theme: CLI flag → env override → reports.yaml default.
    weeks = args.weeks if args.weeks is not None else spec.resolved_weeks()
    theme = args.theme if args.theme is not None else spec.resolved_theme()

    # Apply theme globally before any PDF generation begins.
    # All PDF functions read config._theme via config.T(), so setting it here
    # is sufficient — no need to pass it through the call stack.
    config._theme = config.THEMES[theme]
    if theme:
        print(f"Theme: {config._theme['campaign']}", flush=True)

    if args.dry_run:
        print(f"[dry-run] No files will be uploaded. PDFs will be saved to {args.output_dir}",
              flush=True)

    run_report(
        spec,
        weeks=weeks,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
        location_filter=args.location,
    )

    print("\nDone.", flush=True)
