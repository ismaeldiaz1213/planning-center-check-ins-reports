# tests/golden/fake_pco.py
#
# A small, fully deterministic stand-in for the Planning Center API, served at
# the HTTP layer (it replaces requests.get). The golden pipeline tests run the
# real engine against it, so client code, pagination, roster building, parent
# lookups and PDF rendering are all covered by one snapshot.
#
# Everyone here is invented. The JSON shapes are inferred from what the engine
# reads (pco_client.py, roster_data.py); they were NOT recorded from the live
# API, so this proves "the engine still behaves the same", not "this is exactly
# what Planning Center returns".
#
# The church it models looks like IBL: a bus ministry event (Rutas), Sunday
# school, a second Sunday school session ("C"), and a workers' meeting (Junta).
# Sundays are indexed w = 0 (oldest, 2026-05-31) … 19 (latest, 2026-10-11).

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit

BASE = "https://api.planningcenteronline.com"
WEEKS = 20
LAST_SUNDAY = date(2026, 10, 11)
SUNDAYS = [LAST_SUNDAY - timedelta(weeks=WEEKS - 1 - w) for w in range(WEEKS)]

# The fake returns smaller pages than asked for, so every "next" link is followed.
PAGE_SIZE = {"events": 4, "event_periods": 10, "check_ins": 10, "people": 100}

EV_RUTAS, EV_ESCUELA, EV_C, EV_JUNTA = "1001", "1002", "1003", "1004"

# Order matters: the events the reports need are spread over several pages.
EVENTS = [
    ("1900", "VBS 2025"),
    ("1901", "Campamento de Jóvenes"),
    (EV_RUTAS, "Rutas"),
    ("1902", "Miércoles"),
    (EV_ESCUELA, "Escuela Dominical"),
    ("1903", "Conferencia Misionera"),
    (EV_JUNTA, "Junta de Rutas Attendance"),
    ("1904", "Escuela Dominical (archivo 2024)"),
    (EV_C, '"C" Escuela Dominical'),
]

# event → (UTC hour, minute) its Sunday period starts
EVENT_START = {EV_RUTAS: (13, 0), EV_ESCUELA: (15, 0), EV_C: (15, 45), EV_JUNTA: (12, 30)}

LOCATIONS = {
    "r1": "Ruta 1 - Bus", "r2": "Ruta 2 - Van", "r3": "Ruta 3 - Carro",
    "rw": "Chofer, Capitanes, Ayudantes",
    "nur": "Nursery", "kin": "Kinder Niños", "g3": "3rd Grade Girls", "par": "Clase de Parejas",
    "c7": '"C" 7th Boys', "c8": '"C" 8th Girls', "cth": "Teachers and Helpers",
    "jun": "Junta",
}
ROUTES = ["r1", "r2", "r3"]

# A Sunday when Sunday school was cancelled: the period exists, nobody checked in.
CANCELLED_ESCUELA_WEEK = 15

FIRST = ["Abril", "Benito", "Celia", "Dario", "Elena", "Fabio", "Gala", "Hugo", "Irene", "Joel",
         "Karla", "Leo", "Mara", "Nico", "Olga", "Pablo", "Quetzal", "Rosa", "Saul", "Tina"]
LAST = ["Alcaraz", "Benavides", "Cordero", "Duarte", "Escobar", "Fonseca", "Galindo",
        "Herrera", "Ibarra", "Jurado", "Lozano"]


def _birthdate(age: int, i: int) -> str:
    """A birthdate that makes the person `age` on the frozen day (2026-10-12)."""
    if i % 2:   # birthday still to come this year
        return date(2026 - age - 1, 11 + i % 2, 1 + i % 27).isoformat()
    return date(2026 - age, 1 + i % 9, 1 + i % 27).isoformat()


class FakePCO:
    """Builds the dataset once and answers GET requests against it."""

    def __init__(self):
        self.people: dict[str, dict] = {}        # Check-Ins Person attributes
        self.people_api: dict[str, dict] = {}    # People API records (kids + parents)
        self.households: dict[str, dict] = {}
        self.checkins: dict[tuple[str, int], list[dict]] = {}   # (event, week) → check-ins
        self.requests: list[str] = []
        self._seq = 0
        self._build()

    # ── dataset ───────────────────────────────────────────────────────────────

    def _person(self, pid: str, i: int, first: str, last: str, age: int | None, *,
                child: bool, grade: int | None = None, gender: str = "") -> None:
        phones = [] if i % 7 == 3 else [
            {"number": "(832) 555-0199", "primary": False},
            {"number": f"(832) 555-01{i % 100:02d}", "primary": True},
        ]
        if i % 9 == 4:
            addresses = []
        elif i % 11 == 5:
            addresses = [{"street_line_1": None, "city": "Houston", "state": "TX", "zip": None,
                          "primary": True}]
        else:
            addresses = [{
                "street_line_1": f"{100 + i * 3} Calle Falsa",
                "street_line_2": f"Apt {i}" if i % 4 == 0 else None,
                "city": "Houston", "state": "TX", "zip": "77000", "primary": True,
            }]
        self.people[pid] = {
            "first_name": first, "last_name": last, "name": f"{first} {last}",
            "child": child,
            "birthdate": None if (age is None or i % 8 == 6) else _birthdate(age, i),
            "grade": grade, "gender": gender,
            "created_at": "2024-01-15T16:00:00Z",
            "phone_numbers": phones, "addresses": addresses,
        }

    def _checkin(self, event: str, w: int, pid: str, loc: str, kind: str = "Regular",
                 offset_min: int = 0) -> None:
        self._seq += 1
        hour, minute = EVENT_START[event]
        start = datetime.combine(SUNDAYS[w], datetime.min.time(), tzinfo=UTC).replace(
            hour=hour, minute=minute)
        person = self.people[pid]
        self.checkins.setdefault((event, w), []).append({
            "type": "CheckIn", "id": f"ci{self._seq}",
            "attributes": {
                "first_name": person["first_name"], "last_name": person["last_name"],
                "kind": kind,
                "created_at": (start + timedelta(minutes=offset_min)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "relationships": {
                "locations":    {"data": [{"type": "Location", "id": loc}]},
                "person":       {"data": {"type": "Person", "id": pid}},
                "event_period": {"data": {"type": "EventPeriod", "id": f"{event}-{w:02d}"}},
                "event_times":  {"data": []},
            },
        })

    @staticmethod
    def _weeks(i: int) -> tuple[list[int], str]:
        """The Sundays person `i` attended, by one of eight fixed patterns."""
        regular = [w for w in range(WEEKS) if (i + w) % 6]
        pattern = i % 8
        if pattern == 3:
            return [w for w in range(WEEKS) if (i + w) % 3 == 0], "sporadic"
        if pattern == 4:
            return [w for w in regular if w <= 13], "lapsed"
        if pattern == 5:
            return ([19], "new") if i % 16 == 5 else ([17, 18, 19], "recent")
        if pattern == 6:
            return regular, "moved"
        if pattern == 7:
            return regular, "double"
        return regular, "regular"

    def _build(self) -> None:
        # ── Kids: (class location, other class in the same event, age, grade, event)
        classes = [
            ("nur", "kin", 1, None, EV_ESCUELA, 5),
            ("kin", "nur", 5, 0, EV_ESCUELA, 7),
            ("g3", "kin", 8, 3, EV_ESCUELA, 10),
            ("c7", "c8", 12, 7, EV_C, 6),
            ("c8", "c7", 13, 8, EV_C, 5),
        ]
        i = 0
        kids: list[tuple[str, int]] = []
        for home, other, age, grade, event, count in classes:
            for _ in range(count):
                pid = f"k{i:02d}"
                self._person(pid, i, FIRST[i % len(FIRST)], LAST[(i * 3) % len(LAST)],
                             age + i % 2, child=True,
                             grade=None if i % 5 == 2 else grade,
                             gender="F" if home in ("g3", "c8") else "M")
                weeks, pattern = self._weeks(i)
                kind = "Guest" if pattern == "new" else "Regular"
                for w in weeks:
                    offset = (i * 7 + w * 3) % 50 - 30
                    if not (event == EV_ESCUELA and w == CANCELLED_ESCUELA_WEEK):
                        loc = other if (pattern == "moved" and w < 16) else home
                        if pattern == "double" and w == 18:
                            # Checked into the wrong room first, then the right one.
                            self._checkin(event, w, pid, other, kind, offset - 5)
                        self._checkin(event, w, pid, loc, kind, offset)
                    # Two out of three kids ride a bus; a few change route mid-year.
                    if i % 3:
                        route = ROUTES[i % 3]
                        if i % 10 == 7 and w < 15:
                            route = ROUTES[(i + 1) % 3]
                        self._checkin(EV_RUTAS, w, pid, route, kind, offset - 60)
                kids.append((pid, i))
                i += 1

        # ── Adults in a Sunday school class (never get a parent line)
        for n in range(6):
            pid = f"a{n}"
            self._person(pid, 40 + n, FIRST[(n + 11) % len(FIRST)], LAST[(n * 2 + 1) % len(LAST)],
                         None if n == 4 else 34 + n * 3, child=False)
            for w in self._weeks(40 + n)[0]:
                if w != CANCELLED_ESCUELA_WEEK:
                    self._checkin(EV_ESCUELA, w, pid, "par", "Regular", n * 4 - 10)
                if n in (0, 1):        # two couples ride the bus
                    self._checkin(EV_RUTAS, w, pid, ROUTES[n], "Regular", -55)

        # ── Teachers, tagged Volunteer in Sunday school
        for n, loc in enumerate(["nur", "kin", "kin", "g3", "g3"]):
            pid = f"t{n}"
            self._person(pid, 50 + n, FIRST[(n + 5) % len(FIRST)], LAST[(n + 6) % len(LAST)],
                         28 + n * 5, child=False)
            for w in range(WEEKS):
                if w == CANCELLED_ESCUELA_WEEK or (n + w) % 7 == 0:
                    continue
                # t4 was a regular attender until she started teaching in week 14.
                kind = "Regular" if (n == 4 and w < 14) else "Volunteer"
                self._checkin(EV_ESCUELA, w, pid, loc, kind, -35 + n * 6 + w % 4)
                if n == 1 and w == 19:   # checked in twice; the earlier time counts
                    self._checkin(EV_ESCUELA, w, pid, loc, kind, -50)

        # ── "C" session: helpers check in, but nobody is tagged Volunteer yet
        for n in range(2):
            pid = f"ch{n}"
            self._person(pid, 60 + n, FIRST[(n + 15) % len(FIRST)], LAST[(n + 4) % len(LAST)],
                         41 + n, child=False)
            for w in range(16, WEEKS):
                self._checkin(EV_C, w, pid, "cth", "Regular", -20)

        # ── Bus workers: some tagged Volunteer on their route, some in the workers' room
        for n in range(6):
            pid = f"b{n}"
            self._person(pid, 70 + n, FIRST[(n + 8) % len(FIRST)], LAST[(n + 2) % len(LAST)],
                         22 + n * 6, child=False)
            for w in range(WEEKS):
                if (n + w) % 9 == 0:
                    continue
                if n < 3:
                    self._checkin(EV_RUTAS, w, pid, ROUTES[0 if n < 2 else 1], "Volunteer", -90 + n)
                else:
                    self._checkin(EV_RUTAS, w, pid, "rw", "Regular", -90 + n)
                self._checkin(EV_JUNTA, w, pid, "jun", "Regular", -12 + n * 5 + w % 3)

        # ── Teens at the Junta: 16 counts as a worker, 15 does not, no birthday does not
        for n, age in enumerate([16, 15, None]):
            pid = f"j{n}"
            self._person(pid, 80 + n * 2, FIRST[(n + 2) % len(FIRST)], LAST[(n + 9) % len(LAST)],
                         age, child=False)
            for w in range(14, WEEKS):
                self._checkin(EV_JUNTA, w, pid, "jun", "Regular", 3 + n)

        # ── Households (People API): siblings in pairs, five kinds of primary contact
        for pid, i in kids:
            hh, kind = f"h{i // 2}", (i // 2) % 5
            attrs = self.people[pid]
            record = {"type": "Person", "id": pid,
                      "attributes": {"name": attrs["name"], "child": True,
                                     "birthdate": attrs["birthdate"]},
                      "relationships": {"households": {"data": []}}}
            self.people_api[pid] = record
            if kind == 3:           # no household on file
                continue
            record["relationships"]["households"]["data"] = [{"type": "Household", "id": hh}]
            if hh in self.households:
                continue
            if kind == 2:           # an older sibling is the primary contact → no parent shown
                contact, cname = pid, attrs["name"]
            else:
                contact, cname = f"g{i // 2}", f"Mamá {attrs['last_name']}"
                same_home = kind == 0 and attrs["addresses"] and attrs["addresses"][0]["street_line_1"]
                street = attrs["addresses"][0]["street_line_1"] if same_home else f"{900 + i} Avenida Inventada"
                self.people_api[contact] = {
                    "type": "Person", "id": contact,
                    "attributes": {"name": cname, "child": False,
                                   "birthdate": None if kind == 1 else "1988-03-04"},
                    "relationships": {
                        "phone_numbers": {"data": [] if kind == 4 else
                                          [{"type": "PhoneNumber", "id": f"ph{contact}"}]},
                        "addresses": {"data": [{"type": "Address", "id": f"ad{contact}"}]},
                    },
                    "_included": ([] if kind == 4 else [
                        {"type": "PhoneNumber", "id": f"ph{contact}",
                         "attributes": {"number": f"(832) 555-02{i:02d}", "primary": True}},
                    ]) + [
                        {"type": "Address", "id": f"ad{contact}",
                         "attributes": {"street": street, "city": "Houston", "state": "TX",
                                        "zip": "77000", "primary": True}},
                    ],
                }
            self.households[hh] = {"primary_contact_id": contact, "primary_contact_name": cname}

    # ── HTTP ──────────────────────────────────────────────────────────────────

    def get(self, url, params=None, auth=None, headers=None, timeout=None):   # as requests.get
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query))
        query.update({k: str(v) for k, v in (params or {}).items()})
        path = parts.path.strip("/").split("/")
        kind, body = self._route(path, query)
        self.requests.append(kind)
        if body is None:
            return FakeResponse(404, {"errors": [{"title": "Not found"}]})
        return FakeResponse(200, body)

    def _page(self, kind: str, path: list[str], query: dict, items: list, **extra) -> dict:
        size = min(PAGE_SIZE[kind], int(query.get("per_page", 25)))
        offset = int(query.get("offset", 0))
        body = {"data": items[offset:offset + size], "links": {}, **extra}
        if offset + size < len(items):
            nxt = {**query, "offset": offset + size}
            body["links"]["next"] = f"{BASE}/{'/'.join(path)}?{urlencode(nxt)}"
        return body

    def _route(self, path: list[str], query: dict):
        if path == ["check-ins", "v2", "events"]:
            items = [{"type": "Event", "id": eid, "attributes": {"name": name}} for eid, name in EVENTS]
            return "check-ins/events", self._page("events", path, query, items)

        if path[:3] == ["check-ins", "v2", "events"] and path[4:] == ["event_periods"]:
            event = path[3]
            if event not in EVENT_START:
                return "check-ins/event_periods", None
            hour, minute = EVENT_START[event]
            # One period per Sunday, plus next Sunday's (already created, not started).
            days = SUNDAYS + [LAST_SUNDAY + timedelta(weeks=1)]
            items = [{"type": "EventPeriod", "id": f"{event}-{w:02d}",
                      "attributes": {"starts_at": f"{d.isoformat()}T{hour:02d}:{minute:02d}:00Z"}}
                     for w, d in enumerate(days)]
            items.reverse()   # order=-starts_at
            return "check-ins/event_periods", self._page("event_periods", path, query, items)

        if path[:3] == ["check-ins", "v2", "events"] and path[4:5] == ["event_periods"] \
                and path[6:] == ["check_ins"]:
            event, week = path[3], int(path[5].split("-")[1])
            body = self._page("check_ins", path, query, self.checkins.get((event, week), []))
            included, seen = [], set()
            for c in body["data"]:
                loc = c["relationships"]["locations"]["data"][0]["id"]
                pid = c["relationships"]["person"]["data"]["id"]
                for key, item in (
                    (("Location", loc), {"type": "Location", "id": loc,
                                         "attributes": {"name": LOCATIONS[loc]}}),
                    (("Person", pid), {"type": "Person", "id": pid, "attributes": self.people[pid]}),
                ):
                    if key not in seen:
                        seen.add(key)
                        included.append(item)
            body["included"] = included
            return "check-ins/check_ins", body

        if path == ["people", "v2", "people"]:
            include = query.get("include", "")
            ids = [i for i in query.get("where[id]", "").split(",") if i in self.people_api]
            data, included, seen = [], [], set()
            for pid in ids:
                record = self.people_api[pid]
                rels = record["relationships"]
                if include == "households":
                    data.append({**{k: v for k, v in record.items() if k != "_included"},
                                 "relationships": {"households": rels.get("households", {"data": []})}})
                    for h in rels.get("households", {}).get("data", []):
                        if h["id"] not in seen:
                            seen.add(h["id"])
                            included.append({"type": "Household", "id": h["id"],
                                             "attributes": self.households[h["id"]]})
                else:
                    data.append({k: v for k, v in record.items() if k != "_included"})
                    included.extend(record.get("_included", []))
            return f"people/people?include={include}", self._page("people", path, query, data,
                                                                  included=included)

        return "unknown:" + "/".join(path), None

    def request_counts(self) -> dict:
        counts = Counter(self.requests)
        return {"total": len(self.requests), **{k: counts[k] for k in sorted(counts)}}


class FakeResponse:
    def __init__(self, status: int, body: dict):
        self.status_code = status
        self.ok = status < 400
        self._body = body
        self.text = ""
        self.headers: dict = {}

    def json(self) -> dict:
        return self._body

    def raise_for_status(self) -> None:
        if not self.ok:
            import requests
            raise requests.exceptions.HTTPError(f"{self.status_code} from fake Planning Center")
