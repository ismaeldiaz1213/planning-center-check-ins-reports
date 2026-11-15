# planning_center_reports/services.py
#
# Orchestration: fetch from PCO, shape with roster_data, draw with pdf/, then
# hand each file to the church's Delivery (Google Drive, or a local folder).
#
# Public entry points:
#   run_report(ctx, spec)  — one configured report
#   run_all(ctx)           — every enabled report of ctx.church
#
# A RunContext belongs to one church and one run. It carries that church's
# settings, Planning Center client and delivery, and caches what it fetches, so
# the Rutas event (route column for both Sunday schools), the Junta meeting and
# parent lookups are each fetched once however many reports use them — and one
# sequential run never hits PCO from several jobs at once. Nothing in this
# module reads the environment or module-level state.

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta

from planning_center_reports.church import ChurchConfig
from planning_center_reports.delivery import Delivery
from planning_center_reports.pco_client import PcoClient
from planning_center_reports.pdf.context import RenderContext
from planning_center_reports.pdf.instructions import build_instructions_pdf, instructions_fingerprint
from planning_center_reports.pdf.rosters import generate_roster_pdf
from planning_center_reports.pdf.volunteers import generate_volunteer_pdf
from planning_center_reports.reports import ReportSpec
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
    """One church's run: its settings, connections and per-run cache.

    Use it as a context manager (or call close()) so its work directory is removed.
    """

    def __init__(self, church: ChurchConfig, pco: PcoClient, delivery: Delivery):
        self.church   = church
        self.pco      = pco
        self.delivery = delivery
        self.tz       = church.tz
        self.texts    = church.texts
        self.workdir  = tempfile.mkdtemp(prefix="rosters-")
        self._event_ids: dict[str, str] = {}
        self._periods:   dict[tuple[str, date, int], list[Period]] = {}
        self._checkins:  dict[tuple[str, str], tuple[list, list]] = {}
        self._guardians: dict[str, dict] = {}
        self._instructions: str | None = None

    def __enter__(self) -> RunContext:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    @property
    def today(self) -> date:
        return datetime.now(self.tz).date()

    def render(self, theme: str | None = None) -> RenderContext:
        """The church's words, branding and colours; `theme` overrides its default."""
        return RenderContext.for_church(self.church, theme)

    def event_id(self, name: str) -> str:
        if name not in self._event_ids:
            self._event_ids[name] = self.pco.get_event_id(name)
        return self._event_ids[name]

    def periods(self, event_id: str, since: date, cap: int) -> list[Period]:
        key = (event_id, since, cap)
        if key not in self._periods:
            raw = self.pco.get_event_periods_since(event_id, since, tz=self.tz, max_periods=cap)
            self._periods[key] = [Period(p["id"], p["starts_at"], self.tz) for p in raw]
        return self._periods[key]

    def checkins(self, event_id: str, periods: list[Period]) -> tuple[list, list]:
        """Check-ins for `periods`, fetching only periods not already cached."""
        for p in periods:
            if (event_id, p.id) not in self._checkins:
                # One period per call keeps each period's sideloads with it, so
                # any later subset of Sundays has the people it needs. It costs
                # no extra requests — PCO pages per period either way.
                self._checkins[(event_id, p.id)] = self.pco.get_checkins_for_event_periods(event_id, [p.id])
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
            found = self.pco.get_guardians(missing)
            for i in missing:
                self._guardians[i] = found.get(i, {})
        return {i: self._guardians[i] for i in ids if self._guardians.get(i)}

    def instructions_pdf(self) -> str:
        if self._instructions is None:
            # The instructions bundle always uses the default look, whatever
            # campaign theme a report runs with.
            self._instructions = build_instructions_pdf(
                os.path.join(self.workdir, self.texts.t("file.instructions")), self.render(),
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
    """Filesystem-safe form of a location name, for files in the work directory."""
    return name.replace("/", "-").replace(" ", "_").replace('"', "")


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


def _volunteer_pdf(ctx: RunContext, spec: ReportSpec, render: RenderContext, own_event_id: str,
                   own_periods: list[Period], rosters: dict) -> None:
    """Build and deliver the volunteer attendance sheet for one report."""
    print("\nBuilding volunteer attendance report...", flush=True)
    title = ctx.texts.t("volunteers.title")
    if spec.volunteer_event:
        vid  = ctx.event_id(spec.volunteer_event)
        span = ctx.periods(vid, ctx.today - timedelta(weeks=spec.volunteer_weeks + 2), spec.volunteer_weeks + 2)
        checkins, included = ctx.checkins(vid, span)
        periods = periods_with_checkins(span, checkins)[-spec.volunteer_weeks:]
        # Name each worker's group after the location they serve in this report.
        served = {m.person_id: name for name, r in rosters.items() for m in r.workers}
        report = build_volunteer_report(
            title, checkins, included, periods, ctx.tz,
            min_age=spec.volunteer_min_age,
            group_of=lambda pid, _loc: served.get(pid),
        )
    else:
        periods = own_periods[-spec.volunteer_weeks:]
        checkins, included = ctx.checkins(own_event_id, periods)
        report = build_volunteer_report(title, checkins, included, periods, ctx.tz)
    print(f"  {len(report.rows)} volunteers over {len(report.periods)} Sundays.", flush=True)
    path = generate_volunteer_pdf(report, spec.label,
                                  os.path.join(ctx.workdir, f"{spec.id}-volunteers.pdf"), render)
    ctx.delivery.deliver(path, [ctx.texts.t("folder.volunteers"), spec.label],
                         ctx.texts.t("file.volunteers"))


# ── Entry points ──────────────────────────────────────────────────────────────

def run_report(
    ctx: RunContext,
    spec: ReportSpec,
    weeks: int | None = None,
    location_filter: str | None = None,
    theme: str | None = None,
) -> None:
    """Run the full roster pipeline for one configured report.

      1. Fetch every Sunday since the report's history start, with check-ins
         (people, locations and service times sideloaded — no per-person calls).
      2. Build one roster per location: active, "hace tiempo", workers.
      3. Look up parents for the kids (two batched People API passes).
      4. Optionally add the bus-route column (spec.route_source_event).
      5. Write Roster.pdf per location, plus Instrucciones.pdf when enabled.
      6. Optionally write Voluntarios.pdf (spec.volunteer_report).

    `weeks` overrides the report's active window; `theme` overrides its theme
    (which itself overrides the church's default).
    """
    weeks  = weeks or spec.default_weeks
    render = ctx.render(theme or spec.default_theme)
    texts  = ctx.texts

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
            roster, spec.pdf_subtitle, os.path.join(ctx.workdir, f"{_slug(name)}.pdf"), render,
            show_route=spec.show_route, attendance_summary=spec.attendance_summary,
        )
        ctx.delivery.deliver(path, base + [name], texts.t("file.roster"))
        if spec.instructions:
            ctx.delivery.deliver(ctx.instructions_pdf(), base + [name], texts.t("file.instructions"),
                                 fingerprint=instructions_fingerprint(ctx.render()))

    if spec.volunteer_report and not location_filter:
        _volunteer_pdf(ctx, spec, render, event_id, periods, rosters)


def run_all(ctx: RunContext, theme: str | None = None) -> bool:
    """Run every enabled report of ctx.church. Returns True if all succeeded.

    Each report uses `theme` if given, otherwise its own default_theme. A failing
    report is logged and skipped so the others still run.
    """
    failed: list[str] = []
    for spec in ctx.church.enabled_reports:
        print(f"\n{'═' * 70}\n{spec.icon}  {spec.label}\n{'═' * 70}", flush=True)
        try:
            run_report(ctx, spec, theme=theme)
        except Exception as exc:
            failed.append(spec.id)
            print(f"\n  ✗ Report '{spec.id}' failed: {exc}", flush=True)
    if failed:
        print(f"\nFailed reports: {', '.join(failed)}", flush=True)
    return not failed
