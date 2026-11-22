# checkin_people_list.py
#
# Checks a list of people (from a class roster CSV) into one Check-Ins location for a
# specific past Sunday, so Check-Ins pre-select suggests that class for them next time.
# Uses the same internal bulk_check_ins endpoint as promote_checkins.py (the public
# Check-Ins API is read-only for check-ins).
#
# It never creates people. Names that don't match exactly one active person in People
# are reported and skipped.
#
#   cd backend
#   .venv/bin/python checkin_people_list.py --env-file .env.liberty \
#       --roster roster.csv --event "Adult Bible Classes" \
#       --location "Life Builders Bible Class" --date 2026-11-15 --time 09:30 --dry-run
#
# --roster is a CSV with "Last Name" and "First Name" header cells (any row, any
# column). --env-file holds that church's PCO_APP_ID / PCO_SECRET (Personal Access
# Token) and, for the real run, PCO_SESSION_COOKIE / PCO_CSRF_TOKEN. Its values
# override anything in the project's .env, so IBL's .env can stay as it is.
#
# Full guide (setup, reading the report, resolving duplicates): docs/check-in-tools.md

import argparse
import csv
import re
import sys
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import dotenv_values, load_dotenv


def parse_args():
    p = argparse.ArgumentParser(description=(
        "Check the people on a roster CSV into one Check-Ins location for a past Sunday, "
        "so pre-select suggests that class. Never creates people. See docs/check-in-tools.md."))
    p.add_argument("--env-file", required=True, help="Church-specific env file (overrides .env)")
    p.add_argument("--roster", required=True, help="CSV with 'Last Name' and 'First Name' columns")
    p.add_argument("--event", required=True, help="Check-Ins event name")
    p.add_argument("--location", required=True, help="Check-Ins location (class) name")
    p.add_argument("--date", help="Sunday to check into, YYYY-MM-DD (default: last Sunday before today)")
    p.add_argument("--time", default="09:30", help="Service time, HH:MM 24-hour (default 09:30)")
    p.add_argument("--tz", default="America/New_York", help="Church time zone (default America/New_York)")
    p.add_argument("--report", help="Write the match report to this CSV")
    p.add_argument("--add-ids", default="",
                   help="Comma-separated PCO person IDs to check in as well (e.g. a duplicate resolved by hand)")
    p.add_argument("--only-added", action="store_true",
                   help="Check in only the --add-ids people (for a follow-up run)")
    p.add_argument("--dry-run", action="store_true", help="Match and report only; check no one in")
    return p.parse_args()


# ── Roster ────────────────────────────────────────────────────────────────────

SUFFIX = re.compile(r",?\s*(jr\.?|sr\.?|ii|iii|iv)$", re.IGNORECASE)


def clean_last(name: str) -> str:
    return SUFFIX.sub("", name.strip()).strip(" ,")


def read_roster(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    header = next(
        (i for i, row in enumerate(rows)
         if {"last name", "first name"} <= {c.strip().lower() for c in row}),
        None,
    )
    if header is None:
        sys.exit("Roster has no 'Last Name' / 'First Name' header row")
    cells = [c.strip().lower() for c in rows[header]]
    li, fi = cells.index("last name"), cells.index("first name")

    people, seen = [], set()
    for row in rows[header + 1:]:
        if len(row) <= max(li, fi):
            continue
        last, first = row[li].strip(), row[fi].strip()
        if not last or not first:
            continue
        key = (last.lower(), first.lower())
        if key in seen:
            continue
        seen.add(key)
        people.append({"last": last, "first": first})
    return people


# ── Matching against People ───────────────────────────────────────────────────

def norm(s: str | None) -> str:
    return re.sub(r"[^a-z]", "", (s or "").lower())


def search_people(pco, field: str, value: str) -> list[dict]:
    url = f"{pco.base_url}/people/v2/people"
    params = {f"where[{field}]": value, "per_page": 100}
    out = []
    while url:
        resp = pco._get(url, params, label="people search")
        if resp is None:
            raise Exception("Could not reach Planning Center People")
        resp.raise_for_status()
        body = resp.json()
        out.extend(body["data"])
        url, params = body.get("links", {}).get("next"), None
    return out


def label(p: dict) -> str:
    a = p["attributes"]
    nick = f" ({a['nickname']})" if a.get("nickname") else ""
    return f"{a.get('first_name')}{nick} {a.get('last_name')}" + ("" if a.get("status") == "active" else " [inactive]")


def close(a: str, b: str) -> bool:
    a, b = norm(a), norm(b)
    return bool(a and b) and (a.startswith(b) or b.startswith(a) or SequenceMatcher(None, a, b).ratio() >= 0.75)


def match(pco, roster: list[dict]) -> list[dict]:
    by_last: dict[str, list] = {}
    by_first: dict[str, list] = {}
    results = []
    for r in roster:
        last = clean_last(r["last"])
        if last.lower() not in by_last:
            by_last[last.lower()] = search_people(pco, "last_name", last)
        candidates = by_last[last.lower()]
        want = norm(r["first"])
        hits = [
            p for p in candidates
            if want in {norm(p["attributes"].get(k)) for k in ("first_name", "nickname", "given_name")}
        ]
        active = [p for p in hits if p["attributes"].get("status") == "active"]
        row = {"roster_name": f"{r['first']} {r['last']}", "person_id": "", "pco_name": "",
               "result": "", "did_you_mean": ""}
        if len(active) == 1:
            a = active[0]["attributes"]
            row.update(person_id=active[0]["id"], pco_name=f"{a['first_name']} {a['last_name']}",
                       result="matched", _first=a["first_name"], _last=a["last_name"])
        elif len(active) > 1:
            row["result"] = "ambiguous"
            row["did_you_mean"] = "; ".join(f"{label(p)} (id {p['id']})" for p in active)
        elif hits:
            row["result"] = "inactive"
            row["did_you_mean"] = "; ".join(label(p) for p in hits)
        else:
            row["result"] = "not found"
            # Same last name, similar first name (Jon -> John, Bob -> Bobby).
            sugg = [p for p in candidates
                    if any(close(r["first"], p["attributes"].get(k)) for k in ("first_name", "nickname", "given_name"))]
            # Same first name, similar last name (a typo on the roster).
            if not sugg:
                key = r["first"].strip().lower()
                if key not in by_first:
                    by_first[key] = search_people(pco, "first_name", r["first"].strip())
                sugg = [p for p in by_first[key] if close(last, p["attributes"].get("last_name"))]
            row["did_you_mean"] = "; ".join(label(p) for p in sugg)
        results.append(row)
    return results


# ── Event lookups ─────────────────────────────────────────────────────────────

def find_event_time(pco, event_id: str, target: date, hh: int, mm: int, tz) -> tuple[str, str]:
    """Return (event_period_id, event_time_id) for the session on `target` at hh:mm."""
    url = f"{pco.base_url}/check-ins/v2/events/{event_id}/event_periods"
    resp = pco._get(url, {"order": "-starts_at", "per_page": 25}, label="event periods")
    resp.raise_for_status()
    for ep in resp.json()["data"]:
        t_url = f"{pco.base_url}/check-ins/v2/events/{event_id}/event_periods/{ep['id']}/event_times"
        t_resp = pco._get(t_url, {"per_page": 100}, label="event times")
        t_resp.raise_for_status()
        for et in t_resp.json()["data"]:
            starts = datetime.fromisoformat(et["attributes"]["starts_at"].replace("Z", "+00:00")).astimezone(tz)
            if starts.date() == target and (starts.hour, starts.minute) == (hh, mm):
                return ep["id"], et["id"]
    sys.exit(f"No session on {target} at {hh:02d}:{mm:02d} found in the last 25 periods of this event")


def main():
    args = parse_args()
    env_file = Path(args.env_file)
    if not env_file.is_file():
        sys.exit(f"{env_file} not found")
    load_dotenv(env_file, override=True)  # before anything reads the environment

    from planning_center_reports import legacy
    pco = legacy.pco_client()

    tz = ZoneInfo(args.tz)
    today = datetime.now(tz).date()
    target = date.fromisoformat(args.date) if args.date else today - timedelta(days=(today.weekday() + 1) % 7 or 7)
    if target >= today:
        sys.exit(f"--date {target} is not in the past; refusing (it would count as real attendance)")
    hh, mm = (int(x) for x in args.time.split(":"))

    org = pco._get(f"{pco.base_url}/people/v2", None, label="organization")
    org.raise_for_status()
    org_name = org.json()["data"]["attributes"]["name"]
    print(f"Organization: {org_name}", flush=True)

    event_id = pco.get_event_id(args.event)
    location_id = pco.get_location_id(event_id, args.location)
    period_id, event_time_id = find_event_time(pco, event_id, target, hh, mm, tz)
    print(f"Target: {args.event} / {args.location} on {target} {args.time} "
          f"(period {period_id}, event time {event_time_id})", flush=True)

    roster = read_roster(args.roster)
    print(f"Roster: {len(roster)} names. Matching against People...", flush=True)
    results = match(pco, roster)

    matched = [r for r in results if r["result"] == "matched"]
    skipped = [r for r in results if r["result"] != "matched"]
    print(f"\nMatched {len(matched)} of {len(results)}.")
    groups = [
        ("not found", "NOT IN PLANNING CENTER under the roster's spelling (skipped)"),
        ("ambiguous", "MORE THAN ONE active person with this name (skipped)"),
        ("inactive", "ONLY AN INACTIVE profile exists (skipped)"),
    ]
    for key, title in groups:
        rows = [r for r in skipped if r["result"] == key]
        if not rows:
            continue
        print(f"\n{title}: {len(rows)}")
        for r in rows:
            hint = f"   -> did you mean: {r['did_you_mean']}" if r["did_you_mean"] else "   -> no close match"
            print(f"  - {r['roster_name']:<28}{hint}")

    if args.report:
        with open(args.report, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["roster_name", "person_id", "pco_name", "result",
                                              "did_you_mean"], extrasaction="ignore")
            w.writeheader()
            w.writerows(results)
        print(f"\nReport written to {args.report}")

    extra_ids = [i.strip() for i in args.add_ids.split(",") if i.strip()]
    if extra_ids:
        data, _ = pco._people_batch(extra_ids, "")
        found = {p["id"]: p["attributes"] for p in data}
        missing = [i for i in extra_ids if i not in found]
        if missing:
            sys.exit(f"--add-ids not found in People: {', '.join(missing)}")
        added = [{"person_id": i, "pco_name": f"{found[i]['first_name']} {found[i]['last_name']}",
                  "_first": found[i]["first_name"], "_last": found[i]["last_name"]} for i in extra_ids]
        print(f"\nAdded by ID ({len(added)}):")
        for a in added:
            print(f"  + {a['pco_name']} (id {a['person_id']})")
        matched = added if args.only_added else matched + [a for a in added
                                                           if a["person_id"] not in {m["person_id"] for m in matched}]

    if args.dry_run:
        print(f"\n[dry-run] Would check {len(matched)} people into '{args.location}' for {target} "
              f"{args.time} in {org_name}. No changes made.")
        return

    from promote_checkins import bulk_checkin, get_web_session

    # The browser cookie must come from this church's env file, never from IBL's .env.
    if not dotenv_values(env_file).get("PCO_SESSION_COOKIE"):
        sys.exit(f"PCO_SESSION_COOKIE must be set in {env_file} for a real run")
    members = [{"account_center_person_id": r["person_id"], "first_name": r["_first"], "last_name": r["_last"]}
               for r in matched]
    session = get_web_session(period_id)
    print(f"\nChecking {len(members)} people into '{args.location}' for {target} {args.time}...", flush=True)
    success, dupes, errors = bulk_checkin(session, period_id, event_time_id, event_id, location_id, members)
    print(f"\nDone. {success} checked in, {dupes} duplicates, {errors} errors.")


if __name__ == "__main__":
    main()
