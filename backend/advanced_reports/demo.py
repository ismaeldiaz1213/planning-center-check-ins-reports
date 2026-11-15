# advanced_reports/demo.py
#
# A made-up church for local demos and tests: "Grace Community Church", English,
# with a Sunday School event and a Bus Routes event. DemoPco stands in for
# PcoClient (the methods a run and the dashboard use) and never touches the
# network. Every name, phone number and address here is invented.
#
# The data is generated from a fixed seed relative to today's date, so the
# rosters always show recent Sundays.

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta

from planning_center_reports.pco_client import RequestStats

ORG_ID = "dev-demo"
CHURCH = {"name": "Grace Community Church", "timezone": "America/New_York", "language": "en",
          "branding": {"verse_text": '"Let the little children come to me"',
                       "verse_ref": "Matthew 19:14",
                       "help_contact": "the welcome desk"}}
REPORTS = [
    {"id": "sunday-school", "label": "Sunday School", "pco_event": "Sunday School", "icon": "📚",
     "history_weeks": 12, "default_weeks": 4, "route_source_event": "Bus Routes",
     "show_route": True, "attendance_summary": True, "volunteer_report": True,
     "instructions": True, "drive_folder_prefix": "Sunday School"},
    {"id": "bus-routes", "label": "Bus Routes", "pco_event": "Bus Routes", "icon": "🚌",
     "subtitle": "Bus Ministry", "history_weeks": 12, "default_weeks": 4,
     "volunteer_report": True, "drive_folder_prefix": "Bus Routes"},
]

WEEKS = 12
EVENTS = {"ev-ss": "Sunday School", "ev-bus": "Bus Routes"}
START_UTC = {"ev-ss": (14, 45), "ev-bus": (13, 30)}
CLASSES = [("ss-nursery", "Nursery", (1, 4)), ("ss-k2", "K-2nd Grade", (5, 7)),
           ("ss-35", "3rd-5th Grade", (8, 10)), ("ss-youth", "Youth", (11, 17))]
ROUTES = [("bus-1", "Route 1 - North"), ("bus-2", "Route 2 - East")]
_FIRST = ["Ava", "Ben", "Chloe", "Dylan", "Ella", "Finn", "Grace", "Henry", "Isla", "Jack", "Kate",
          "Liam", "Mia", "Noah", "Olive", "Paul", "Quinn", "Ruby", "Sam", "Tess", "Uma", "Victor",
          "Wren", "Xander", "Yara", "Zane"]
_LAST = ["Adams", "Baker", "Carter", "Dawson", "Ellis", "Foster", "Grant", "Hayes", "Irwin",
         "Jensen", "Keller", "Lawson", "Meyer", "Nolan", "Owens", "Parker", "Reed", "Stone"]
_ADULT = ["Alice", "Brian", "Carla", "David", "Erin", "Frank", "Gina", "Howard", "Irene", "James"]


def _last_sunday(today: date) -> date:
    """The most recent Sunday strictly before today (so its check-ins are in the past)."""
    return today - timedelta(days=(today.weekday() + 1) % 7 or 7)


class DemoPco:
    def __init__(self, today: date | None = None, seed: int = 7):
        self.stats = RequestStats()
        rng = random.Random(seed)
        last = _last_sunday(today or datetime.now(UTC).date())
        self.sundays = [last - timedelta(weeks=WEEKS - 1 - w) for w in range(WEEKS)]
        self.people: dict[str, dict] = {}
        self.guardians: dict[str, dict] = {}
        self.checkins: dict[tuple[str, int], list[dict]] = {}
        self._seq = 0
        today = self.sundays[-1]

        def person(pid, first, last_name, age, child, i):
            self.people[pid] = {
                "first_name": first, "last_name": last_name, "name": f"{first} {last_name}",
                "child": child, "gender": "",
                "birthdate": (today - timedelta(days=age * 365 + 40 + i * 3)).isoformat(),
                "grade": (age - 5 if child and 5 <= age <= 17 else None),
                "created_at": "2025-01-12T15:00:00Z",
                "phone_numbers": [] if i % 9 == 4 else [{"number": f"(555) 01{i % 100:02d}-{1000 + i * 7}", "primary": True}],
                "addresses": [] if i % 11 == 6 else [{
                    "street_line_1": f"{120 + i * 4} Maple Street", "street_line_2": None,
                    "city": "Springfield", "state": "OH", "zip": "45501", "primary": True}],
            }

        # Kids: each belongs to one class; some ride a bus; some stopped coming;
        # a few are new this week.
        i = 0
        for loc_id, _name, (lo, hi) in CLASSES:
            for _n in range(rng.randint(11, 17)):
                i += 1
                pid = f"kid{i}"
                last_name = rng.choice(_LAST)
                person(pid, rng.choice(_FIRST), last_name, rng.randint(lo, hi), True, i)
                if i % 6:
                    parent = rng.choice(_ADULT)
                    self.guardians[pid] = {
                        "name": f"{parent} {last_name}",
                        "phone": f"(555) 02{i % 100:02d}-{2000 + i * 3}",
                        "address": "" if i % 4 else f"{300 + i} Oak Avenue, Springfield, OH, 45501",
                    }
                route = rng.choice(ROUTES)[0] if rng.random() < 0.4 else None
                pattern = rng.random()
                for w in range(WEEKS):
                    if pattern < 0.12 and w < WEEKS - 1:       # brand new this week
                        continue
                    if 0.12 <= pattern < 0.30 and w > 5:       # stopped coming
                        continue
                    if rng.random() < 0.72:
                        self._checkin("ev-ss", w, pid, loc_id, "Regular", rng.randint(-12, 9))
                        if route:
                            self._checkin("ev-bus", w, pid, route, "Regular", rng.randint(-20, 5))

        # Volunteers: teachers per class, drivers and helpers per route.
        for group, event in ([c[0] for c in CLASSES], "ev-ss"), ([r[0] for r in ROUTES], "ev-bus"):
            for loc_id in group:
                for _n in range(2 if event == "ev-ss" else 3):
                    i += 1
                    pid = f"vol{i}"
                    person(pid, rng.choice(_ADULT), rng.choice(_LAST), rng.randint(19, 60), False, i)
                    usual = rng.randint(-25, 5)
                    for w in range(WEEKS):
                        if rng.random() < 0.85:
                            self._checkin(event, w, pid, loc_id, "Volunteer", usual + rng.randint(-6, 12))

    def _checkin(self, event: str, w: int, pid: str, loc: str, kind: str, offset_min: int) -> None:
        self._seq += 1
        hour, minute = START_UTC[event]
        start = datetime.combine(self.sundays[w], datetime.min.time(), tzinfo=UTC).replace(hour=hour, minute=minute)
        p = self.people[pid]
        self.checkins.setdefault((event, w), []).append({
            "type": "CheckIn", "id": f"ci{self._seq}",
            "attributes": {"first_name": p["first_name"], "last_name": p["last_name"], "kind": kind,
                           "created_at": (start + timedelta(minutes=offset_min)).strftime("%Y-%m-%dT%H:%M:%SZ")},
            "relationships": {
                "locations":    {"data": [{"type": "Location", "id": loc}]},
                "person":       {"data": {"type": "Person", "id": pid}},
                "event_period": {"data": {"type": "EventPeriod", "id": f"{event}-{w:02d}"}},
                "event_times":  {"data": []},
            },
        })

    # ── The PcoClient methods a run and the dashboard use ─────────────────────
    def list_events(self) -> list[dict]:
        return [{"id": i, "name": n, "archived": False} for i, n in EVENTS.items()]

    def get_event_id(self, event_name: str) -> str:
        for event_id, name in EVENTS.items():
            if name == event_name:
                return event_id
        raise Exception(f"Event '{event_name}' not found")

    def get_locations(self, event_id: str) -> list[dict]:
        if event_id not in EVENTS:
            raise Exception(f"Event {event_id!r} not found")
        pairs = [(c[0], c[1]) for c in CLASSES] if event_id == "ev-ss" else ROUTES
        return [{"id": i, "name": n} for i, n in pairs]

    def get_event_periods_since(self, event_id, since, tz=UTC, max_periods=52) -> list[dict]:
        hour, minute = START_UTC[event_id]
        found = []
        for w, day in enumerate(self.sundays):
            starts = datetime.combine(day, datetime.min.time(), tzinfo=UTC).replace(hour=hour, minute=minute)
            if starts.astimezone(tz).date() >= since and starts <= datetime.now(UTC):
                found.append({"id": f"{event_id}-{w:02d}", "starts_at": starts})
        return found[-max_periods:]

    def get_checkins_for_event_periods(self, event_id, event_period_ids) -> tuple[list, list]:
        checkins: list[dict] = []
        for period_id in event_period_ids:
            checkins += self.checkins.get((event_id, int(period_id.rsplit("-", 1)[1])), [])
        included = [{"type": "Location", "id": loc["id"], "attributes": {"name": loc["name"]}}
                    for loc in self.get_locations(event_id)]
        seen: set[str] = set()
        for c in checkins:
            pid = c["relationships"]["person"]["data"]["id"]
            if pid not in seen:
                seen.add(pid)
                included.append({"type": "Person", "id": pid, "attributes": self.people[pid]})
        return checkins, included

    def get_guardians(self, child_ids) -> dict[str, dict]:
        return {i: self.guardians[i] for i in child_ids if i in self.guardians}
