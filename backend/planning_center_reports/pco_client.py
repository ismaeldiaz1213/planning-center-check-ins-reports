# planning_center_reports/pco_client.py
#
# All communication with the Planning Center Online (PCO) API lives here.
# The public surface is five functions:
#   get_event_id               — resolve an event name to its PCO ID
#   get_recent_event_periods   — fetch the N most recent Sunday periods
#   get_checkins_for_event_periods — paginate through all check-ins for those periods
#   get_person_details         — fetch phone, address, birthday, grade for one person
#   get_helpers_set            — return set of person_ids (age 16+) from Junta de Rutas
#
# get_person_details is the hot path — it is called once per unique attendee and
# implements retry logic for rate-limits and network errors. Results are cached
# in _person_cache (keyed by person_id) so repeat calls within a single run are
# free.

import time
from datetime import date

import requests
from requests.auth import HTTPBasicAuth

from planning_center_reports.config import BASE_URL, PCO_APP_ID, PCO_SECRET

# Build auth once at module load; HTTPBasicAuth with None values is safe to
# construct — it only causes a failure if an actual request is attempted without
# valid credentials.
_auth = HTTPBasicAuth(PCO_APP_ID, PCO_SECRET)


class PaginationCircuitBreakerError(Exception):
    """Raised when a per-period page count exceeds _MAX_PAGES_PER_PERIOD.
    Not caught by get_helpers_set's broad except — propagates to abort the run."""

# Module-level cache: person_id → details dict. Shared across the whole run so
# a person who appears on multiple bus routes is only fetched once.
_person_cache: dict = {}

# Module-level cache: person_id → bool indicating if they are a helper.
# Populated by get_helpers_set() and reused across both Rutas and Escuela Dominical
# so we only fetch the helpers event once.
_helpers_cache: set = set()

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


def _format_period_date(starts_at: str) -> str:
    """Format a PCO starts_at ISO string to a short Spanish date label.

    "2025-04-06T00:00:00Z" → "Abr 6"
    """
    from datetime import datetime
    from planning_center_reports.config import MESES_ABREV
    if not starts_at:
        return ""
    try:
        dt = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
        return f"{MESES_ABREV.get(dt.month, '')} {dt.day}"
    except Exception:
        return starts_at[:10] if starts_at else ""


def get_recent_event_periods(event_id: str, weeks: int = 5) -> tuple:
    """Return (period_ids, period_dates, period_starts_at) for the `weeks` most recent periods.

    period_ids      — ordered list of PCO event period ID strings
    period_dates    — dict mapping period_id → short Spanish label (e.g. "Abr 6")
    period_starts_at — dict mapping period_id → raw ISO-8601 starts_at string;
                       used by _build_sunday_data to compute per-Sunday visitor status
    """
    url      = f"{BASE_URL}/check-ins/v2/events/{event_id}/event_periods"
    params   = {"order": "-created_at", "per_page": weeks}
    response = requests.get(url, auth=_auth, params=params)
    response.raise_for_status()
    data = response.json()["data"]
    if not data:
        raise Exception("No event periods found")
    print(f"  Using {len(data)} event period(s):", flush=True)
    period_ids       = []
    period_dates     = {}
    period_starts_at = {}
    for ep in data:
        pid       = ep["id"]
        starts_at = ep["attributes"].get("starts_at", "")
        print(f"    - {pid} ({starts_at})", flush=True)
        period_ids.append(pid)
        period_dates[pid]     = _format_period_date(starts_at)
        period_starts_at[pid] = starts_at
    return period_ids, period_dates, period_starts_at


def _fetch_checkins_page(url: str, params: dict, page: int) -> dict:
    """Fetch one page of check-ins with retry logic. Returns the parsed JSON body."""
    max_retries = 7
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
            time.sleep(wait)
            continue
        if response.status_code == 429:
            wait = 2 ** attempt
            for remaining in range(wait, 0, -1):
                print(f"  Rate limited — retrying in {remaining}s...  ", end="\r", flush=True)
                time.sleep(1)
            print("  Rate limit wait done, retrying...          ", flush=True)
            continue
        if not response.ok:
            print(
                f"\n  HTTP {response.status_code} fetching page {page}: {response.text[:200]}",
                flush=True,
            )
            response.raise_for_status()
        return response.json()
    raise Exception(f"Failed to fetch check-ins page {page} after {max_retries} retries.")


_MAX_PAGES_PER_PERIOD = 30  # circuit breaker — a single period should never exceed ~3000 check-ins


def get_checkins_for_event_periods(event_id: str, event_period_ids: list) -> tuple:
    """Fetch check-ins for each event period individually.

    Uses the nested /events/{event_id}/event_periods/{period_id}/check_ins endpoint
    so PCO scopes results to exactly that period. This keeps page count proportional
    to attendance size, not to the event's full history.

    Returns (checkins, included) where both are lists of PCO API objects.
    `included` contains sideloaded Location and Person records.
    """
    all_checkins: list = []
    all_included: list = []

    for period_id in event_period_ids:
        print(f"  Fetching check-ins for period {period_id}...", flush=True)
        url    = f"{BASE_URL}/check-ins/v2/events/{event_id}/event_periods/{period_id}/check_ins"
        params = {"include": "locations,person", "per_page": 100}
        page   = 1

        while url:
            if page > _MAX_PAGES_PER_PERIOD:
                raise PaginationCircuitBreakerError(
                    f"Period {period_id} exceeded {_MAX_PAGES_PER_PERIOD} pages — "
                    "the PCO filter may not be working. Aborting to avoid runaway fetching."
                )
            body     = _fetch_checkins_page(url, params, page)
            batch    = body["data"]
            all_checkins.extend(batch)
            all_included.extend(body.get("included", []))
            print(f"    Period {period_id} — page {page}: {len(batch)} check-ins", flush=True)
            next_url = body.get("links", {}).get("next")
            if not next_url or next_url == url:
                break
            url    = next_url
            params = {}
            page  += 1

    print(f"  Total check-ins: {len(all_checkins)}", flush=True)
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


def get_helpers_set(weeks: int = 5) -> set:
    """Return the set of person_ids (age 16+) who checked into the
    'Junta de Rutas Attendance' event in the last `weeks` weeks.

    Results are cached in _helpers_cache so multiple calls within a run
    only fetch the event once.
    """
    if _helpers_cache:
        return _helpers_cache

    print("  Fetching helpers (Junta de Rutas Attendance)...", flush=True)
    try:
        event_id = get_event_id("Junta de Rutas Attendance")
    except Exception as e:
        print(f"  ⚠ Could not find 'Junta de Rutas Attendance' event: {e}", flush=True)
        return set()

    try:
        event_period_ids, _, _ = get_recent_event_periods(event_id, weeks=weeks)
    except Exception as e:
        print(f"  ⚠ Could not fetch helpers event periods: {e}", flush=True)
        return set()

    try:
        checkins, included = get_checkins_for_event_periods(event_id, event_period_ids)
    except PaginationCircuitBreakerError:
        raise
    except Exception as e:
        print(f"  ⚠ Could not fetch helpers check-ins: {e}", flush=True)
        return set()

    # Collect all unique person_ids from the helpers event
    candidates = set()
    for checkin in checkins:
        person_rel = checkin["relationships"].get("person", {}).get("data")
        person_id = person_rel["id"] if person_rel else None
        if person_id:
            candidates.add(person_id)

    # Filter by age 16+ — fetch each candidate's birthday and check age
    def _age_from_birthday_iso(birthday_raw: str) -> int:
        """Compute age from ISO-8601 birthday string. Return 0 if invalid."""
        import re
        if not birthday_raw:
            return 0
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", birthday_raw.strip())
        if not m:
            return 0
        try:
            dob = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            today = date.today()
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        except ValueError:
            return 0

    helpers = set()
    for i, person_id in enumerate(candidates, 1):
        details = get_person_details(person_id)
        birthday = details.get("birthday", "")
        age = _age_from_birthday_iso(birthday)
        if age >= 16:
            helpers.add(person_id)
            print(f"    [{i}/{len(candidates)}] Helper: {person_id} (age {age})", flush=True)
        else:
            print(f"    [{i}/{len(candidates)}] Not helper: {person_id} (age {age})", flush=True)

    _helpers_cache.update(helpers)
    print(f"  Found {len(helpers)} helpers.", flush=True)
    return _helpers_cache
