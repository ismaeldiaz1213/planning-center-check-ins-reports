# planning_center_reports/services.py
#
# Orchestration layer: fetch data from PCO, transform it into attendee records,
# generate PDFs, and upload them to Google Drive.
#
# There is one public entry point — run_report(spec) — which owns the full
# pipeline for any configured report. Everything that used to differ between the
# Rutas and Escuela Dominical runs (route lookup, helper detection, attendance
# summaries, which PDFs to emit, where to upload them) is now a flag on the
# ReportSpec, and every one of those flags is optional. See reports.py.
#
# run_rutas / run_escuela_dominical remain as thin wrappers for backwards
# compatibility with existing callers.
#
# _build_attendees is kept here (rather than in pco_client) because it is a
# transformation step that mixes API data with derived fields; it is tested
# separately in tests/test_attendance.py.

import os
import shutil
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

from planning_center_reports.config import GOOGLE_DRIVE_PARENT_FOLDER_ID
from planning_center_reports.drive_client import (
    get_drive_service,
    get_or_create_folder,
    upload_and_replace,
)
from planning_center_reports.pco_client import (
    get_checkins_for_event_periods,
    get_event_id,
    get_helpers_set,
    get_person_details,
    get_recent_event_periods,
    _person_cache,
)
from planning_center_reports.pdf.rosters import (
    generate_address_pdf,
    generate_simple_roster_pdf,
)
from planning_center_reports.reports import OUTPUT_FILENAMES, ReportSpec, get_report


def _get_route_mapping(event_name: str, weeks: int = 5) -> dict:
    """Build a person_id → route_name mapping from `event_name`'s check-ins.

    Returns a dict where keys are person_ids and values are route names
    (e.g. "Ruta 1 - Bus"). Each person is mapped to the first route seen for
    them in the returned check-in list. Reports with no bus ministry should skip
    this call entirely rather than pass an event name.
    """
    print(f"  Building route mappings from {event_name} check-ins...", flush=True)
    route_map = {}
    try:
        event_id = get_event_id(event_name)
        event_period_ids, _, _ = get_recent_event_periods(event_id, weeks=weeks)
        checkins, included = get_checkins_for_event_periods(event_id, event_period_ids)

        location_lookup = {
            item["id"]: item["attributes"]["name"]
            for item in included if item["type"] == "Location"
        }

        # For each person, find their route (first location they checked into)
        seen = set()
        for checkin in checkins:
            person_rel = checkin["relationships"].get("person", {}).get("data")
            person_id = person_rel["id"] if person_rel else None
            if person_id and person_id not in seen:
                location_data = checkin["relationships"]["locations"]["data"]
                if location_data:
                    location_id = location_data[0]["id"]
                    route_name = location_lookup.get(location_id, "")
                    if route_name:
                        route_map[person_id] = route_name
                        seen.add(person_id)

        print(f"  Mapped {len(route_map)} people to routes.", flush=True)
    except Exception as e:
        print(f"  ⚠ Could not build route mapping: {e}", flush=True)

    return route_map


def _build_attendees(
    checkins: list,
    included: list,
    total_weeks: int = 5,
    helpers_set: set = None,
    route_map: dict = None,
    location_filter: str | None = None,
) -> tuple:
    """Transform raw PCO check-in data into grouped attendee records.

    Returns (grouped, location_lookup) where:
      grouped          — dict mapping location_name → list of Attendee dicts
      location_lookup  — dict mapping location_id → location_name

    Each attendee record is deduplicated per location (a person who attended
    multiple weeks appears only once). The `attendance` field counts how many
    of the `total_weeks` periods the person was present.

    Parameters
    ----------
    helpers_set  — optional set of person_ids who are helpers (age 16+ from Junta)
    route_map    — optional dict mapping person_id → route_name (for Escuela Dominical)
    """
    if helpers_set is None:
        helpers_set = set()
    if route_map is None:
        route_map = {}

    location_lookup = {
        item["id"]: item["attributes"]["name"]
        for item in included if item["type"] == "Location"
    }
    person_lookup = {
        item["id"]: item
        for item in included if item["type"] == "Person"
    }

    # First pass — count distinct event-period IDs per (person, location) pair
    attendance_counts: dict = defaultdict(set)
    for checkin in checkins:
        location_data = checkin["relationships"]["locations"]["data"]
        if not location_data:
            continue
        location_id   = location_data[0]["id"]
        location_name = location_lookup.get(location_id, "Unknown Location")
        person_rel    = checkin["relationships"].get("person", {}).get("data")
        person_id     = person_rel["id"] if person_rel else None
        ep_id = (checkin
                 .get("relationships", {})
                 .get("event_period", {})
                 .get("data", {})
                 .get("id"))
        if person_id and ep_id:
            attendance_counts[(person_id, location_name)].add(ep_id)

    # Second pass — build one record per unique (person, location) pair
    grouped: dict      = defaultdict(list)
    seen: dict         = defaultdict(set)
    unique_count = 0
    skip_count   = 0

    for checkin in checkins:
        location_data = checkin["relationships"]["locations"]["data"]
        if not location_data:
            continue

        location_id   = location_data[0]["id"]
        location_name = location_lookup.get(location_id, "Unknown Location")

        # Skip non-matching locations before any API calls
        if location_filter and location_filter.lower() not in location_name.lower():
            continue

        person_rel    = checkin["relationships"].get("person", {}).get("data")
        person_id     = person_rel["id"] if person_rel else None

        # Deduplicate within each location across all fetched weeks
        if person_id and person_id in seen[location_name]:
            skip_count += 1
            continue
        if person_id:
            seen[location_name].add(person_id)

        weeks_attended = len(attendance_counts.get((person_id, location_name), set()))
        attendance_str = f"{weeks_attended}/{total_weeks}" if person_id else ""

        record = {
            "person_id":  person_id,
            "first_name": checkin["attributes"]["first_name"],
            "last_name":  checkin["attributes"]["last_name"],
            "phone":      "",
            "address":    "",
            "birthday":   "",
            "grade":      "",
            "created_at": "",
            "is_visitor": False,
            "attendance": attendance_str,
            "route":      "",
            "is_helper":  False,
        }

        if person_id:
            # Sideloaded Person data gives us the birthday without an extra request
            sideloaded = person_lookup.get(person_id)
            if sideloaded:
                record["birthday"] = sideloaded["attributes"].get("birthdate") or ""

            if person_id not in _person_cache:
                print(f"  [{unique_count + 1}] Fetching {record['first_name']} "
                      f"{record['last_name']} (id: {person_id})...", flush=True)
                time.sleep(0.5)   # gentle rate-limiting between person fetches
            else:
                print(f"  [{unique_count + 1}] Cached: "
                      f"{record['first_name']} {record['last_name']}", flush=True)

            details = get_person_details(person_id)
            record.update({k: v for k, v in details.items()})
            # Restore attendance after update (get_person_details doesn't return it)
            record["attendance"] = attendance_str

            # Visitor = added to PCO within the last 7 days
            created_str = record.get("created_at", "")
            if created_str:
                try:
                    created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    record["is_visitor"] = (datetime.now(timezone.utc) - created_dt).days < 7
                except Exception:
                    pass

            # Helper = in the helpers_set
            record["is_helper"] = person_id in helpers_set

            # Route = from the route_map, but never shown for helpers (bus workers)
            if person_id in route_map and person_id not in helpers_set:
                record["route"] = route_map[person_id]

        unique_count += 1
        grouped[location_name].append(record)

    print(f"  Processed {unique_count} unique, skipped {skip_count} duplicates.", flush=True)
    return dict(grouped), location_lookup


def _build_sunday_data(
    checkins: list,
    period_ids: list,
    period_dates: dict,
    location_id: str,
    helpers_set: set,
    period_starts_at: dict,
    person_created_at: dict,
) -> list:
    """Return per-Sunday attendance dicts for one class location.

    Each entry: {"label": "Abr 6", "regular": N, "visitors": M}
    Helpers are excluded. Visitor status is evaluated per Sunday: a person is
    a visitor for a given period if they were added to PCO within 7 days before
    that period's start date (not relative to today).
    """
    from planning_center_reports.models import _is_visitor_for_period

    period_regular  = {pid: set() for pid in period_ids}
    period_visitors = {pid: set() for pid in period_ids}

    for checkin in checkins:
        person_rel = checkin["relationships"].get("person", {}).get("data")
        person_id  = person_rel["id"] if person_rel else None
        if not person_id or person_id in helpers_set:
            continue

        if location_id:
            loc_ids = [loc["id"] for loc in checkin["relationships"]["locations"]["data"]]
            if location_id not in loc_ids:
                continue

        period_id = checkin["relationships"]["event_period"]["data"]["id"]
        if period_id not in period_regular:
            continue

        created   = person_created_at.get(person_id, "")
        starts_at = period_starts_at.get(period_id, "")
        if _is_visitor_for_period(created, starts_at):
            period_visitors[period_id].add(person_id)
        else:
            period_regular[period_id].add(person_id)

    return [
        {
            "label":    period_dates.get(pid, ""),
            "regular":  len(period_regular[pid]),
            "visitors": len(period_visitors[pid]),
        }
        for pid in period_ids
    ]


def _validate_location_filter(location_filter: str | None, included: list) -> None:
    """Exit early if location_filter matches nothing in the sideloaded location data.
    Called right after the check-in fetch so we fail before helpers + person detail calls."""
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


def _filter_locations(grouped: dict, location_filter: str | None) -> dict:
    """Return grouped filtered to locations whose name contains location_filter (case-insensitive).
    Exits with an error listing available locations if no match is found."""
    if not location_filter:
        return grouped
    filtered = {k: v for k, v in grouped.items() if location_filter.lower() in k.lower()}
    if not filtered:
        print(f"No location matching '{location_filter}'.", flush=True)
        print(f"Available: {sorted(grouped.keys())}", flush=True)
        sys.exit(1)
    return filtered


def _save_pdf_locally(pdf_path: str, location_name: str, filename: str,
                      output_dir: str, folder_prefix: str | None = None) -> None:
    """Copy a generated PDF to output_dir, prefixed with the location name.

    When the report defines a drive_folder_prefix, mirror that nesting locally so
    a --dry-run tree matches what would land in Google Drive.
    """
    if folder_prefix:
        output_dir = os.path.join(output_dir, _slug(folder_prefix))
    os.makedirs(output_dir, exist_ok=True)
    dest = os.path.join(output_dir, f"{_slug(location_name)}_{filename}")
    shutil.copy(pdf_path, dest)
    print(f"  [dry-run] Saved → {dest}", flush=True)


def _slug(name: str) -> str:
    """Filesystem-safe form of a location or folder name."""
    return name.replace("/", "-").replace(" ", "_").replace('"', "")


def _resolve_drive_folder(drive_service, spec: ReportSpec, location_name: str) -> str:
    """Return the Drive folder ID this report's PDFs for `location_name` belong in.

    With no drive_folder_prefix the location folder sits directly under the
    configured parent, which is the original behaviour. With a prefix, the
    location folder is nested one level deeper — this is what keeps two reports
    that share class names (e.g. the two Escuela Dominical sessions) from
    overwriting each other's rosters.
    """
    parent_id = GOOGLE_DRIVE_PARENT_FOLDER_ID
    if spec.drive_folder_prefix:
        parent_id = get_or_create_folder(drive_service, parent_id, spec.drive_folder_prefix)
    return get_or_create_folder(drive_service, parent_id, location_name)


def _nothing_to_generate(spec: ReportSpec, reason: str) -> None:
    """Report that a run produced no PDFs, without treating it as a failure.

    A report is often configured before its Check-Ins event exists or before
    anyone has checked into it — a new class that has not started meeting yet.
    That is an expected state, not an error, so the run exits 0 and says so
    plainly; nothing about the schedule or the job needs to change.
    """
    print(f"\n  {reason}", flush=True)
    print(f"  Nothing to generate for report '{spec.id}' — this is not an error.", flush=True)
    print("  Rosters will be produced automatically once check-ins start "
          "arriving for this event.", flush=True)


def run_report(
    spec: ReportSpec,
    weeks: int = 5,
    dry_run: bool = False,
    output_dir: str = "./out",
    location_filter: str | None = None,
):
    """Run the full roster pipeline for one configured report.

    For each location that had check-ins in the last `weeks` weeks:
      1. Fetches check-ins for the report's PCO event.
      2. Enriches attendee records with person details from the People API.
      3. Optionally marks helpers          (only when spec.helpers_event is set).
      4. Optionally maps people to routes  (only when spec.route_source_event is set).
      5. Optionally builds per-Sunday attendance summaries (spec.attendance_summary).
      6. Generates the PDFs named in spec.outputs.
      7. Uploads them to Drive, or saves them to output_dir when dry_run.

    Every step after (2) is opt-in, so a report that declares none of them makes
    no extra PCO calls at all.
    """
    print(f"Finding event {spec.pco_event!r} for report '{spec.id}'...", flush=True)
    try:
        event_id = get_event_id(spec.pco_event)
    except Exception as exc:
        _nothing_to_generate(
            spec,
            f"⚠ No Check-Ins event named {spec.pco_event!r} exists in Planning Center yet. ({exc})",
        )
        return
    print("Event ID:", event_id, flush=True)

    print(f"Finding recent event periods (last {weeks} weeks)...", flush=True)
    period_ids, period_dates, period_starts_at = get_recent_event_periods(event_id, weeks=weeks)
    if not period_ids:
        _nothing_to_generate(
            spec, f"⚠ {spec.pco_event!r} has no event periods in the last {weeks} weeks."
        )
        return

    print("Fetching check-ins...", flush=True)
    checkins, included = get_checkins_for_event_periods(event_id, period_ids)
    if not checkins:
        _nothing_to_generate(
            spec, f"⚠ No one has checked into {spec.pco_event!r} in the last {weeks} weeks."
        )
        return

    # Validate filter before the expensive helper, route-map, and person-detail fetches
    _validate_location_filter(location_filter, included)

    # Optional feature: helper detection. Skipped entirely when unconfigured.
    helpers_set = (
        get_helpers_set(spec.helpers_event, weeks=weeks, min_age=spec.helper_min_age)
        if spec.helpers_event else set()
    )

    # Optional feature: bus-route lookup. Skipped entirely when unconfigured.
    route_map = (
        _get_route_mapping(spec.route_source_event, weeks=weeks)
        if spec.route_source_event else {}
    )

    grouped, location_lookup = _build_attendees(
        checkins, included, weeks, helpers_set=helpers_set, route_map=route_map,
        location_filter=location_filter,
    )
    if not grouped:
        _nothing_to_generate(spec, "⚠ No attendees matched after filtering.")
        return
    print(f"Locations to process: {sorted(grouped.keys())}", flush=True)

    # Inverse map so we can look up location_id by name inside the loop
    name_to_location_id = {v: k for k, v in location_lookup.items()}

    drive_service = None
    if not dry_run:
        print("\nConnecting to Google Drive...", flush=True)
        drive_service = get_drive_service()

    for location_name, attendees in grouped.items():
        vc = sum(1 for p in attendees if p.get("is_visitor"))
        print(f"\nGenerating PDFs for {location_name} "
              f"({len(attendees)} attendees, {vc} new this week)...", flush=True)

        sunday_data = None
        if spec.attendance_summary:
            person_created_at = {
                p["person_id"]: p.get("created_at", "")
                for p in attendees if p.get("person_id")
            }
            sunday_data = _build_sunday_data(
                checkins, period_ids, period_dates,
                name_to_location_id.get(location_name),
                helpers_set, period_starts_at, person_created_at,
            )

        generated: list[tuple[str, str]] = []   # (local temp path, drive filename)
        for kind in spec.outputs:
            filename = OUTPUT_FILENAMES[kind]
            if kind == "address":
                path = generate_address_pdf(location_name, attendees, filename)
            else:
                path = generate_simple_roster_pdf(
                    location_name, spec.pdf_subtitle, attendees, filename,
                    show_route=spec.show_route, sunday_data=sunday_data,
                )
            generated.append((path, filename))

        try:
            if dry_run:
                for path, filename in generated:
                    _save_pdf_locally(path, location_name, filename, output_dir,
                                      spec.drive_folder_prefix)
            else:
                folder_id = _resolve_drive_folder(drive_service, spec, location_name)
                for path, filename in generated:
                    upload_and_replace(drive_service, folder_id, path, filename)
                names = " + ".join(f for _, f in generated)
                print(f"  ✓ Uploaded {names} for {location_name}", flush=True)
        finally:
            for path, _ in generated:
                if os.path.exists(path):
                    os.remove(path)


# ── Backwards-compatible wrappers ─────────────────────────────────────────────
# Kept so existing callers and tests that import run_rutas / run_escuela_dominical
# keep working. New code should call run_report() with a ReportSpec.

def run_rutas(weeks: int = 5, dry_run: bool = False, output_dir: str = "./out",
              location_filter: str | None = None):
    """Run the report configured under the id 'rutas' (or the PCO event "Rutas")."""
    return run_report(get_report("rutas"), weeks=weeks, dry_run=dry_run,
                      output_dir=output_dir, location_filter=location_filter)


def run_escuela_dominical(weeks: int = 5, dry_run: bool = False, output_dir: str = "./out",
                          location_filter: str | None = None):
    """Run the report configured under the id 'escuela' (or "Escuela Dominical")."""
    return run_report(get_report("escuela"), weeks=weeks, dry_run=dry_run,
                      output_dir=output_dir, location_filter=location_filter)
