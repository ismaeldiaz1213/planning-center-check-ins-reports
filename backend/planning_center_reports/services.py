# planning_center_reports/services.py
#
# Orchestration: fetch from PCO, shape with roster_data, draw with pdf/, then
# upload to Google Drive (or save locally on --dry-run).
#
# Public entry points:
#   run_report(spec)  — one configured report
#   run_all()         — every enabled report in one process
#
# A RunContext caches PCO data for the length of a run. run_all() shares one
# context, so the Rutas event (route column for both Sunday schools), the Junta
# meeting and parent lookups are each fetched once however many reports use
# them — and one sequential process never hits PCO from several jobs at once.

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import planning_center_reports.config as config
from planning_center_reports.config import CHURCH_TIMEZONE, GOOGLE_DRIVE_PARENT_FOLDER_ID
from planning_center_reports.drive_client import (
    get_drive_service,
    get_or_create_folder,
    upload_and_replace,
    upload_if_changed,
)
from planning_center_reports.pco_client import (
    get_checkins_for_event_periods,
    get_event_id,
    get_event_periods_since,
    get_guardians,
)
from planning_center_reports.pdf.instructions import build_instructions_pdf, instructions_fingerprint
from planning_center_reports.pdf.rosters import generate_roster_pdf
from planning_center_reports.pdf.volunteers import generate_volunteer_pdf
from planning_center_reports.reports import (
    INSTRUCTIONS_FILENAME,
    OUTPUT_FILENAMES,
    VOLUNTEERS_FILENAME,
    VOLUNTEERS_FOLDER,
    ReportSpec,
    enabled_reports,
)
from planning_center_reports.roster_data import (
    Period,
    attach_guardians,
    build_rosters,
    build_volunteer_report,
    child_ids,
    latest_location_by_person,
    periods_with_checkins,
)


class RunContext:
    """Per-run cache of everything fetched from PCO, plus shared run state."""

    def __init__(self, dry_run: bool = False, output_dir: str = "./out"):
        self.tz          = ZoneInfo(CHURCH_TIMEZONE)
        self.dry_run     = dry_run
        self.output_dir  = output_dir
        self.workdir     = tempfile.mkdtemp(prefix="rosters-")
        self._event_ids: dict[str, str] = {}
        self._periods:   dict[tuple[str, date, int], list[Period]] = {}
        self._checkins:  dict[tuple[str, str], tuple[list, list]] = {}
        self._guardians: dict[str, dict] = {}
        self._drive = None
        self._instructions: str | None = None

    @property
    def today(self) -> date:
        return datetime.now(self.tz).date()

    def event_id(self, name: str) -> str:
        if name not in self._event_ids:
            self._event_ids[name] = get_event_id(name)
        return self._event_ids[name]

    def periods(self, event_id: str, since: date, cap: int) -> list[Period]:
        key = (event_id, since, cap)
        if key not in self._periods:
            raw = get_event_periods_since(event_id, since, tz=self.tz, max_periods=cap)
            self._periods[key] = [Period(p["id"], p["starts_at"], self.tz) for p in raw]
        return self._periods[key]

    def checkins(self, event_id: str, periods: list[Period]) -> tuple[list, list]:
        """Check-ins for `periods`, fetching only periods not already cached."""
        for p in periods:
            if (event_id, p.id) not in self._checkins:
                # One period per call keeps each period's sideloads with it, so
                # any later subset of Sundays has the people it needs. It costs
                # no extra requests — PCO pages per period either way.
                self._checkins[(event_id, p.id)] = get_checkins_for_event_periods(event_id, [p.id])
        all_checkins: list = []
        all_included: list = []
        for p in periods:
            c, inc = self._checkins[(event_id, p.id)]
            all_checkins.extend(c)
            all_included.extend(inc)
        return all_checkins, all_included

    def guardians(self, ids: list[str]) -> dict[str, dict]:
        missing = [i for i in dict.fromkeys(ids) if i not in self._guardians]
        if missing:
            found = get_guardians(missing)
            for i in missing:
                self._guardians[i] = found.get(i, {})
        return {i: self._guardians[i] for i in ids if self._guardians.get(i)}

    @property
    def drive(self):
        if self._drive is None:
            print("\nConnecting to Google Drive...", flush=True)
            self._drive = get_drive_service()
        return self._drive

    def instructions_pdf(self) -> str:
        if self._instructions is None:
            self._instructions = build_instructions_pdf(
                os.path.join(self.workdir, INSTRUCTIONS_FILENAME)
            )
        return self._instructions

    def close(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate_location_filter(location_filter: str | None, included: list) -> None:
    """Exit early if location_filter matches nothing in the sideloaded location data."""
    if not location_filter:
        return
    location_names = {
        item["attributes"]["name"]
        for item in included if item["type"] == "Location"
    }
    matches = [n for n in location_names if location_filter.lower() in n.lower()]
    if not matches:
        print(f"\nNo location matching '{location_filter}'.", flush=True)
        print(f"Available: {sorted(location_names)}", flush=True)
        sys.exit(1)
    print(f"Filter '{location_filter}' matches: {sorted(matches)}", flush=True)


def _slug(name: str) -> str:
    """Filesystem-safe form of a location or folder name."""
    return name.replace("/", "-").replace(" ", "_").replace('"', "")


def _deliver(ctx: RunContext, path: str, folders: list[str], filename: str,
             fingerprint: str | None = None) -> None:
    """Upload `path` into the nested Drive `folders` (under the parent folder),
    or copy it under output_dir on a dry run."""
    if ctx.dry_run:
        dest_dir = os.path.join(ctx.output_dir, *[_slug(f) for f in folders])
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, filename)
        shutil.copy(path, dest)
        print(f"  [dry-run] Saved → {dest}", flush=True)
        return
    folder_id = GOOGLE_DRIVE_PARENT_FOLDER_ID
    for name in folders:
        folder_id = get_or_create_folder(ctx.drive, folder_id, name)
    if fingerprint:
        if upload_if_changed(ctx.drive, folder_id, path, filename, fingerprint):
            print(f"  ✓ Uploaded {filename}", flush=True)
    else:
        upload_and_replace(ctx.drive, folder_id, path, filename)
        print(f"  ✓ Uploaded {filename}", flush=True)


def _nothing_to_generate(spec: ReportSpec, reason: str) -> None:
    """Report that a run produced no PDFs, without treating it as a failure.

    A report is often configured before its Check-Ins event exists or before
    anyone has checked into it — that is an expected state, not an error.
    """
    print(f"\n  {reason}", flush=True)
    print(f"  Nothing to generate for report '{spec.id}' — this is not an error.", flush=True)
    print("  Rosters will be produced automatically once check-ins start "
          "arriving for this event.", flush=True)


def _route_map(ctx: RunContext, spec: ReportSpec) -> dict[str, str]:
    """person_id → bus route most recently ridden, from spec.route_source_event."""
    print(f"  Building route mappings from {spec.route_source_event} check-ins...", flush=True)
    try:
        rid     = ctx.event_id(spec.route_source_event)
        periods = ctx.periods(rid, spec.history_start(ctx.today), spec.max_history_weeks)
        checkins, included = ctx.checkins(rid, periods)
        mapping = latest_location_by_person(checkins, included, periods)
        print(f"  Mapped {len(mapping)} people to routes.", flush=True)
        return mapping
    except Exception as e:
        print(f"  ⚠ Could not build route mapping: {e}", flush=True)
        return {}


def _volunteer_pdf(ctx: RunContext, spec: ReportSpec, own_event_id: str,
                   own_periods: list[Period], rosters: dict) -> None:
    """Build and deliver Voluntarios.pdf for one report."""
    print("\nBuilding volunteer attendance report...", flush=True)
    if spec.volunteer_event:
        vid  = ctx.event_id(spec.volunteer_event)
        span = ctx.periods(vid, ctx.today - timedelta(weeks=spec.volunteer_weeks + 2), spec.volunteer_weeks + 2)
        checkins, included = ctx.checkins(vid, span)
        periods = periods_with_checkins(span, checkins)[-spec.volunteer_weeks:]
        # Name each worker's group after the location they serve in this report.
        served = {m.person_id: name for name, r in rosters.items() for m in r.workers}
        report = build_volunteer_report(
            "Asistencia de voluntarios", checkins, included, periods, ctx.tz,
            min_age=spec.volunteer_min_age,
            group_of=lambda pid, _loc: served.get(pid, "Sin asignar"),
        )
    else:
        periods = own_periods[-spec.volunteer_weeks:]
        checkins, included = ctx.checkins(own_event_id, periods)
        report = build_volunteer_report(
            "Asistencia de voluntarios", checkins, included, periods, ctx.tz,
        )
    print(f"  {len(report.rows)} volunteers over {len(report.periods)} Sundays.", flush=True)
    path = generate_volunteer_pdf(report, spec.label, os.path.join(ctx.workdir, f"{spec.id}-volunteers.pdf"))
    _deliver(ctx, path, [VOLUNTEERS_FOLDER, spec.label], VOLUNTEERS_FILENAME)


# ── Entry points ──────────────────────────────────────────────────────────────

def run_report(
    spec: ReportSpec,
    weeks: int | None = None,
    dry_run: bool = False,
    output_dir: str = "./out",
    location_filter: str | None = None,
    ctx: RunContext | None = None,
):
    """Run the full roster pipeline for one configured report.

      1. Fetch every Sunday since the report's history start, with check-ins
         (people, locations and service times sideloaded — no per-person calls).
      2. Build one roster per location: active, "hace tiempo", workers.
      3. Look up parents for the kids (two batched People API passes).
      4. Optionally add the bus-route column (spec.route_source_event).
      5. Write Roster.pdf per location, plus Instrucciones.pdf when enabled.
      6. Optionally write Voluntarios.pdf (spec.volunteer_report).
    """
    own_ctx = ctx is None
    ctx = ctx or RunContext(dry_run=dry_run, output_dir=output_dir)
    weeks = weeks or spec.resolved_weeks()
    try:
        print(f"Finding event {spec.pco_event!r} for report '{spec.id}'...", flush=True)
        try:
            event_id = ctx.event_id(spec.pco_event)
        except Exception as exc:
            _nothing_to_generate(
                spec, f"⚠ No Check-Ins event named {spec.pco_event!r} exists in Planning Center yet. ({exc})",
            )
            return

        since = spec.history_start(ctx.today)
        print(f"Finding Sundays since {since.isoformat()}...", flush=True)
        periods = ctx.periods(event_id, since, spec.max_history_weeks)
        if not periods:
            _nothing_to_generate(spec, f"⚠ {spec.pco_event!r} has no Sundays since {since.isoformat()}.")
            return

        print(f"Fetching check-ins for {len(periods)} Sundays...", flush=True)
        checkins, included = ctx.checkins(event_id, periods)
        periods = periods_with_checkins(periods, checkins)
        if not checkins or not periods:
            _nothing_to_generate(spec, f"⚠ No one has checked into {spec.pco_event!r} since {since.isoformat()}.")
            return

        _validate_location_filter(location_filter, included)
        route_map = _route_map(ctx, spec) if spec.route_source_event else {}
        rosters = build_rosters(checkins, included, periods, weeks,
                                route_map=route_map, location_filter=location_filter)

        kids = child_ids(rosters)
        print(f"Looking up parents for {len(kids)} kids...", flush=True)
        try:
            attach_guardians(rosters, ctx.guardians(kids))
        except Exception as e:
            print(f"  ⚠ Could not look up parents — rosters will omit them: {e}", flush=True)

        print(f"Locations to process: {sorted(rosters)}", flush=True)
        base = [spec.drive_folder_prefix] if spec.drive_folder_prefix else []
        for name in sorted(rosters):
            roster = rosters[name]
            print(f"\nGenerating {name} ({len(roster.active)} on the list, "
                  f"{roster.new_this_week} new this week, {len(roster.inactive)} hace tiempo, "
                  f"{len(roster.workers)} workers)...", flush=True)
            path = generate_roster_pdf(
                roster, spec.pdf_subtitle, os.path.join(ctx.workdir, f"{_slug(name)}.pdf"),
                show_route=spec.show_route, attendance_summary=spec.attendance_summary,
            )
            _deliver(ctx, path, base + [name], OUTPUT_FILENAMES["simple"])
            if spec.instructions:
                _deliver(ctx, ctx.instructions_pdf(), base + [name], INSTRUCTIONS_FILENAME,
                         fingerprint=instructions_fingerprint())

        if spec.volunteer_report and not location_filter:
            _volunteer_pdf(ctx, spec, event_id, periods, rosters)
    finally:
        if own_ctx:
            ctx.close()


def run_all(dry_run: bool = False, output_dir: str = "./out", theme: str | None = None) -> bool:
    """Run every enabled report in one process. Returns True if all succeeded.

    Each report uses `theme` if given, otherwise its own default_theme. A failing
    report is logged and skipped so the others still run.
    """
    ctx = RunContext(dry_run=dry_run, output_dir=output_dir)
    failed: list[str] = []
    try:
        for spec in enabled_reports():
            print(f"\n{'═' * 70}\n{spec.icon}  {spec.label}\n{'═' * 70}", flush=True)
            config._theme = config.THEMES[theme or spec.resolved_theme()]
            try:
                run_report(spec, ctx=ctx)
            except Exception as exc:
                failed.append(spec.id)
                print(f"\n  ✗ Report '{spec.id}' failed: {exc}", flush=True)
    finally:
        ctx.close()
    if failed:
        print(f"\nFailed reports: {', '.join(failed)}", flush=True)
    return not failed
