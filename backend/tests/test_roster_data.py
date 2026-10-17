# tests/test_roster_data.py
#
# The roster rules in roster_data.py: who is active, who moved to "Hace tiempo",
# date added, new this week, workers, Sunday counts, routes and volunteer arrivals.

from datetime import UTC, datetime, timedelta

from planning_center_reports.roster_data import (
    Period,
    attach_guardians,
    build_rosters,
    build_volunteer_report,
    child_ids,
    latest_location_by_person,
    periods_with_checkins,
)

FIRST = datetime(2026, 8, 23, 15, 0, tzinfo=UTC)
PERIODS = [Period(f"ep{i}", FIRST + timedelta(weeks=i)) for i in range(8)]   # Aug 23 … Oct 11
LOCATIONS = [
    {"type": "Location", "id": "A", "attributes": {"name": "3rd Grade Girls"}},
    {"type": "Location", "id": "B", "attributes": {"name": "4th Grade Girls"}},
]


def person(pid, first="Ana", last="Lopez", child=True, **attrs):
    return {"type": "Person", "id": pid,
            "attributes": {"first_name": first, "last_name": last, "child": child, **attrs}}


def checkin(pid, period, loc="A", kind="Regular", created=None, times=()):
    return {
        "attributes": {"first_name": "", "last_name": "", "kind": kind,
                       "created_at": created or ""},
        "relationships": {
            "person":       {"data": {"id": pid}},
            "locations":    {"data": [{"id": loc}] if loc else []},
            "event_period": {"data": {"id": f"ep{period}"}},
            "event_times":  {"data": [{"id": t} for t in times]},
        },
    }


def build(checkins, people, active_weeks=6, **kw):
    return build_rosters(checkins, LOCATIONS + people, PERIODS, active_weeks, **kw)


class TestActiveAndInactive:
    def test_seen_in_the_window_is_active(self):
        r = build([checkin("p1", 7)], [person("p1")])["3rd Grade Girls"]
        assert [m.person_id for m in r.active] == ["p1"]
        assert r.inactive == []

    def test_not_seen_lately_moves_to_hace_tiempo(self):
        r = build([checkin("p1", 0), checkin("p1", 1)], [person("p1")])["3rd Grade Girls"]
        assert r.active == []
        (m,) = r.inactive
        assert m.weeks_absent == 6
        assert m.times_total == 2
        assert m.last_seen == PERIODS[1].local_date

    def test_attendance_counts_only_the_window(self):
        cks = [checkin("p1", i) for i in (0, 1, 5, 6, 7)]
        (m,) = build(cks, [person("p1")])["3rd Grade Girls"].active
        assert (m.attended, m.window) == (3, 6)
        assert m.attendance_label == "3/6"

    def test_window_shrinks_when_history_is_short(self):
        (m,) = build([checkin("p1", 7)], [person("p1")], active_weeks=20)["3rd Grade Girls"].active
        assert m.window == 8

    def test_inactive_sorted_most_recently_lapsed_first(self):
        cks = [checkin("old", 0), checkin("recent", 1)]
        r = build(cks, [person("old", last="Z"), person("recent", last="A")])["3rd Grade Girls"]
        assert [m.person_id for m in r.inactive] == ["recent", "old"]


class TestDateAddedAndNew:
    def test_regular_since_the_first_sunday_has_no_date_added(self):
        (m,) = build([checkin("p1", 0), checkin("p1", 7)], [person("p1")])["3rd Grade Girls"].active
        assert m.date_added is None
        assert m.is_new is False

    def test_date_added_is_first_sunday_in_this_class(self):
        (m,) = build([checkin("p1", 3), checkin("p1", 7)], [person("p1")])["3rd Grade Girls"].active
        assert m.date_added == PERIODS[3].local_date

    def test_first_ever_check_in_on_the_latest_sunday_is_new(self):
        r = build([checkin("p1", 7)], [person("p1")])["3rd Grade Girls"]
        assert r.active[0].is_new is True
        assert r.new_this_week == 1

    def test_recent_additions_are_counted(self):
        r = build([checkin("a", 0), checkin("a", 7), checkin("b", 4)], [person("a"), person("b")])
        assert r["3rd Grade Girls"].added_recently == 1


class TestClassChanges:
    def test_person_appears_only_in_their_latest_class(self):
        cks = [checkin("p1", 0, "A"), checkin("p1", 5, "B")]
        rosters = build(cks, [person("p1")])
        assert "3rd Grade Girls" not in rosters
        (m,) = rosters["4th Grade Girls"].active
        assert m.date_added == PERIODS[5].local_date
        assert m.is_new is False           # not new to church — just new to the class

    def test_location_filter_limits_rosters(self):
        cks = [checkin("p1", 7, "A"), checkin("p2", 7, "B")]
        rosters = build(cks, [person("p1"), person("p2")], location_filter="4th")
        assert list(rosters) == ["4th Grade Girls"]

    def test_check_in_without_a_location_is_ignored(self):
        assert build([checkin("p1", 7, loc=None)], [person("p1")]) == {}


class TestWorkers:
    def test_volunteer_tag_moves_person_to_workers(self):
        r = build([checkin("t1", 7, kind="Volunteer"), checkin("k1", 7)],
                  [person("t1", child=False), person("k1")])["3rd Grade Girls"]
        assert [m.person_id for m in r.workers] == ["t1"]
        assert [m.person_id for m in r.active] == ["k1"]

    def test_workers_are_left_out_of_sunday_counts(self):
        r = build([checkin("t1", 7, kind="Volunteer"), checkin("k1", 7)],
                  [person("t1"), person("k1")])["3rd Grade Girls"]
        assert r.sundays[-1].total == 1

    def test_lapsed_workers_are_not_on_the_call_list(self):
        r = build([checkin("t1", 0, kind="Volunteer"), checkin("k1", 7)],
                  [person("t1"), person("k1")])["3rd Grade Girls"]
        assert r.workers == [] and r.inactive == []

    def test_workers_never_show_a_route(self):
        r = build([checkin("t1", 7, kind="Volunteer")], [person("t1")],
                  route_map={"t1": "Ruta 7"})["3rd Grade Girls"]
        assert r.workers[0].route == ""


class TestSundayCounts:
    def test_counts_cover_the_window_with_first_timers_split_out(self):
        cks = [checkin("a", 0), checkin("a", 6), checkin("a", 7), checkin("b", 7)]
        r = build(cks, [person("a"), person("b")])["3rd Grade Girls"]
        assert len(r.sundays) == 6
        assert r.sundays[-1].label == PERIODS[7].label
        assert (r.sundays[-1].regular, r.sundays[-1].visitors) == (1, 1)
        assert r.sundays[-2].total == 1


class TestRoutesAndHelpers:
    def test_route_is_the_most_recent_ridden_ignoring_drivers(self):
        included = [{"type": "Location", "id": "r1", "attributes": {"name": "Ruta 1"}},
                    {"type": "Location", "id": "r7", "attributes": {"name": "Ruta 7"}}]
        cks = [checkin("k1", 2, "r1"), checkin("k1", 6, "r7"), checkin("d1", 6, "r7", kind="Volunteer")]
        assert latest_location_by_person(cks, included, PERIODS) == {"k1": "Ruta 7"}

    def test_periods_without_check_ins_are_dropped(self):
        kept = periods_with_checkins(PERIODS, [checkin("p1", 2), checkin("p1", 5)])
        assert [p.id for p in kept] == ["ep2", "ep5"]

    def test_child_ids_include_kids_and_minors_only(self):
        rosters = build([checkin("kid", 7), checkin("teen", 7), checkin("adult", 7)], [
            person("kid", child=True),
            person("teen", child=False, birthdate=f"{datetime.now().year - 15}-01-01"),
            person("adult", child=False, birthdate="1980-01-01"),
        ])
        assert sorted(child_ids(rosters)) == ["kid", "teen"]

    def test_attach_guardians_sets_parent_on_members(self):
        rosters = build([checkin("kid", 7)], [person("kid")])
        attach_guardians(rosters, {"kid": {"name": "Mamá", "phone": "1", "address": ""}})
        assert rosters["3rd Grade Girls"].active[0].guardian["name"] == "Mamá"


# ── Volunteer arrivals ────────────────────────────────────────────────────────

def arrived(pid, period, minutes, **kw):
    """Check-in `minutes` after 15:00 UTC on that Sunday."""
    when = PERIODS[period].starts_at + timedelta(minutes=minutes)
    return checkin(pid, period, created=when.strftime("%Y-%m-%dT%H:%M:%SZ"), **kw)


class TestVolunteerReport:
    def _report(self, cks, people, **kw):
        return build_volunteer_report("Asistencia", cks, LOCATIONS + people,
                                      PERIODS[-4:], UTC, **kw)

    def test_only_volunteer_tagged_check_ins_count_by_default(self):
        r = self._report([arrived("t1", 7, -20, kind="Volunteer"), arrived("k1", 7, 5)],
                         [person("t1", name="Teacher One"), person("k1")])
        assert [row.name for row in r.rows] == ["Teacher One"]
        assert r.rows[0].arrivals[-1].clock == "2:40"

    def test_min_age_mode_takes_everyone_old_enough(self):
        r = self._report([arrived("adult", 7, 10), arrived("kid", 7, 10)],
                         [person("adult", name="Adult", birthdate="1980-01-01"),
                          person("kid", name="Kid", birthdate="2018-01-01")], min_age=16)
        assert [row.name for row in r.rows] == ["Adult"]

    def test_earliest_check_in_wins_and_absences_are_none(self):
        r = self._report([arrived("t1", 7, 5, kind="Volunteer"), arrived("t1", 7, -3, kind="Volunteer")],
                         [person("t1", name="T")])
        assert [a.clock if a else None for a in r.rows[0].arrivals] == [None, None, None, "2:57"]

    def test_times_are_local(self):
        from zoneinfo import ZoneInfo
        r = build_volunteer_report("A", [arrived("t1", 7, 0, kind="Volunteer")],
                                   LOCATIONS + [person("t1", name="T")], PERIODS[-4:],
                                   ZoneInfo("America/Chicago"))
        assert r.rows[0].arrivals[-1].clock == "10:00"      # 15:00 UTC in October = 10:00 CDT

    def test_summary_numbers(self):
        cks = [arrived("a", 6, -20, kind="Volunteer"), arrived("a", 7, 10, kind="Volunteer"),
               arrived("b", 7, 0, kind="Volunteer")]
        r = self._report(cks, [person("a", name="A"), person("b", name="B")])
        last = r.sundays[-1]
        assert (last.present, last.first, last.average) == (2, "3:00", "3:05")
        assert r.sundays[0].present == 0 and r.sundays[0].first == ""
        assert r.attendance_rate == 3 / 8
        assert r.rows[0].average_clock == "2:55"

    def test_group_of_names_each_row(self):
        r = self._report([arrived("t1", 7, 0, kind="Volunteer")], [person("t1", name="T")],
                         group_of=lambda pid, loc: f"{loc}!")
        assert r.rows[0].group == "3rd Grade Girls!"
