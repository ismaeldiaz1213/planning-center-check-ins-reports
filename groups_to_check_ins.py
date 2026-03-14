import os
import time
import requests
from datetime import datetime, timedelta, timezone
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

PCO_APP_ID = os.getenv("PCO_APP_ID")
PCO_SECRET = os.getenv("PCO_SECRET")
PCO_SESSION_COOKIE = os.getenv("PCO_SESSION_COOKIE")  # planning_center_session value from browser
PCO_CSRF_TOKEN = os.getenv("PCO_CSRF_TOKEN")          # csrf-token meta tag value from browser

API_BASE = "https://api.planningcenteronline.com"
WEB_BASE = "https://check-ins.planningcenteronline.com"
api_auth = HTTPBasicAuth(PCO_APP_ID, PCO_SECRET)

# Shared holder so get_web_session can reference the event_period_id
# (set in main() before calling get_web_session)
_event_period_id_holder = [None]

EVENT_NAME = "Escuela Dominical"
GROUP_NAME = "11th and 12th Grade Class"
LOCATION_NAME = "11th and 12th Grade Class"

BATCH_SIZE = 25  # people per bulk request


# ------------------------------
# Web Session (for bulk_check_ins)
# ------------------------------

def get_web_session():
    """
    Build a requests session using the browser session cookie and CSRF token
    from your active Planning Center login. No scraping needed.
    """
    import re

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

    print("Building session from browser cookie...")
    session = requests.Session()
    session.cookies.set(
        "planning_center_session",
        PCO_SESSION_COOKIE,
        domain="check-ins.planningcenteronline.com"
    )
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "X-Csrf-Token": PCO_CSRF_TOKEN or "",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Origin": "https://check-ins.planningcenteronline.com",
        "Referer": f"https://check-ins.planningcenteronline.com/event_periods/{_event_period_id_holder[0]}/check_ins",
    })

    # Verify the session is valid and grab a fresh CSRF token if needed
    test = session.get(f"{WEB_BASE}/event_periods/{_event_period_id_holder[0]}/check_ins")
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
            print(f"  ✓ Got CSRF token from live page")
        else:
            print("  ⚠ Could not find CSRF token — will try without it")

    print("  ✓ Session valid")
    return session


# ------------------------------
# API Helpers
# ------------------------------

def api_get(path, params=None):
    url = f"{API_BASE}{path}" if path.startswith("/") else path
    r = requests.get(url, auth=api_auth, params=params)
    r.raise_for_status()
    return r.json()


def get_all_pages(path, params=None):
    results = []
    url = f"{API_BASE}{path}"
    while url:
        body = api_get(url, params=params)
        results.extend(body["data"])
        url = body.get("links", {}).get("next")
        params = None
    return results


# ------------------------------
# Step 1 — Find the Group
# ------------------------------

def get_group_id(group_name):
    print(f"Looking up group: '{group_name}'...")
    groups = get_all_pages("/groups/v2/groups", params={"where[name]": group_name, "per_page": 25})
    for g in groups:
        if g["attributes"]["name"] == group_name:
            print(f"  Found group ID: {g['id']}")
            return g["id"]
    raise Exception(f"Group '{group_name}' not found")


# ------------------------------
# Step 2 — Get All Group Members
# ------------------------------

def get_group_members(group_id):
    print(f"Fetching members of group {group_id}...")

    # Fetch memberships with person sideloaded so we get first/last name
    all_memberships = []
    all_included = []
    url = f"{API_BASE}/groups/v2/groups/{group_id}/memberships"
    params = {"include": "person", "per_page": 100}
    while url:
        body = api_get(url, params=params)
        all_memberships.extend(body["data"])
        all_included.extend(body.get("included", []))
        url = body.get("links", {}).get("next")
        params = None

    # Build person lookup from included records
    person_lookup = {p["id"]: p["attributes"] for p in all_included if p["type"] == "Person"}

    members = []
    for m in all_memberships:
        person_rel = m.get("relationships", {}).get("person", {}).get("data")
        if not person_rel:
            continue
        person_id = person_rel["id"]
        attrs = person_lookup.get(person_id, {})
        members.append({
            "account_center_person_id": person_id,
            "first_name": attrs.get("first_name", ""),
            "last_name": attrs.get("last_name", ""),
        })

    print(f"  Found {len(members)} members.")
    return members


# ------------------------------
# Step 3 — Find the Event
# ------------------------------

def get_event_id(event_name):
    print(f"Looking up Check-Ins event: '{event_name}'...")
    events = get_all_pages("/check-ins/v2/events", params={"per_page": 100})
    for e in events:
        if e["attributes"]["name"] == event_name:
            print(f"  Found event ID: {e['id']}")
            return e["id"]
    raise Exception(f"Event '{event_name}' not found")


# ------------------------------
# Step 4 — Find Last Sunday's Event Period
# ------------------------------

def get_last_sunday_event_period(event_id):
    print("Finding last Sunday's event period...")
    today = datetime.now(timezone.utc).date()
    days_since_sunday = (today.weekday() + 1) % 7
    last_sunday = today - timedelta(days=days_since_sunday if days_since_sunday > 0 else 7)
    print(f"  Last Sunday: {last_sunday}")

    body = api_get(
        f"/check-ins/v2/events/{event_id}/event_periods",
        params={"order": "-created_at", "per_page": 10}
    )
    for ep in body["data"]:
        starts_at = ep["attributes"].get("starts_at", "")
        if starts_at:
            ep_date = datetime.fromisoformat(starts_at.replace("Z", "+00:00")).date()
            print(f"  Checking period {ep['id']} on {ep_date}")
            if ep_date == last_sunday:
                print(f"  ✓ Matched event period: {ep['id']}")
                return ep["id"]

    if body["data"]:
        ep = body["data"][0]
        print(f"  No exact match — using most recent: {ep['id']} ({ep['attributes'].get('starts_at')})")
        return ep["id"]

    raise Exception("No event periods found")


# ------------------------------
# Step 5 — Find the Event Time
# ------------------------------

def get_event_time_id(event_id, event_period_id):
    print(f"Fetching event time for period {event_period_id}...")
    event_times = get_all_pages(
        "/check-ins/v2/event_times",
        params={"where[event_id]": event_id, "per_page": 100}
    )
    for et in event_times:
        ep_rel = et.get("relationships", {}).get("event_period", {}).get("data", {})
        if ep_rel.get("id") == str(event_period_id):
            print(f"  Using event time: {et['id']}")
            return et["id"]
    if event_times:
        print(f"  No period match — using first event time: {event_times[0]['id']}")
        return event_times[0]["id"]
    raise Exception("No event times found")


# ------------------------------
# Step 6 — Find the Location
# ------------------------------

def get_location_id(event_id, location_name):
    print(f"Looking up location: '{location_name}'...")
    locations = get_all_pages(f"/check-ins/v2/events/{event_id}/locations", params={"per_page": 100})
    for loc in locations:
        if loc["attributes"]["name"] == location_name:
            print(f"  Found location ID: {loc['id']}")
            return loc["id"]
    raise Exception(f"Location '{location_name}' not found")


# ------------------------------
# Step 7 — Bulk Check-In via internal endpoint
# ------------------------------

def bulk_checkin(session, event_period_id, event_time_id, event_id, location_id, members):
    """
    POST to the internal bulk_check_ins endpoint used by the PCO web UI.
    Sends up to BATCH_SIZE people per request.
    Returns (success_count, duplicate_count, error_count).
    """
    url = f"{WEB_BASE}/event_periods/{event_period_id}/bulk_check_ins"
    total_success = 0
    total_dupes = 0
    total_errors = 0

    for i in range(0, len(members), BATCH_SIZE):
        batch = members[i:i + BATCH_SIZE]
        print(f"\n  Sending batch {i // BATCH_SIZE + 1} ({len(batch)} people)...")

        # Build form-encoded payload matching what the browser sends
        form_data = [("check-in-kind", "Regular")]
        for m in batch:
            prefix = "bulk_check_in[check_ins_attributes][]"
            form_data += [
                (f"{prefix}[first_name]",                                    m["first_name"]),
                (f"{prefix}[last_name]",                                     m["last_name"]),
                (f"{prefix}[account_center_person_id]",                      m["account_center_person_id"]),
                (f"{prefix}[check_in_times_attributes][][location_id]",      str(location_id)),
                (f"{prefix}[check_in_times_attributes][][event_time_id]",    str(event_time_id)),
                (f"{prefix}[check_in_times_attributes][][kind]",             "Regular"),
                (f"{prefix}[event_id]",                                      str(event_id)),
                (f"{prefix}[event_period_id]",                               str(event_period_id)),
            ]

        resp = session.post(url, data=form_data)

        if not resp.ok:
            print(f"  ✗ Batch failed ({resp.status_code}): {resp.text[:300]}")
            total_errors += len(batch)
            continue

        # Empty body = success (Content-Length: 0 is what the PCO UI gets back)
        if not resp.text.strip():
            print(f"  ✓ {len(batch)} submitted successfully")
            total_success += len(batch)
            continue

        # If we got HTML back, the session/CSRF was rejected
        if "text/html" in resp.headers.get("Content-Type", "") or resp.text.strip().startswith("<!DOCTYPE"):
            print(f"  ✗ Got HTML response — session or CSRF token may be expired")
            print(f"    Snippet: {resp.text[:150]}")
            total_errors += len(batch)
            continue

        try:
            result = resp.json()
            success = result.get("total", 0) - result.get("duplicate_count", 0)
            dupes   = result.get("duplicate_count", 0)
            total_success += success
            total_dupes   += dupes
            print(f"  ✓ {success} checked in, {dupes} duplicates skipped")
        except Exception:
            # Non-empty, non-HTML, non-JSON — treat as success
            print(f"  ✓ {len(batch)} submitted (response: {resp.text[:80]})")
            total_success += len(batch)

    return total_success, total_dupes, total_errors


# ------------------------------
# Main
# ------------------------------

def main():
    print("=" * 55)
    print("  Auto Check-In: 5th Grade Boys → Escuela Dominical")
    print("=" * 55)

    if not PCO_SESSION_COOKIE:
        raise Exception("PCO_SESSION_COOKIE must be set in .env — run the script once to see instructions.")

    # Discover all IDs via the public API
    group_id        = get_group_id(GROUP_NAME)
    members         = get_group_members(group_id)
    if not members:
        print("No members found — nothing to do.")
        return

    event_id        = get_event_id(EVENT_NAME)
    event_period_id = get_last_sunday_event_period(event_id)
    event_time_id   = get_event_time_id(event_id, event_period_id)
    location_id     = get_location_id(event_id, LOCATION_NAME)

    # Log in via the web to get a session capable of calling bulk_check_ins
    _event_period_id_holder[0] = event_period_id
    session = get_web_session()

    # Bulk check-in all members
    print(f"\nBulk checking in {len(members)} members in batches of {BATCH_SIZE}...")
    success, dupes, errors = bulk_checkin(
        session, event_period_id, event_time_id, event_id, location_id, members
    )

    print(f"\n{'=' * 55}")
    print(f"  Done! {success} checked in, {dupes} duplicates, {errors} errors.")
    print(f"{'=' * 55}")


if __name__ == "__main__":
    main()