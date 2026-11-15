# planning_center_reports/pco_client.py
#
# All communication with the Planning Center Online (PCO) API lives here.
#
# PcoClient is one church's connection: its credentials, its request pacing, its
# request counter and its caches. Nothing is shared between two clients, so two
# churches can be served by one process without seeing each other's data or
# using up each other's rate limit.
#
#   client.get_event_id               — resolve an event name to its PCO ID
#   client.get_event_periods_since    — every past Sunday period on or after a start date
#   client.get_recent_event_periods   — the N most recent past periods (used by the scripts)
#   client.get_checkins_for_event_periods — paginate through all check-ins for those periods
#   client.get_guardians              — parents of a list of children (two batched passes)
#   client.get_person_details         — one person from the People API (scripts only)
#   client.get_locations / get_location_id / get_event_times — lookups for the scripts
#
# Pure helpers that need no connection stay module-level:
#   person_details     — phone/address/birthday/grade from a sideloaded Person
#   age_from_birthday  — age in years from an ISO-8601 birthday string
#
# The roster pipeline never calls the People API per person: check-ins are fetched
# with include=person, and the Check-Ins Person already carries phone numbers,
# addresses, birthdate, grade, gender and created_at. That keeps a whole-school-
# year run to a few hundred requests.
#
# Every request goes through PcoClient._get(), which paces calls under PCO's
# limit of 100 requests per 20 seconds, honours Retry-After on 429, refreshes an
# expired OAuth token once, and retries network errors with exponential back-off.

import re
import time
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime

import requests
from requests.auth import HTTPBasicAuth

from planning_center_reports.config import BASE_URL


class PaginationCircuitBreakerError(Exception):
    """Raised when a per-period page count exceeds _MAX_PAGES_PER_PERIOD.
    Propagates to abort the run rather than generate rosters from partial data."""


# ── Authentication ────────────────────────────────────────────────────────────

class PersonalAccessToken:
    """A Planning Center Personal Access Token (application id + secret), sent as
    HTTP Basic auth. This is how IBL's original job signs in."""

    def __init__(self, app_id: str | None, secret: str | None):
        # HTTPBasicAuth with None values is safe to construct — it only fails
        # when a request is actually sent without valid credentials.
        self._auth = HTTPBasicAuth(app_id, secret)

    def request_kwargs(self) -> dict:
        return {"auth": self._auth}

    def refresh(self) -> bool:
        return False        # a rejected token cannot be renewed


class OAuthBearer:
    """An OAuth access token, sent as "Authorization: Bearer …".

    `refresh` is called when Planning Center answers 401 (the access token
    expired). It must return a new access token, or raise if the church has to
    reconnect. The client retries the request once with the new token.
    """

    def __init__(self, access_token: str, refresh: Callable[[], str] | None = None):
        self._token = access_token
        self._refresh = refresh

    def request_kwargs(self) -> dict:
        return {"headers": {"Authorization": f"Bearer {self._token}"}}

    def refresh(self) -> bool:
        if self._refresh is None:
            return False
        self._token = self._refresh()
        return True


# ── Request statistics ────────────────────────────────────────────────────────

@dataclass
class RequestStats:
    """What a run cost in Planning Center API traffic (docs/benchmarks.md).

    Counts every attempt that reached the network, so a request retried twice
    counts three times — that is what Planning Center's rate limit sees.
    """
    requests:        int = 0      # HTTP attempts sent
    network_retries: int = 0      # attempts that failed with a network error
    rate_limited:    int = 0      # 429 responses from Planning Center
    token_refreshes: int = 0      # 401s answered by refreshing the OAuth token
    http_s:          float = 0.0  # time spent waiting for responses
    throttle_wait_s: float = 0.0  # time we paused to stay under our own 80 / 20 s pace
    backoff_wait_s:  float = 0.0  # time we paused after a 429 or network error

    def reset(self) -> None:
        self.__init__()

    def as_dict(self) -> dict:
        return {k: round(v, 3) if isinstance(v, float) else v for k, v in asdict(self).items()}

    def summary(self) -> str:
        return (f"Planning Center requests: {self.requests} "
                f"({self.network_retries} network retries, {self.rate_limited} rate-limited) · "
                f"{self.http_s:.1f}s waiting for responses · "
                f"{self.throttle_wait_s + self.backoff_wait_s:.1f}s paused for the rate limit")


_NETWORK_ERRORS = (
    requests.exceptions.SSLError,
    requests.exceptions.ReadTimeout,
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
)

_MAX_PAGES_PER_PERIOD = 30  # circuit breaker — a single period should never exceed ~3000 check-ins
_PEOPLE_BATCH = 100         # ids per where[id]= request — keeps URLs well under limits

def _retry_after(response) -> int | None:
    """Seconds PCO asked us to wait, from the Retry-After header, if present."""
    raw = (getattr(response, "headers", None) or {}).get("Retry-After")
    try:
        return max(1, int(float(raw)))
    except (TypeError, ValueError):
        return None


# PCO integer → display-string mapping for the grade field on People records.
GRADE_MAP = {
    -2: "Nursery", -1: "Pre-K", 0: "Kinder",
    1: "1°",  2: "2°",  3: "3°",  4: "4°",  5: "5°",  6: "6°",
    7: "7°",  8: "8°",  9: "9°", 10: "10°", 11: "11°", 12: "12°",
}


def age_from_birthday(birthday_raw: str) -> int:
    """Compute age in years from an ISO-8601 birthday string. Returns 0 if invalid/empty."""
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


def _format_period_date(starts_at: str) -> str:
    """Format a PCO starts_at ISO string to a short Spanish date label.

    "2025-04-06T00:00:00Z" → "Abr 6"
    """
    from datetime import datetime

    # Only the IBL maintenance scripts print these labels, so Spanish is fixed here.
    from planning_center_reports.i18n.es import MONTHS_ABBR as MESES_ABREV
    if not starts_at:
        return ""
    try:
        dt = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
        return f"{MESES_ABREV.get(dt.month, '')} {dt.day}"
    except Exception:
        return starts_at[:10] if starts_at else ""


def _parse_ts(raw: str) -> datetime | None:
    """Parse a PCO ISO-8601 timestamp into an aware UTC datetime."""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def _primary(items: list) -> dict | None:
    """Return the primary entry of a PCO contact list, else the first, else None."""
    if not items:
        return None
    return next((i for i in items if i.get("primary")), items[0])


def _format_address(a: dict) -> str:
    parts = filter(None, [
        a.get("street_line_1") or a.get("street"), a.get("street_line_2"),
        a.get("city"), a.get("state"), a.get("zip"),
    ])
    return ", ".join(parts)


def person_details(attrs: dict) -> dict:
    """Build the roster details for one Check-Ins Person (an `included` record's
    attributes). No request is made — check-ins sideload all of this.
    """
    phone   = _primary(attrs.get("phone_numbers") or [])
    address = _primary(attrs.get("addresses") or [])
    grade_raw = attrs.get("grade")
    return {
        "phone":      phone.get("number", "") if phone else "",
        "address":    _format_address(address) if address else "",
        "birthday":   attrs.get("birthdate") or "",
        "grade":      GRADE_MAP.get(grade_raw, "") if grade_raw is not None else "",
        "grade_num":  grade_raw,
        "gender":     attrs.get("gender") or "",
        "created_at": attrs.get("created_at") or "",
    }


def _related_ids(record: dict, rel: str) -> list[str]:
    return [r["id"] for r in (record.get("relationships", {}).get(rel, {}).get("data") or [])]


def _is_adult(attrs: dict) -> bool:
    """True for a People record that is not flagged as a child and, when a
    birthdate is known, is at least 18."""
    if attrs.get("child"):
        return False
    birthdate = attrs.get("birthdate") or ""
    return not birthdate or age_from_birthday(birthdate) >= 18


# ── The client ────────────────────────────────────────────────────────────────

class PcoClient:
    """One church's connection to Planning Center."""

    def __init__(self, auth, *, base_url: str = BASE_URL, rate_max: int = 80,
                 rate_window_s: float = 20.0, max_retries: int = 7):
        self.auth = auth
        self.base_url = base_url
        # PCO allows 100 requests per rolling 20 s per app. Staying at 80 leaves
        # room for anyone else using the same credentials at the same moment.
        self.rate_max = rate_max
        self.rate_window_s = rate_window_s
        self.max_retries = max_retries
        self.stats = RequestStats()
        self._request_times: deque = deque()
        # person_id → details, so the scripts fetch each person once per run.
        self._person_cache: dict = {}

    # ── Request pacing ────────────────────────────────────────────────────────

    def _throttle(self) -> None:
        """Block until one more request fits in the rolling rate window."""
        times = self._request_times
        now = time.monotonic()
        while times and now - times[0] >= self.rate_window_s:
            times.popleft()
        if len(times) >= self.rate_max:
            wait = self.rate_window_s - (now - times[0])
            if wait > 0:
                self.stats.throttle_wait_s += wait
                time.sleep(wait)
            times.popleft()
        times.append(time.monotonic())

    def _get(self, url: str, params: dict | None = None, label: str = "request"):
        """GET with pacing, 429 handling, one token refresh and network retries.

        Returns the final Response (which may still be a non-2xx error the caller
        handles), or None when every attempt failed with a network error.
        """
        stats = self.stats
        refreshed = False
        for attempt in range(self.max_retries):
            self._throttle()
            stats.requests += 1
            sent = time.perf_counter()
            try:
                response = requests.get(url, params=params, timeout=60, **self.auth.request_kwargs())
            except _NETWORK_ERRORS as e:
                stats.http_s += time.perf_counter() - sent
                stats.network_retries += 1
                wait = 2 ** attempt
                print(f"  {type(e).__name__} on {label} — retrying in {wait}s "
                      f"({attempt + 1}/{self.max_retries})...", flush=True)
                stats.backoff_wait_s += wait
                time.sleep(wait)
                continue
            stats.http_s += time.perf_counter() - sent
            if response.status_code == 429:
                stats.rate_limited += 1
                wait = _retry_after(response) or 2 ** attempt
                print(f"  Rate limited by PCO on {label} — waiting {wait}s...", flush=True)
                stats.backoff_wait_s += wait
                time.sleep(wait)
                continue
            if response.status_code == 401 and not refreshed and self.auth.refresh():
                refreshed = True
                stats.token_refreshes += 1
                continue
            return response
        return None

    # ── Check-Ins and People ──────────────────────────────────────────────────

    def get_event_id(self, event_name: str) -> str:
        """Return the PCO event ID for a named event.

        Raises an exception if the event name is not found — it is case-sensitive.
        Follows pagination: PCO returns 25 events per page by default, and archived
        events stay in the list, so newer events can sit past the first page.
        """
        url    = f"{self.base_url}/check-ins/v2/events"
        params = {"per_page": 100}
        while url:
            response = self._get(url, params, label="event lookup")
            if response is None:
                raise Exception("Could not reach Planning Center to look up events")
            response.raise_for_status()
            body = response.json()
            for event in body["data"]:
                if event["attributes"]["name"] == event_name:
                    return event["id"]
            url    = body.get("links", {}).get("next")
            params = None  # the "next" link already carries per_page/offset
        raise Exception(f"Event '{event_name}' not found")

    def get_recent_event_periods(self, event_id: str, weeks: int = 5) -> tuple:
        """Return (period_ids, period_dates, period_starts_at) for the `weeks` most recent
        periods that have already happened (starts_at in the past).

        period_ids      — ordered list of PCO event period ID strings, most recent first
        period_dates    — dict mapping period_id → short Spanish label (e.g. "Abr 6")
        period_starts_at — dict mapping period_id → raw ISO-8601 starts_at string;
                           used by _build_sunday_data to compute per-Sunday visitor status

        Ordered and filtered by `starts_at`, not `created_at` — PCO can create recurring
        event periods ahead of schedule, so the most-recently-created period is not
        reliably the most recent Sunday, and may even be a future one.
        """
        url      = f"{self.base_url}/check-ins/v2/events/{event_id}/event_periods"
        params   = {"order": "-starts_at", "per_page": 100}
        response = self._get(url, params, label="event periods")
        if response is None:
            raise Exception("Could not reach Planning Center to list event periods")
        response.raise_for_status()
        now  = datetime.now(UTC)
        data = []
        for ep in response.json()["data"]:
            starts_at = ep["attributes"].get("starts_at", "")
            try:
                starts_at_dt = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            if starts_at_dt <= now:
                data.append(ep)
            if len(data) >= weeks:
                break
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

    def get_event_periods_since(self, event_id: str, since: date, tz=UTC,
                                max_periods: int = 52) -> list[dict]:
        """Return every period of `event_id` that has already started and falls on
        or after `since` (compared as a local date in `tz`), oldest first.

        Each item is {"id", "starts_at"} with starts_at as an aware datetime.
        At most `max_periods` (the most recent ones) are returned, as a safety cap.
        """
        url    = f"{self.base_url}/check-ins/v2/events/{event_id}/event_periods"
        params = {"order": "-starts_at", "per_page": 100}
        now    = datetime.now(UTC)
        found: list[dict] = []
        while url and len(found) < max_periods:
            response = self._get(url, params, label="event periods")
            if response is None:
                raise Exception("Could not reach Planning Center to list event periods")
            response.raise_for_status()
            body  = response.json()
            older = False
            for ep in body["data"]:
                starts = _parse_ts(ep["attributes"].get("starts_at", ""))
                if starts is None or starts > now:
                    continue
                if starts.astimezone(tz).date() < since:
                    older = True
                    break
                found.append({"id": ep["id"], "starts_at": starts})
                if len(found) >= max_periods:
                    break
            if older:
                break
            url    = body.get("links", {}).get("next")
            params = None
        found.sort(key=lambda p: p["starts_at"])
        return found

    def _fetch_checkins_page(self, url: str, params: dict, page: int) -> dict:
        """Fetch one page of check-ins with retry logic. Returns the parsed JSON body."""
        response = self._get(url, params, label=f"check-ins page {page}")
        if response is None:
            raise Exception(f"Failed to fetch check-ins page {page} after {self.max_retries} retries.")
        if not response.ok:
            print(
                f"\n  HTTP {response.status_code} fetching page {page}: {response.text[:200]}",
                flush=True,
            )
            response.raise_for_status()
        return response.json()

    def get_checkins_for_event_periods(self, event_id: str, event_period_ids: list) -> tuple:
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
            url    = f"{self.base_url}/check-ins/v2/events/{event_id}/event_periods/{period_id}/check_ins"
            params = {"include": "locations,person", "per_page": 100}
            page   = 1

            while url:
                if page > _MAX_PAGES_PER_PERIOD:
                    raise PaginationCircuitBreakerError(
                        f"Period {period_id} exceeded {_MAX_PAGES_PER_PERIOD} pages — "
                        "the PCO filter may not be working. Aborting to avoid runaway fetching."
                    )
                body     = self._fetch_checkins_page(url, params, page)
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

    def get_person_details(self, person_id: str) -> dict:
        """Fetch phone, address, birthday, and grade for one PCO person from the
        People API. Used by the maintenance scripts; the roster pipeline reads the
        same fields from sideloaded check-in data instead (see person_details).

        Results are cached by person_id. Returns an empty dict on permanent failure or 404.
        """
        if person_id in self._person_cache:
            return self._person_cache[person_id]

        url      = f"{self.base_url}/people/v2/people/{person_id}"
        params   = {"include": "emails,phone_numbers,addresses"}
        response = self._get(url, params, label=f"person {person_id}")
        if response is None:
            print(f"  Giving up on person {person_id} after {self.max_retries} retries.", flush=True)
            self._person_cache[person_id] = {}
            return {}
        if response.status_code == 404:
            self._person_cache[person_id] = {}
            return {}
        response.raise_for_status()

        body         = response.json()
        person_attrs = body["data"]["attributes"]
        included     = body.get("included", [])

        phones    = [i["attributes"] for i in included if i["type"] == "PhoneNumber"]
        addresses = [i["attributes"] for i in included if i["type"] == "Address"]

        result = person_details({
            **person_attrs,
            "phone_numbers": phones,
            "addresses":     addresses,
        })
        self._person_cache[person_id] = result
        return result

    def _people_batch(self, ids: list[str], include: str) -> tuple[list, list]:
        """Fetch People API records for `ids`, 100 per request.

        PCO filters /people/v2/people by a comma-separated where[id] list, so a few
        requests cover a whole roster. Returns (data, included) across all batches.
        """
        data: list = []
        included: list = []
        unique = list(dict.fromkeys(i for i in ids if i))
        for start in range(0, len(unique), _PEOPLE_BATCH):
            chunk  = unique[start:start + _PEOPLE_BATCH]
            url    = f"{self.base_url}/people/v2/people"
            params = {"where[id]": ",".join(chunk), "per_page": _PEOPLE_BATCH, "include": include}
            while url:
                response = self._get(url, params, label="people batch")
                if response is None:
                    raise Exception("Could not reach Planning Center People")
                response.raise_for_status()
                body = response.json()
                data.extend(body.get("data", []))
                included.extend(body.get("included", []))
                url    = body.get("links", {}).get("next")
                params = None
        return data, included

    def get_guardians(self, child_ids: list[str]) -> dict[str, dict]:
        """Return {child_id: {"name", "phone", "address"}} for each child's parent.

        The parent is the primary contact of the child's PCO household — the same
        person Planning Center prints as "[P]" on its own roster reports. Two
        batched passes: children → households, then primary contacts → phone and
        address.

        Only adults count. When parents don't attend, PCO sometimes makes an older
        sibling the household's primary contact — that child is never shown as a
        parent. Children with no adult primary contact are omitted.
        """
        if not child_ids:
            return {}

        kids, kid_included = self._people_batch(child_ids, "households")
        households = {i["id"]: i["attributes"] for i in kid_included if i["type"] == "Household"}

        contact_for: dict[str, tuple[str, str]] = {}   # child → (contact id, contact name)
        for kid in kids:
            for hid in _related_ids(kid, "households"):
                h   = households.get(hid) or {}
                cid = str(h.get("primary_contact_id") or "")
                if cid and cid != kid["id"]:
                    contact_for[kid["id"]] = (cid, h.get("primary_contact_name") or "")
                    break

        contacts, contact_included = self._people_batch(
            [cid for cid, _ in contact_for.values()], "phone_numbers,addresses"
        )
        by_type_id = {(i["type"], i["id"]): i["attributes"] for i in contact_included}
        details: dict[str, dict] = {}
        for person in contacts:
            attrs = person["attributes"]
            if not _is_adult(attrs):
                continue
            details[person["id"]] = person_details({
                **attrs,
                "phone_numbers": [by_type_id[("PhoneNumber", i)] for i in _related_ids(person, "phone_numbers")
                                  if ("PhoneNumber", i) in by_type_id],
                "addresses":     [by_type_id[("Address", i)] for i in _related_ids(person, "addresses")
                                  if ("Address", i) in by_type_id],
            }) | {"name": attrs.get("name") or ""}

        guardians: dict[str, dict] = {}
        for kid_id, (cid, cname) in contact_for.items():
            d = details.get(cid)
            if d is None:          # a child, or not returned by PCO
                continue
            guardians[kid_id] = {
                "name":    d.get("name") or cname,
                "phone":   d.get("phone", ""),
                "address": d.get("address", ""),
            }
        return guardians

    def get_locations(self, event_id: str) -> list:
        """Return [{'id', 'name'}, ...] for every Check-Ins location under `event_id`.

        Locations belong to the event (not a specific period), so this covers every period.
        """
        url      = f"{self.base_url}/check-ins/v2/events/{event_id}/locations"
        response = self._get(url, {"per_page": 100}, label="locations")
        if response is None:
            raise Exception("Could not reach Planning Center to list locations")
        response.raise_for_status()
        return [
            {"id": loc["id"], "name": loc["attributes"]["name"]}
            for loc in response.json()["data"]
        ]

    def get_location_id(self, event_id: str, location_name: str) -> str:
        """Return the PCO location ID for a named Check-Ins location under `event_id`.

        Raises an exception if the name is not found — it is case-sensitive.
        """
        for loc in self.get_locations(event_id):
            if loc["name"] == location_name:
                return loc["id"]
        raise Exception(f"Location '{location_name}' not found on event {event_id}")

    def get_event_times(self, event_id: str, event_period_id: str) -> list:
        """Return [{'id', 'hour', 'minute', 'name'}, ...] for every event_time under
        `event_period_id`. A period can have more than one service time (e.g. 8am and
        10am) — bulk check-in submissions require picking the right one alongside the
        period and location IDs.
        """
        url      = f"{self.base_url}/check-ins/v2/event_times"
        response = self._get(url, {"where[event_id]": event_id, "per_page": 100}, label="event times")
        if response is None:
            raise Exception("Could not reach Planning Center to list event times")
        response.raise_for_status()
        times = []
        for et in response.json()["data"]:
            ep_rel = et.get("relationships", {}).get("event_period", {}).get("data") or {}
            if ep_rel.get("id") == str(event_period_id):
                attrs = et["attributes"]
                times.append({
                    "id":     et["id"],
                    "hour":   attrs.get("hour"),
                    "minute": attrs.get("minute"),
                    "name":   attrs.get("name", ""),
                })
        return times
