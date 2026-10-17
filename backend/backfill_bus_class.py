# backfill_bus_class.py
#
# Seeds the "C" Escuela Dominical classes (the bus-route kids' Sunday school) with
# their students, so Check-Ins pre-select suggests the right "C" class for each kid.
#
# Pre-select suggests whichever location a person checked into most recently. A new
# event has no history, so nobody gets a suggestion until they've been checked in
# once by hand. This replays one check-in per bus kid into last Sunday's "C" period,
# using the same internal bulk endpoint as promote_checkins.py.
#
# Who: anyone checked into a "Ruta …" location of --route-event in the last --weeks
# Sundays (drivers/captains/helpers check into a non-"Ruta" location and are skipped),
# who is under --max-age, AND who also checked into the regular Escuela Dominical
# (--escuela-event) in that window. --include-non-attendees drops that last rule and
# also takes riders who never checked into Sunday school.
#
# Which class: People grade + gender (see assign_class). When a kid has no grade on
# file, the grade is taken from the class they've been attending in the regular
# Escuela Dominical. Anyone still without a 7–12 grade is skipped
# and listed, so they can be fixed in People and the tool re-run (re-runs are safe:
# PCO reports existing check-ins as duplicates rather than doubling them).
#
#   cd backend
#   python backfill_bus_class.py --dry-run     # preview who lands where
#   python backfill_bus_class.py               # do it
#
# Requires PCO_SESSION_COOKIE (and ideally PCO_CSRF_TOKEN) in .env — see
# promote_checkins.get_web_session.

import argparse
from collections import defaultdict

import planning_center_reports.config as config  # noqa: F401 — triggers .env loading
from planning_center_reports.pco_client import (
    age_from_birthday,
    get_checkins_for_event_periods,
    get_event_id,
    get_locations,
    get_person_details,
    get_recent_event_periods,
)
from promote_checkins import bulk_checkin, get_web_session, resolve_event_time_id

C_EVENT = '"C" Escuela Dominical'

# Regular Escuela Dominical class → grade, used only when People has no grade.
FALLBACK_CLASS_GRADES = {
    "7th Grade Boys": 7,  "7th Grade Girls": 7,
    "8th Grade Boys": 8,  "8th Grade Girls": 8,
    "9th and 10th Grade Boys": 9, "9th and 10th Grade Girls": 9,
    "11th and 12th Grade Class": 11,
}


def assign_class(grade: int | None, gender: str) -> str | None:
    """Return the "C" location name for a grade (7–12) and PCO gender, or None."""
    if grade is None or not 7 <= grade <= 12:
        return None
    if grade >= 11:
        return '"C" 11th &12th Coed'
    if gender not in ("Male", "Female"):
        return None
    side = "Boys" if gender == "Male" else "Girls"
    if grade == 7:
        return f'"C" 7th {side}'
    if grade == 8:
        return f'"C" 8th {side}'
    return f'"C" 9th &10th {side}'


def first_location_per_person(event_name: str, weeks: int, name_prefix: str = "") -> dict:
    """Return {person_id: {first_name, last_name, location}} for everyone checked into
    `event_name` in the last `weeks` periods, keeping their most recent location.
    With `name_prefix`, only locations starting with it count."""
    event_id = get_event_id(event_name)
    period_ids, _, _ = get_recent_event_periods(event_id, weeks=weeks)
    checkins, included = get_checkins_for_event_periods(event_id, period_ids)
    locations = {i["id"]: i["attributes"]["name"] for i in included if i["type"] == "Location"}
    people = {i["id"]: i["attributes"] for i in included if i["type"] == "Person"}

    # Check-ins come back newest period first, so the first hit is the latest.
    seen = {}
    for checkin in checkins:
        person_rel = checkin["relationships"].get("person", {}).get("data")
        location_data = checkin["relationships"].get("locations", {}).get("data") or []
        if not person_rel or not location_data:
            continue
        location = locations.get(location_data[0]["id"], "")
        if not location.startswith(name_prefix) or person_rel["id"] in seen:
            continue
        attrs = people.get(person_rel["id"], {})
        seen[person_rel["id"]] = {
            "first_name": attrs.get("first_name", ""),
            "last_name": attrs.get("last_name", ""),
            "location": location,
        }
    return seen


def plan_assignments(riders: dict, escuela_classes: dict, details: dict, max_age: int,
                     require_escuela: bool = True) -> tuple:
    """Split riders into ({c_location: [member, ...]}, [(member, reason), ...] skipped).

    riders          — {person_id: {first_name, last_name, location}} from the route event
    escuela_classes — {person_id: regular Escuela class name} for everyone who attended it
    details         — {person_id: {grade_num, gender, birthday}}
    require_escuela — only riders present in escuela_classes are considered
    """
    assignments = defaultdict(list)
    skipped = []
    for pid, rider in riders.items():
        if require_escuela and pid not in escuela_classes:
            continue
        member = {
            "account_center_person_id": pid,
            "first_name": rider["first_name"],
            "last_name": rider["last_name"],
            "route": rider["location"],
        }
        d = details.get(pid, {})
        age = age_from_birthday(d.get("birthday", ""))
        if age >= max_age:
            continue  # adults on the bus — not a skip worth reporting
        grade = d.get("grade_num")
        if grade is None:
            grade = FALLBACK_CLASS_GRADES.get(escuela_classes.get(pid, ""))
            member["grade_source"] = "class" if grade is not None else ""
        else:
            member["grade_source"] = "people"
        c_class = assign_class(grade, d.get("gender", ""))
        if c_class:
            assignments[c_class].append(member)
        elif grade is None and 11 <= age < max_age:
            # Teen-aged with no grade anywhere — likely belongs in "C" but needs fixing.
            skipped.append((member, f"no grade on file (age {age})"))
        elif grade is not None and 7 <= grade <= 12:
            skipped.append((member, f"grade {grade} but gender '{d.get('gender') or 'unknown'}'"))
    return dict(assignments), skipped


def main():
    parser = argparse.ArgumentParser(
        description='Check bus-route kids into their "C" Escuela Dominical class for the '
                    "most recent Sunday so Check-Ins pre-select suggests it."
    )
    parser.add_argument("--event", default=C_EVENT, help=f"Destination event (default: {C_EVENT})")
    parser.add_argument("--route-event", default="Rutas", help="Bus-route event (default: Rutas)")
    parser.add_argument("--route-prefix", default="Ruta",
                        help="Only riders checked into locations starting with this count (default: Ruta)")
    parser.add_argument("--escuela-event", default="Escuela Dominical",
                        help="Regular Sunday school event: riders must have attended it, and it "
                             "supplies the class for kids with no grade on file")
    parser.add_argument("--include-non-attendees", action="store_true",
                        help="Also take bus riders who never checked into --escuela-event")
    parser.add_argument("--weeks", type=int, default=5,
                        help="Recent Sundays to search for bus riders (default: 5)")
    parser.add_argument("--time", default="10:45",
                        help="Service time to check into, HH:MM 24-hour (default: 10:45)")
    parser.add_argument("--max-age", type=int, default=20,
                        help="Skip anyone at or above this age (default: 20)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the plan without submitting any check-ins")
    args = parser.parse_args()

    event_id = get_event_id(args.event)
    period_ids, period_dates, _ = get_recent_event_periods(event_id, weeks=1)
    destination_period_id = period_ids[0]
    location_ids = {loc["name"]: loc["id"] for loc in get_locations(event_id)}

    print(f"\nFinding bus riders in '{args.route_event}' (last {args.weeks} weeks)...", flush=True)
    riders = first_location_per_person(args.route_event, args.weeks, args.route_prefix)
    print(f"  {len(riders)} riders", flush=True)

    print(f"\nReading who attended '{args.escuela_event}' (last {args.weeks} weeks)...", flush=True)
    escuela = {
        pid: v["location"]
        for pid, v in first_location_per_person(args.escuela_event, args.weeks).items()
    }
    require_escuela = not args.include_non_attendees
    candidates = [pid for pid in riders if pid in escuela or not require_escuela]
    if require_escuela:
        print(f"  {len(candidates)} of {len(riders)} riders also attended '{args.escuela_event}' "
              f"— the rest are left out (--include-non-attendees to add them)", flush=True)

    print(f"\nLooking up grade/gender for {len(candidates)} riders (cached, may take a few minutes)...",
          flush=True)
    details = {}
    for pid in candidates:
        d = get_person_details(pid)
        details[pid] = {
            "grade_num": d.get("grade_num"),
            "gender": d.get("gender", ""),
            "birthday": d.get("birthday", ""),
        }

    assignments, skipped = plan_assignments(riders, escuela, details, args.max_age, require_escuela)

    missing = [name for name in assignments if name not in location_ids]
    if missing:
        raise Exception(f"Locations not found on '{args.event}': {missing}. "
                        f"Available: {sorted(location_ids)}")

    event_time_id = resolve_event_time_id(event_id, destination_period_id, args.time)
    when = f"{period_dates[destination_period_id]} at {args.time}"

    total = sum(len(m) for m in assignments.values())
    print(f"\nPlan: {total} kids into '{args.event}' for {when}", flush=True)
    for name in sorted(assignments):
        members = sorted(assignments[name], key=lambda m: (m["last_name"], m["first_name"]))
        print(f"\n  {name} — {len(members)}", flush=True)
        for m in members:
            note = "  (grade from class)" if m["grade_source"] == "class" else ""
            print(f"    - {m['first_name']} {m['last_name']}  [{m['route']}]{note}", flush=True)
    if skipped:
        print(f"\n  Skipped {len(skipped)} — fix in People and re-run to include them:", flush=True)
        for m, reason in skipped:
            print(f"    - {m['first_name']} {m['last_name']}  [{m['route']}]: {reason}", flush=True)

    if args.dry_run:
        print("\n[dry-run] No changes made.")
        return

    session = get_web_session(destination_period_id)
    totals = [0, 0, 0]
    for name in sorted(assignments):
        print(f"\nChecking {len(assignments[name])} into '{name}'...", flush=True)
        result = bulk_checkin(session, destination_period_id, event_time_id, event_id,
                              location_ids[name], assignments[name])
        totals = [t + r for t, r in zip(totals, result)]

    print(f"\nDone. {totals[0]} checked in, {totals[1]} duplicates, {totals[2]} errors.")


if __name__ == "__main__":
    main()
