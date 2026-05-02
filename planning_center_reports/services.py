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
    get_person_details,
    get_recent_event_periods,
    _person_cache,
)
from planning_center_reports.pdf.rosters import (
    generate_address_pdf,
    generate_simple_roster_pdf,
)


def _build_attendees(checkins: list, included: list, total_weeks: int = 5) -> tuple:
    """Transform raw PCO check-in data into grouped attendee records.

    Returns (grouped, location_lookup) where:
      grouped          — dict mapping location_name → list of Attendee dicts
      location_lookup  — dict mapping location_id → location_name

    Each attendee record is deduplicated per location (a person who attended
    multiple weeks appears only once). The `attendance` field counts how many
    of the `total_weeks` periods the person was present.
    """
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

        unique_count += 1
        grouped[location_name].append(record)

    print(f"  Processed {unique_count} unique, skipped {skip_count} duplicates.", flush=True)
    return dict(grouped), location_lookup


def run_rutas(weeks: int = 5):
    """Run the full pipeline for the Rutas (bus routes) event.

    For each bus route location:
      1. Fetches check-ins for the last `weeks` Sundays.
      2. Enriches attendee records with person details from the People API.
      3. Generates Direcciones-Roster.pdf (address-grouped) and Roster.pdf (alphabetical).
      4. Uploads both PDFs to the corresponding Drive subfolder.
    """
    print("Finding event 'Rutas'...", flush=True)
    event_id = get_event_id("Rutas")
    print("Event ID:", event_id, flush=True)

    print(f"Finding recent event periods (last {weeks} weeks)...", flush=True)
    event_period_ids = get_recent_event_periods(event_id, weeks=weeks)

    print("Fetching check-ins...", flush=True)
    checkins, included = get_checkins_for_event_periods(event_id, event_period_ids)

    grouped, location_lookup = _build_attendees(checkins, included, weeks)
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
      3. Generates Roster.pdf (alphabetical).
      4. Uploads it to the corresponding Drive subfolder.
    """
    print("Finding event 'Escuela Dominical'...", flush=True)
    event_id = get_event_id("Escuela Dominical")
    print("Event ID:", event_id, flush=True)

    print(f"Finding recent event periods (last {weeks} weeks)...", flush=True)
    period_ids = get_recent_event_periods(event_id, weeks=weeks)

    print("Fetching Escuela Dominical check-ins...", flush=True)
    checkins, included = get_checkins_for_event_periods(event_id, period_ids)

    grouped, location_lookup = _build_attendees(checkins, included, weeks)
    print(f"Locations found: {list(location_lookup.values())}", flush=True)

    print("\nConnecting to Google Drive...", flush=True)
    drive_service = get_drive_service()

    for location_name, attendees in grouped.items():
        vc = sum(1 for p in attendees if p.get("is_visitor"))
        print(f"\nGenerating roster for {location_name} "
              f"({len(attendees)} attendees, {vc} new this week)...", flush=True)

        pdf_file  = generate_simple_roster_pdf(
            location_name, "Escuela Dominical", attendees, "Roster.pdf"
        )
        folder_id = get_or_create_folder(drive_service, GOOGLE_DRIVE_PARENT_FOLDER_ID, location_name)
        upload_and_replace(drive_service, folder_id, pdf_file, "Roster.pdf")
        os.remove(pdf_file)
        print(f"  ✓ Uploaded Roster.pdf for {location_name}", flush=True)
