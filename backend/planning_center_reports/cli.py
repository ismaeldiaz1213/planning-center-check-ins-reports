# planning_center_reports/cli.py
#
# Command-line entrypoint. Resolves the requested report from reports.yaml,
# builds the run from .env and reports.yaml (legacy.py), then runs the shared pipeline.
#
# main() is called from the project-root main.py so that the Docker container's
# ENTRYPOINT ("python main.py") continues to work without any changes to the
# Dockerfile or Cloud Run job definitions. The positional argument accepts either
# a report id ("escuela-b") or the PCO event name ("Escuela Dominical"), so
# existing Cloud Run job arguments keep working unchanged. --all runs every
# enabled report in one process, sharing fetched PCO data between them.

import argparse
import json
import sys

from planning_center_reports import legacy
from planning_center_reports.legacy import (
    ReportConfigError,
    config_path,
    enabled_reports,
    get_report,
)
from planning_center_reports.services import run_all, run_report


def _print_reports(fmt: str) -> None:
    """Print the configured reports in the requested format and return."""
    specs = enabled_reports()
    if fmt == "ids":
        for spec in specs:
            print(spec.id)
        return
    if fmt == "json":
        print(json.dumps([legacy.public_dict(spec) for spec in specs], ensure_ascii=False, indent=2))
        return

    source = config_path()
    print(f"Config: {source if source else 'built-in defaults (no reports.yaml found)'}")
    for spec in specs:
        history = (f"since {spec.start_date.isoformat()}" if spec.start_date
                   else f"rolling {spec.history_weeks} weeks")
        features = [
            f"history={history}",
            f"active={legacy.resolved_weeks(spec)} weeks",
        ]
        if spec.route_source_event:
            features.append(f"routes←{spec.route_source_event}")
        if spec.volunteer_report:
            source = (f"{spec.volunteer_event} ({spec.volunteer_min_age}+)" if spec.volunteer_event
                      else "Volunteer check-ins")
            features.append(f"volunteers←{source}")
        if spec.instructions:
            features.append("instructions")
        if spec.attendance_summary:
            features.append("attendance-summary")
        if spec.drive_folder_prefix:
            features.append(f"drive:{spec.drive_folder_prefix}/")
        if legacy.resolved_theme(spec):
            features.append(f"theme={legacy.resolved_theme(spec)}")
        print(f"\n  {spec.icon} {spec.id}")
        print(f"     label      {spec.label}")
        print(f"     pco_event  {spec.pco_event!r}")
        print(f"     features   {'; '.join(features)}")


def _announce_theme(theme: str | None) -> None:
    if theme:
        print(f"Theme: {legacy.church().texts.t(f'campaign.{theme}')}", flush=True)


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
        "--all",
        action="store_true",
        help="Run every enabled report in one process (what the weekly Cloud Run job does).",
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
        help="Active window in Sundays: people seen in the last N are on the list, "
             "older ones move to 'Hace tiempo' (default: the report's default_weeks)",
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

        if args.all:
            if args.report or args.location or args.weeks:
                parser.error("--all runs every report with its own settings; "
                             "drop the report name, --location and --weeks")
            if args.dry_run:
                print(f"[dry-run] No files will be uploaded. PDFs will be saved to {args.output_dir}",
                      flush=True)
            with legacy.run_context(dry_run=args.dry_run, output_dir=args.output_dir) as ctx:
                ok = run_all(ctx, theme=args.theme)
                print(f"\n{ctx.pco.stats.summary()}", flush=True)
            print("\nDone." if ok else "\nDone with errors.", flush=True)
            sys.exit(0 if ok else 1)

        if not args.report:
            parser.error("a report id or PCO event name is required (see --list-reports or --all)")

        spec = get_report(args.report)
    except ReportConfigError as exc:
        print(f"{exc}", flush=True)
        sys.exit(1)

    if not spec.enabled:
        print(f"Report '{spec.id}' is disabled in the report configuration.", flush=True)
        sys.exit(1)

    # Precedence for weeks/theme: CLI flag → env override → reports.yaml default.
    weeks = args.weeks if args.weeks is not None else legacy.resolved_weeks(spec)
    theme = args.theme if args.theme is not None else legacy.resolved_theme(spec)

    _announce_theme(theme)

    if args.dry_run:
        print(f"[dry-run] No files will be uploaded. PDFs will be saved to {args.output_dir}",
              flush=True)

    with legacy.run_context(dry_run=args.dry_run, output_dir=args.output_dir) as ctx:
        run_report(ctx, spec, weeks=weeks, location_filter=args.location, theme=theme)
        print(f"\n{ctx.pco.stats.summary()}", flush=True)
    print("\nDone.", flush=True)
