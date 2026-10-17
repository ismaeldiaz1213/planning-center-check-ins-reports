# planning_center_reports/roster_data.py
#
# Pure transformations from raw PCO check-in data to what the PDFs draw.
# No I/O happens here — services.py fetches, this module shapes, pdf/ renders —
# so every rule below is unit-tested in tests/test_roster_data.py.
#
# The rules, per report:
#   • A person belongs to the location of their most recent check-in (mirrors
#     Check-Ins "pre-select"), so a kid who changed classes appears only once.
#   • Active   — seen in the last `active_weeks` Sundays → main roster.
#     Inactive — seen since the history start but not lately → "Hace tiempo".
#   • Workers  — Planning Center tags their latest check-in as kind "Volunteer";
#     they get their own table and are left out of the kids' counts.
#   • Date added — first check-in at their location since the history start.
#     Blank when that was the very first Sunday: they were already a regular.
#   • New (★) — their first check-in for the whole event was the latest Sunday.

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from statistics import mean

from planning_center_reports.config import MESES_ABREV
from planning_center_reports.pco_client import _parse_ts, age_from_birthday, person_details

VOLUNTEER_KIND = "Volunteer"


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Period:
    """One Sunday (PCO event period)."""
    id:        str
    starts_at: datetime          # aware UTC
    tz:        object = UTC

    @property
    def local_date(self) -> date:
        return self.starts_at.astimezone(self.tz).date()

    @property
    def label(self) -> str:
        """Short Spanish label, e.g. "Oct 11"."""
        return short_date(self.local_date)


def short_date(d: date | None) -> str:
    return f"{MESES_ABREV[d.month]} {d.day}" if d else ""


@dataclass
class Member:
    person_id:  str
    first_name: str
    last_name:  str
    phone:      str = ""
    address:    str = ""
    birthday:   str = ""
    grade:      str = ""
    child:      bool = False
    route:      str = ""
    guardian:   dict | None = None     # {"name", "phone", "address"} for kids
    attended:   int = 0                    # Sundays present in the active window
    window:     int = 0                    # size of the active window
    times_total: int = 0                   # Sundays present since the history start
    date_added: date | None = None      # None ⇒ regular since the start
    last_seen:  date | None = None
    weeks_absent: int = 0                  # Sundays since last seen
    is_new:     bool = False
    is_worker:  bool = False

    @property
    def attendance_label(self) -> str:
        return f"{self.attended}/{self.window}" if self.window else ""

    @property
    def sort_key(self) -> tuple:
        return (self.last_name.lower(), self.first_name.lower())


@dataclass
class SundayCount:
    label:    str
    regular:  int
    visitors: int

    @property
    def total(self) -> int:
        return self.regular + self.visitors


@dataclass
class LocationRoster:
    location: str
    active:   list[Member] = field(default_factory=list)
    inactive: list[Member] = field(default_factory=list)
    workers:  list[Member] = field(default_factory=list)
    sundays:  list[SundayCount] = field(default_factory=list)
    history_start: date | None = None
    history_sundays: int = 0
    window_start: date | None = None

    @property
    def new_this_week(self) -> int:
        return sum(1 for m in self.active if m.is_new)

    def is_recent(self, member: Member) -> bool:
        """Added inside the active window — the people worth a welcome call."""
        return bool(member.date_added and self.window_start and member.date_added >= self.window_start)

    @property
    def added_recently(self) -> int:
        return sum(1 for m in self.active if self.is_recent(m))

    @property
    def average_attendance(self) -> float:
        return mean(s.total for s in self.sundays) if self.sundays else 0.0


# ── Check-in parsing helpers ──────────────────────────────────────────────────

def _rel_id(checkin: dict, rel: str) -> str | None:
    data = checkin.get("relationships", {}).get(rel, {}).get("data")
    if isinstance(data, list):
        return data[0]["id"] if data else None
    return data["id"] if data else None


def index_included(included: list) -> tuple[dict, dict, dict]:
    """Split sideloaded records into (locations, people, event_times) by id."""
    locations, people, times = {}, {}, {}
    for item in included:
        kind = item.get("type")
        if kind == "Location":
            locations[item["id"]] = item["attributes"].get("name", "")
        elif kind == "Person":
            people[item["id"]] = item["attributes"]
        elif kind == "EventTime":
            times[item["id"]] = item["attributes"]
    return locations, people, times


def periods_with_checkins(periods: list[Period], checkins: list) -> list[Period]:
    """Drop Sundays nobody checked into (cancelled services, future placeholders)."""
    used = {_rel_id(c, "event_period") for c in checkins}
    return [p for p in periods if p.id in used]


def latest_location_by_person(checkins: list, included: list, periods: list[Period]) -> dict[str, str]:
    """Map person_id → name of the location of their most recent check-in.

    Used for the "Ruta" column: the route a kid rode most recently. Volunteer
    check-ins (drivers, captains) are ignored — a route belongs to its riders.
    """
    order = {p.id: i for i, p in enumerate(periods)}
    locations, _, _ = index_included(included)
    best: dict[str, tuple[int, str]] = {}
    for c in checkins:
        pid  = _rel_id(c, "person")
        idx  = order.get(_rel_id(c, "event_period"))
        name = locations.get(_rel_id(c, "locations") or "", "")
        if not pid or idx is None or not name or c["attributes"].get("kind") == VOLUNTEER_KIND:
            continue
        if pid not in best or idx >= best[pid][0]:
            best[pid] = (idx, name)
    return {pid: name for pid, (_, name) in best.items()}


# ── Roster builder ────────────────────────────────────────────────────────────

def build_rosters(
    checkins: list,
    included: list,
    periods: list[Period],
    active_weeks: int,
    route_map: dict[str, str] | None = None,
    location_filter: str | None = None,
) -> dict[str, LocationRoster]:
    """Group a report's check-ins into one LocationRoster per location.

    `periods` must be oldest-first and only contain Sundays that had check-ins.
    """
    route_map = route_map or {}
    locations, people, _ = index_included(included)
    order = {p.id: i for i, p in enumerate(periods)}
    n = len(periods)
    if n == 0:
        return {}
    window = min(active_weeks, n)
    window_first = n - window

    # person → list of (period idx, location name, kind, check-in record)
    visits: dict[str, list] = defaultdict(list)
    for c in checkins:
        pid = _rel_id(c, "person")
        idx = order.get(_rel_id(c, "event_period"))
        loc = locations.get(_rel_id(c, "locations") or "")
        if not pid or idx is None or not loc:
            continue
        visits[pid].append((idx, loc, c["attributes"].get("kind") or "", c))

    rosters: dict[str, LocationRoster] = {}
    # per location, per period idx: set of (person, first-ever idx, worker?)
    presence: dict[str, dict[int, list]] = defaultdict(lambda: defaultdict(list))

    for pid, rows in visits.items():
        rows.sort(key=lambda r: (r[0], r[3]["attributes"].get("created_at") or ""))
        last_idx, home, last_kind, last_checkin = rows[-1]
        if location_filter and location_filter.lower() not in home.lower():
            continue

        at_home   = sorted({r[0] for r in rows if r[1] == home})
        first_any = rows[0][0]
        attrs     = people.get(pid, {})
        details   = person_details(attrs) if attrs else {}

        member = Member(
            person_id=pid,
            first_name=attrs.get("first_name") or last_checkin["attributes"].get("first_name", ""),
            last_name=attrs.get("last_name") or last_checkin["attributes"].get("last_name", ""),
            phone=details.get("phone", ""),
            address=details.get("address", ""),
            birthday=details.get("birthday", ""),
            grade=details.get("grade", ""),
            child=bool(attrs.get("child")),
            route=route_map.get(pid, ""),
            attended=sum(1 for i in at_home if i >= window_first),
            window=window,
            times_total=len({r[0] for r in rows}),
            date_added=periods[at_home[0]].local_date if at_home[0] > 0 else None,
            last_seen=periods[last_idx].local_date,
            weeks_absent=n - 1 - last_idx,
            is_new=first_any == n - 1 and n > 1,
            is_worker=last_kind == VOLUNTEER_KIND,
        )

        roster = rosters.setdefault(home, LocationRoster(location=home))
        active = last_idx >= window_first
        if member.is_worker:
            if active:
                member.route = ""   # a route is a rider's, not a driver's
                roster.workers.append(member)
        elif active:
            roster.active.append(member)
        else:
            roster.inactive.append(member)

        if not member.is_worker:
            for i in at_home:
                if i >= window_first:
                    presence[home][i].append(first_any == i and i > 0)

    for name, roster in rosters.items():
        roster.active.sort(key=lambda m: m.sort_key)
        roster.workers.sort(key=lambda m: m.sort_key)
        # Most recently lapsed first — the likeliest to come back with a call.
        roster.inactive.sort(key=lambda m: (m.weeks_absent, m.sort_key))
        roster.history_start = periods[0].local_date
        roster.history_sundays = n
        roster.window_start = periods[window_first].local_date
        roster.sundays = [
            SundayCount(
                label=periods[i].label,
                regular=sum(1 for is_first in presence[name][i] if not is_first),
                visitors=sum(1 for is_first in presence[name][i] if is_first),
            )
            for i in range(window_first, n)
        ]
    return rosters


def child_ids(rosters: dict[str, LocationRoster]) -> list[str]:
    """Everyone on a roster who needs a parent line: kids, active or not."""
    out = []
    for roster in rosters.values():
        for m in roster.active + roster.inactive:
            if m.child or (m.birthday and age_from_birthday(m.birthday) < 18):
                out.append(m.person_id)
    return out


def attach_guardians(rosters: dict[str, LocationRoster], guardians: dict[str, dict]) -> None:
    for roster in rosters.values():
        for m in roster.active + roster.inactive:
            g = guardians.get(m.person_id)
            if g and g.get("name"):
                m.guardian = g


# ── Volunteer attendance ──────────────────────────────────────────────────────

@dataclass
class Arrival:
    minute_of_day: int    # local check-in time as minutes after midnight
    clock:         str    # e.g. "9:42"


def format_clock(minute_of_day: float) -> str:
    """Minutes after midnight → "9:42" (12-hour, no a.m./p.m. — services are mornings)."""
    m = round(minute_of_day)
    hour, minute = divmod(m, 60)
    return f"{hour % 12 or 12}:{minute:02d}"


def _average_clock(arrivals: list[Arrival]) -> str:
    return format_clock(mean(a.minute_of_day for a in arrivals)) if arrivals else ""


@dataclass
class VolunteerRow:
    person_id: str
    name:      str
    group:     str
    arrivals:  list[Arrival | None]

    @property
    def present(self) -> list[Arrival]:
        return [a for a in self.arrivals if a]

    @property
    def average_clock(self) -> str:
        return _average_clock(self.present)


@dataclass
class SundayVolunteers:
    label:   str
    present: int
    first:   str          # earliest check-in
    average: str          # average check-in


@dataclass
class VolunteerReport:
    title:   str
    periods: list[Period]
    rows:    list[VolunteerRow]

    @property
    def sundays(self) -> list[SundayVolunteers]:
        out = []
        for i, p in enumerate(self.periods):
            arrivals = [r.arrivals[i] for r in self.rows if r.arrivals[i]]
            out.append(SundayVolunteers(
                label=p.label,
                present=len(arrivals),
                first=format_clock(min(a.minute_of_day for a in arrivals)) if arrivals else "",
                average=_average_clock(arrivals),
            ))
        return out

    @property
    def average_present(self) -> float:
        return mean(s.present for s in self.sundays) if self.periods else 0.0

    @property
    def attendance_rate(self) -> float | None:
        slots = len(self.rows) * len(self.periods)
        return sum(len(r.present) for r in self.rows) / slots if slots else None


def build_volunteer_report(
    title: str,
    checkins: list,
    included: list,
    periods: list[Period],
    tz,
    min_age: int | None = None,
    group_of: Callable[[str, str], str] | None = None,
) -> VolunteerReport:
    """Who served and when they checked in, over `periods` (oldest first).

    Without `min_age`, volunteers are check-ins tagged kind "Volunteer".
    With it, everyone that age or older counts — for a workers-only event such
    as the bus ministry's meeting, where nobody is tagged.
    `group_of(person_id, location_name)` names the row's group (class/route).
    Times are reported as-is; no comparison with a scheduled start is made.
    """
    locations, people, _ = index_included(included)
    order = {p.id: i for i, p in enumerate(periods)}
    rows: dict[str, VolunteerRow] = {}

    for c in checkins:
        pid = _rel_id(c, "person")
        idx = order.get(_rel_id(c, "event_period"))
        if not pid or idx is None:
            continue
        attrs = people.get(pid, {})
        if min_age is None:
            if (c["attributes"].get("kind") or "") != VOLUNTEER_KIND:
                continue
        elif age_from_birthday(attrs.get("birthdate") or "") < min_age:
            continue
        checked = _parse_ts(c["attributes"].get("created_at") or "")
        if not checked:
            continue
        local = checked.astimezone(tz)
        minute_of_day = local.hour * 60 + local.minute

        loc = locations.get(_rel_id(c, "locations") or "", "")
        if pid not in rows:
            name = attrs.get("name") or (
                f"{c['attributes'].get('first_name', '')} {c['attributes'].get('last_name', '')}".strip()
            )
            group = group_of(pid, loc) if group_of else loc
            rows[pid] = VolunteerRow(pid, name, group or "Sin asignar", [None] * len(periods))
        prev = rows[pid].arrivals[idx]
        if prev is None or minute_of_day < prev.minute_of_day:
            rows[pid].arrivals[idx] = Arrival(minute_of_day, format_clock(minute_of_day))

    ordered = sorted(rows.values(), key=lambda r: (r.group == "Sin asignar", r.group, r.name.lower()))
    return VolunteerReport(title=title, periods=periods, rows=ordered)
