# planning_center_reports/services.py
#
# Orchestration layer: fetch data from PCO, transform it into attendee records,
# generate PDFs, and upload them to Google Drive.
#
# The two public functions — run_rutas and run_escuela_dominical — each own the
# full pipeline for their respective PCO event. They are called from cli.py
# after the theme and credentials have been set up.
#
# _build_attendees is kept here (rather than in pco_client) because it is a
# transformation step that mixes API data with derived fields; it is tested
# separately in tests/test_attendance.py.

import os
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


def _get_route_mapping(weeks: int = 5) -> dict:
    """Build a person_id → route_name mapping from Rutas check-ins.

    Returns a dict where keys are person_ids and values are route names
    (e.g. "Ruta 1 - Bus"). Each person is mapped to the first/most recent
    route they attended.
    """
    print("  Building route mappings from Rutas check-ins...", flush=True)
    route_map = {}
    try:
        event_id = get_event_id("Rutas")
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


def run_rutas(weeks: int = 5):
    """Run the full pipeline for the Rutas (bus routes) event.

    For each bus route location:
      1. Fetches check-ins for the last `weeks` Sundays.
      2. Enriches attendee records with person details from the People API.
      3. Marks helpers (age 16+ from Junta de Rutas Attendance).
      4. Generates Direcciones-Roster.pdf (address-grouped) and Roster.pdf (alphabetical).
      5. Uploads both PDFs to the corresponding Drive subfolder.
    """
    print("Finding event 'Rutas'...", flush=True)
    event_id = get_event_id("Rutas")
    print("Event ID:", event_id, flush=True)

    print(f"Finding recent event periods (last {weeks} weeks)...", flush=True)
    event_period_ids, _, _ = get_recent_event_periods(event_id, weeks=weeks)

    # Fetch helpers early — reused for Rutas rosters
    helpers_set = get_helpers_set(weeks=weeks)

    print("Fetching check-ins...", flush=True)
    checkins, included = get_checkins_for_event_periods(event_id, event_period_ids)

    grouped, location_lookup = _build_attendees(
        checkins, included, weeks, helpers_set=helpers_set
    )
    print(f"Locations found: {list(location_lookup.values())}", flush=True)

    print("\nConnecting to Google Drive...", flush=True)
    drive_service = get_drive_service()

    for location_name, attendees in grouped.items():
        vc = sum(1 for p in attendees if p.get("is_visitor"))
        print(f"\nGenerating PDFs for {location_name} "
              f"({len(attendees)} attendees, {vc} new this week)...", flush=True)

        addr_pdf  = generate_address_pdf(location_name, attendees, "Direcciones-Roster.pdf")
        lista_pdf = generate_simple_roster_pdf(
            location_name, "Ministerio de Autobuses", attendees, "Roster.pdf"
        )

        folder_id = get_or_create_folder(drive_service, GOOGLE_DRIVE_PARENT_FOLDER_ID, location_name)
        upload_and_replace(drive_service, folder_id, addr_pdf,  "Direcciones-Roster.pdf")
        upload_and_replace(drive_service, folder_id, lista_pdf, "Roster.pdf")
        os.remove(addr_pdf)
        os.remove(lista_pdf)
        print(f"  ✓ Uploaded Direcciones-Roster.pdf + Roster.pdf for {location_name}", flush=True)


def run_escuela_dominical(weeks: int = 5):
    """Run the full pipeline for the Escuela Dominical (Sunday school) event.

    For each class location:
      1. Fetches check-ins for the last `weeks` Sundays.
      2. Enriches attendee records with person details from the People API.
      3. Maps each person to their bus route (from Rutas check-ins).
      4. Filters out workers (age 16+ from Junta de Rutas Attendance).
      5. Generates Roster.pdf with route information and attendance summary.
      6. Uploads it to the corresponding Drive subfolder.
    """
    print("Finding event 'Escuela Dominical'...", flush=True)
    event_id = get_event_id("Escuela Dominical")
    print("Event ID:", event_id, flush=True)

    print(f"Finding recent event periods (last {weeks} weeks)...", flush=True)
    period_ids, period_dates, period_starts_at = get_recent_event_periods(event_id, weeks=weeks)

    # Fetch helpers and route mappings early
    helpers_set = get_helpers_set(weeks=weeks)
    route_map = _get_route_mapping(weeks=weeks)

    print("Fetching Escuela Dominical check-ins...", flush=True)
    checkins, included = get_checkins_for_event_periods(event_id, period_ids)

    grouped, location_lookup = _build_attendees(
        checkins, included, weeks, helpers_set=helpers_set, route_map=route_map
    )
    print(f"Locations found: {list(location_lookup.values())}", flush=True)

    # Inverse map so we can look up location_id by name inside the loop
    name_to_location_id = {v: k for k, v in location_lookup.items()}

    print("\nConnecting to Google Drive...", flush=True)
    drive_service = get_drive_service()

    for location_name, attendees in grouped.items():
        # Helpers remain on the roster — they just have no route (cleared in _build_attendees)
        vc = sum(1 for p in attendees if p.get("is_visitor"))
        print(f"\nGenerating roster for {location_name} "
              f"({len(attendees)} attendees, {vc} new this week)...", flush=True)

        # Build per-Sunday attendance counts for this class
        location_id       = name_to_location_id.get(location_name)
        person_created_at = {
            p["person_id"]: p.get("created_at", "")
            for p in attendees if p.get("person_id")
        }
        sunday_data = _build_sunday_data(
            checkins, period_ids, period_dates, location_id,
            helpers_set, period_starts_at, person_created_at,
        )

        pdf_file  = generate_simple_roster_pdf(
            location_name, "Escuela Dominical", attendees, "Roster.pdf",
            show_route=True, sunday_data=sunday_data,
        )
        folder_id = get_or_create_folder(drive_service, GOOGLE_DRIVE_PARENT_FOLDER_ID, location_name)
        upload_and_replace(drive_service, folder_id, pdf_file, "Roster.pdf")
        os.remove(pdf_file)
        print(f"  ✓ Uploaded Roster.pdf for {location_name}", flush=True)
