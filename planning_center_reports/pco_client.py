# planning_center_reports/pco_client.py
#
# All communication with the Planning Center Online (PCO) API lives here.
# The public surface is four functions:
#   get_event_id               — resolve an event name to its PCO ID
#   get_recent_event_periods   — fetch the N most recent Sunday periods
#   get_checkins_for_event_periods — paginate through all check-ins for those periods
#   get_person_details         — fetch phone, address, birthday, grade for one person
#
# get_person_details is the hot path — it is called once per unique attendee and
# implements retry logic for rate-limits and network errors. Results are cached
# in _person_cache (keyed by person_id) so repeat calls within a single run are
# free.

import time

import requests
from requests.auth import HTTPBasicAuth

from planning_center_reports.config import BASE_URL, PCO_APP_ID, PCO_SECRET

# Build auth once at module load; HTTPBasicAuth with None values is safe to
# construct — it only causes a failure if an actual request is attempted without
# valid credentials.
_auth = HTTPBasicAuth(PCO_APP_ID, PCO_SECRET)

# Module-level cache: person_id → details dict. Shared across the whole run so
# a person who appears on multiple bus routes is only fetched once.
_person_cache: dict = {}

# PCO integer → display-string mapping for the grade field on People records.
GRADE_MAP = {
    -2: "Nursery", -1: "Pre-K", 0: "Kinder",
    1: "1°",  2: "2°",  3: "3°",  4: "4°",  5: "5°",  6: "6°",
    7: "7°",  8: "8°",  9: "9°", 10: "10°", 11: "11°", 12: "12°",
}


def get_event_id(event_name: str) -> str:
    """Return the PCO event ID for a named event.

    Raises an exception if the event name is not found — it is case-sensitive.
    """
    url      = f"{BASE_URL}/check-ins/v2/events"
    response = requests.get(url, auth=_auth)
    response.raise_for_status()
    for event in response.json()["data"]:
        if event["attributes"]["name"] == event_name:
            return event["id"]
    raise Exception(f"Event '{event_name}' not found")


def get_recent_event_periods(event_id: str, weeks: int = 5) -> list:
    """Return the IDs of the `weeks` most recent event periods for `event_id`."""
    url      = f"{BASE_URL}/check-ins/v2/events/{event_id}/event_periods"
    params   = {"order": "-created_at", "per_page": weeks}
    response = requests.get(url, auth=_auth, params=params)
    response.raise_for_status()
    data = response.json()["data"]
    if not data:
        raise Exception("No event periods found")
    print(f"  Using {len(data)} event period(s):", flush=True)
    for ep in data:
        print(f"    - {ep['id']} ({ep['attributes'].get('starts_at', 'unknown date')})", flush=True)
    return [ep["id"] for ep in data]


def get_checkins_for_event_periods(event_id: str, event_period_ids: list) -> tuple:
    """Paginate through all check-ins for the given event, keeping only those
    that belong to the specified event period IDs.

    Returns (checkins, included) where both are lists of PCO API objects.
    `included` contains sideloaded Location and Person records.
    """
    all_checkins, all_included = [], []
    valid_period_ids = set(event_period_ids)
    print(f"  Fetching all check-ins for event {event_id}...", flush=True)
    url    = f"{BASE_URL}/check-ins/v2/check_ins"
    params = {"where[event_id]": event_id, "include": "locations,person", "per_page": 100}
    page   = 1

    while url:
        print(f"    Page {page}...", flush=True)
        response = requests.get(url, auth=_auth, params=params)
        print(f"    Status: {response.status_code}", flush=True)
        response.raise_for_status()
        body  = response.json()
        batch = body["data"]
        kept  = 0
        for checkin in batch:
            ep_id = (checkin
                     .get("relationships", {})
                     .get("event_period", {})
                     .get("data", {})
                     .get("id"))
            if ep_id in valid_period_ids:
                all_checkins.append(checkin)
                kept += 1
        all_included.extend(body.get("included", []))
        print(f"    Got {len(batch)}, kept {kept}", flush=True)
        next_url = body.get("links", {}).get("next")
        # Guard against the API returning the same next URL (infinite loop).
        if next_url == url:
            break
        url    = next_url
        params = {}
        page  += 1

    print(f"  Total matching check-ins: {len(all_checkins)}", flush=True)
    return all_checkins, all_included


def get_person_details(person_id: str) -> dict:
    """Fetch phone, address, birthday, and grade for one PCO person.

    Results are cached by person_id. Retries up to 7 times on network errors
    and 429 rate-limit responses using exponential back-off.
    Returns an empty dict on permanent failure or 404.
    """
    if person_id in _person_cache:
        return _person_cache[person_id]

    url      = f"{BASE_URL}/people/v2/people/{person_id}"
    params   = {"include": "emails,phone_numbers,addresses"}
    max_retries = 7
    response    = None

    for attempt in range(max_retries):
        try:
            response = requests.get(url, auth=_auth, params=params, timeout=60)
        except (
            requests.exceptions.SSLError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
        ) as e:
            wait = 2 ** attempt
            print(f"  {type(e).__name__} — waiting {wait}s before retry ({attempt + 1}/{max_retries})...", flush=True)
            for remaining in range(wait, 0, -1):
                print(f"  Retrying in {remaining}s...  ", end="\r", flush=True)
                time.sleep(1)
            print("  Retrying now...                   ", flush=True)
            continue

        if response.status_code == 404:
            _person_cache[person_id] = {}
            return {}
        if response.status_code == 429:
            wait = 2 ** attempt
            for remaining in range(wait, 0, -1):
                print(f"  Rate limited — retrying in {remaining}s...  ", end="\r", flush=True)
                time.sleep(1)
            print("  Rate limit wait done, retrying...          ", flush=True)
            continue
        response.raise_for_status()
        break
    else:
        print(f"  Giving up on person {person_id} after {max_retries} retries.", flush=True)
        _person_cache[person_id] = {}
        return {}

    body         = response.json()
    person_attrs = body["data"]["attributes"]
    included     = body.get("included", [])

    phones    = [i for i in included if i["type"] == "PhoneNumber"]
    addresses = [i for i in included if i["type"] == "Address"]

    primary_phone = next(
        (p["attributes"]["number"] for p in phones if p["attributes"].get("primary")),
        phones[0]["attributes"]["number"] if phones else "",
    )

    primary_address = ""
    if addresses:
        addr  = next((a for a in addresses if a["attributes"].get("primary")), addresses[0])
        a     = addr["attributes"]
        parts = filter(None, [
            a.get("street_line_1"), a.get("street_line_2"),
            a.get("city"), a.get("state"), a.get("zip"),
        ])
        primary_address = ", ".join(parts)

    grade_raw = person_attrs.get("grade")
    grade     = GRADE_MAP.get(grade_raw, "") if grade_raw is not None else ""

    result = {
        "phone":      primary_phone,
        "address":    primary_address,
        "birthday":   person_attrs.get("birthdate") or "",
        "grade":      grade,
        "created_at": person_attrs.get("created_at") or "",
    }
    _person_cache[person_id] = result
    return result
