# promote_checkins.py
#
# Moves a class up a grade in Check-Ins **pre-select history**, without touching the
# "grade" field on People. Pre-select suggests whichever location a person checked
# into most recently, overriding any grade/age filters on the location — Planning
# Center has no bulk/official way to rewrite that history, so this replays a real
# check-in into the destination location using the same internal endpoint the
# Check-Ins web app itself calls (the public PCO API is read-only for check-ins).
#
# Typical use: the Sunday before grade-promotion weekend, run this once per class:
#
#   cd backend
#   python promote_checkins.py --list-locations                      # confirm exact names
#   python promote_checkins.py --from-location "2nd Grade" \
#                               --to-location "3rd Grade" --dry-run   # preview
#   python promote_checkins.py --from-location "2nd Grade" \
#                               --to-location "3rd Grade"             # do it
#
# --weeks (default 2) controls how far back we look for people to move — 2 weeks
# catches anyone who missed one Sunday but was present the other. Everyone found is
# checked into --to-location for the single most recent Sunday, at --time (default
# 10:00), so that becomes their newest check-in and pre-select points there starting
# next Sunday. --max-age (default 20) skips anyone at or above that age — e.g. an
# older student sitting in with a younger class shouldn't get promoted along with it.
#
# Requires PCO_SESSION_COOKIE and PCO_CSRF_TOKEN in .env — see the exception message
# below for how to get them from an active browser session.

import argparse
import os
import re

import requests

import planning_center_reports.config as config  # noqa: F401 — triggers .env loading
from planning_center_reports.pco_client import (
    age_from_birthday,
    get_checkins_for_event_periods,
    get_event_id,
    get_event_times,
    get_location_id,
    get_locations,
    get_person_details,
    get_recent_event_periods,
)

WEB_BASE = "https://check-ins.planningcenteronline.com"
BATCH_SIZE = 25  # people per bulk request, matches the PCO web UI's own batching

PCO_SESSION_COOKIE = os.getenv("PCO_SESSION_COOKIE")
PCO_CSRF_TOKEN = os.getenv("PCO_CSRF_TOKEN")


def get_web_session(event_period_id: str) -> requests.Session:
    """Build a requests session using the browser session cookie and CSRF token
    from an active Planning Center login. No public API alternative exists —
    creating check-ins is not part of the documented Check-Ins API."""
    if not PCO_SESSION_COOKIE:
        raise Exception(
            "PCO_SESSION_COOKIE not set in .env\n\n"
            "To get it:\n"
            "  1. Open check-ins.planningcenteronline.com in Chrome while logged in\n"
            "  2. Open DevTools (F12) → Application tab → Cookies → check-ins.planningcenteronline.com\n"
            "  3. Copy the value of 'planning_center_session'\n"
            "  4. Add to .env:  PCO_SESSION_COOKIE=<that value>\n\n"
            "To get the CSRF token:\n"
            "  1. In DevTools → Console, run:\n"
            "       document.querySelector('meta[name=csrf-token]').content\n"
            "  2. Add to .env:  PCO_CSRF_TOKEN=<that value>"
        )

    print("Building session from browser cookie...", flush=True)
    session = requests.Session()
    session.cookies.set(
        "planning_center_session", PCO_SESSION_COOKIE, domain="check-ins.planningcenteronline.com"
    )
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "X-Csrf-Token": PCO_CSRF_TOKEN or "",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Origin": WEB_BASE,
        "Referer": f"{WEB_BASE}/event_periods/{event_period_id}/check_ins",
    })

    test = session.get(f"{WEB_BASE}/event_periods/{event_period_id}/check_ins")
    if "planning center - login" in test.text.lower():
        raise Exception(
            "Session cookie is invalid or expired.\n"
            "Please refresh check-ins.planningcenteronline.com and grab a fresh cookie."
        )

    if not PCO_CSRF_TOKEN:
        m = re.search(r'<meta[^>]+name="csrf-token"[^>]+content="([^"]+)"', test.text)
        if not m:
            m = re.search(r'<meta[^>]+content="([^"]+)"[^>]+name="csrf-token"', test.text)
        if m:
            session.headers["X-Csrf-Token"] = m.group(1)
            print("  Got CSRF token from live page", flush=True)
        else:
            print("  Could not find CSRF token — will try without it", flush=True)

    print("  Session valid", flush=True)
    return session


def resolve_event_time_id(event_id: str, event_period_id: str, time_str: str) -> str:
    """Return the event_time ID matching `time_str` ("HH:MM", 24-hour) for the period.

    A period can have more than one service time — always pick explicitly rather
    than defaulting to "whichever comes back first" from the API.
    """
    try:
        hour, minute = (int(p) for p in time_str.split(":"))
    except ValueError:
        raise Exception(f"--time must be HH:MM (24-hour), got '{time_str}'")

    times = get_event_times(event_id, event_period_id)
    for et in times:
        if et["hour"] == hour and et["minute"] == minute:
            return et["id"]

    available = ", ".join(f"{et['hour']:02d}:{et['minute']:02d} ({et['name']})" for et in times) or "none found"
    raise Exception(f"No event_time at {time_str} for this period. Available: {available}")


def filter_by_max_age(members: list, max_age: int) -> list:
    """Drop anyone whose age (from their People birthday) is >= max_age.
    People with no birthday on file are kept (can't be excluded, but also
    shouldn't silently vanish from the batch)."""
    kept = []
    for m in members:
        details = get_person_details(m["account_center_person_id"])
        birthday = details.get("birthday", "")
        if not birthday:
            kept.append(m)
            continue
        age = age_from_birthday(birthday)
        if age >= max_age:
            print(f"  Skipping {m['first_name']} {m['last_name']} (age {age}, >= {max_age})", flush=True)
        else:
            kept.append(m)
    return kept


def get_people_seen_at_location(event_id: str, period_ids: list, location_id: str) -> list:
    """Return unique people (id, first_name, last_name) who checked into `location_id`
    during any of `period_ids`."""
    checkins, included = get_checkins_for_event_periods(event_id, period_ids)
    person_lookup = {i["id"]: i["attributes"] for i in included if i["type"] == "Person"}

    seen = {}
    for checkin in checkins:
        location_data = checkin["relationships"].get("locations", {}).get("data") or []
        if not any(loc["id"] == location_id for loc in location_data):
            continue
        person_rel = checkin["relationships"].get("person", {}).get("data")
        if not person_rel:
            continue
        person_id = person_rel["id"]
        if person_id in seen:
            continue
        attrs = person_lookup.get(person_id, {})
        seen[person_id] = {
            "account_center_person_id": person_id,
            "first_name": attrs.get("first_name", ""),
            "last_name": attrs.get("last_name", ""),
        }
    return list(seen.values())


def bulk_checkin(session, event_period_id, event_time_id, event_id, location_id, members):
    """POST to the internal bulk_check_ins endpoint used by the PCO web UI.
    Returns (success_count, duplicate_count, error_count)."""
    url = f"{WEB_BASE}/event_periods/{event_period_id}/bulk_check_ins"
    total_success = 0
    total_dupes = 0
    total_errors = 0

    for i in range(0, len(members), BATCH_SIZE):
        batch = members[i:i + BATCH_SIZE]
        print(f"\n  Sending batch {i // BATCH_SIZE + 1} ({len(batch)} people)...", flush=True)

        form_data = [("check-in-kind", "Regular")]
        for m in batch:
            prefix = "bulk_check_in[check_ins_attributes][]"
            form_data += [
                (f"{prefix}[first_name]", m["first_name"]),
                (f"{prefix}[last_name]", m["last_name"]),
                (f"{prefix}[account_center_person_id]", m["account_center_person_id"]),
                (f"{prefix}[check_in_times_attributes][][location_id]", str(location_id)),
                (f"{prefix}[check_in_times_attributes][][event_time_id]", str(event_time_id)),
                (f"{prefix}[check_in_times_attributes][][kind]", "Regular"),
                (f"{prefix}[event_id]", str(event_id)),
                (f"{prefix}[event_period_id]", str(event_period_id)),
            ]

        resp = session.post(url, data=form_data)

        if not resp.ok:
            print(f"  Batch failed ({resp.status_code}): {resp.text[:300]}", flush=True)
            total_errors += len(batch)
            continue

        if not resp.text.strip():
            print(f"  {len(batch)} submitted successfully", flush=True)
            total_success += len(batch)
            continue

        if "text/html" in resp.headers.get("Content-Type", "") or resp.text.strip().startswith("<!DOCTYPE"):
            print("  Got HTML response — session or CSRF token may be expired", flush=True)
            total_errors += len(batch)
            continue

        try:
            result = resp.json()
            success = result.get("total", 0) - result.get("duplicate_count", 0)
            dupes = result.get("duplicate_count", 0)
            total_success += success
            total_dupes += dupes
            print(f"  {success} checked in, {dupes} duplicates skipped", flush=True)
        except Exception:
            print(f"  {len(batch)} submitted (response: {resp.text[:80]})", flush=True)
            total_success += len(batch)

    return total_success, total_dupes, total_errors


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Move a Sunday school class up a grade in Check-Ins pre-select history: "
            "checks everyone seen at --from-location in the last --weeks Sundays into "
            "--to-location for the most recent Sunday."
        )
    )
    parser.add_argument("--event", default="Escuela Dominical", help="PCO Check-Ins event name")
    parser.add_argument("--from-location", help="Current class name (source of who to move)")
    parser.add_argument("--to-location", help="Next class name (destination)")
    parser.add_argument(
        "--weeks", type=int, default=2,
        help="How many recent Sundays to search for attendees of --from-location (default: 2)",
    )
    parser.add_argument(
        "--time", default="10:00",
        help="Service time to check people into, HH:MM 24-hour (default: 10:00)",
    )
    parser.add_argument(
        "--max-age", type=int, default=20,
        help="Skip anyone whose age is at or above this (default: 20 — i.e. don't move 20+)",
    )
    parser.add_argument(
        "--list-locations", action="store_true",
        help="Print all Check-Ins locations for --event and exit — use this to get exact names",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print who would be moved without submitting any check-ins",
    )
    args = parser.parse_args()

    event_id = get_event_id(args.event)

    if args.list_locations:
        for loc in get_locations(event_id):
            print(loc["name"])
        return

    if not args.from_location or not args.to_location:
        parser.error("--from-location and --to-location are required (or use --list-locations)")

    period_ids, period_dates, _ = get_recent_event_periods(event_id, weeks=args.weeks)
    destination_period_id = period_ids[0]  # most recent Sunday
    print(f"Destination Sunday: {period_dates[destination_period_id]} (period {destination_period_id})", flush=True)

    from_location_id = get_location_id(event_id, args.from_location)
    to_location_id = get_location_id(event_id, args.to_location)

    members = get_people_seen_at_location(event_id, period_ids, from_location_id)
    if not members:
        print(f"No one found at '{args.from_location}' in the last {args.weeks} week(s) — nothing to do.")
        return

    print(f"\nFound {len(members)} people at '{args.from_location}':", flush=True)
    for m in members:
        print(f"  - {m['first_name']} {m['last_name']}", flush=True)

    print(f"\nChecking ages (skipping {args.max_age}+)...", flush=True)
    members = filter_by_max_age(members, args.max_age)
    if not members:
        print("Nobody left to move after the age filter — nothing to do.")
        return

    event_time_id = resolve_event_time_id(event_id, destination_period_id, args.time)

    if args.dry_run:
        print(f"\n[dry-run] Would check {len(members)} people into '{args.to_location}' "
              f"for {period_dates[destination_period_id]} at {args.time}. No changes made.")
        for m in members:
            print(f"  - {m['first_name']} {m['last_name']}", flush=True)
        return

    session = get_web_session(destination_period_id)

    print(f"\nChecking {len(members)} people into '{args.to_location}' "
          f"for {period_dates[destination_period_id]} at {args.time}...", flush=True)
    success, dupes, errors = bulk_checkin(
        session, destination_period_id, event_time_id, event_id, to_location_id, members
    )

    print(f"\nDone. {success} checked in, {dupes} duplicates, {errors} errors.")


if __name__ == "__main__":
    main()
