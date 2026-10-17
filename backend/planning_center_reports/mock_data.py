# Mock attendees and attendance data for preview.py and demo_run.py.
# Addresses and phone numbers use public Chick-fil-A locations near the church.
#
# mock_roster() and mock_volunteers() turn these into the same shapes the real
# pipeline builds (roster_data.LocationRoster / VolunteerReport), so previews
# exercise every section of the PDFs: new kids, parents, workers, "hace tiempo".

from datetime import UTC, date, datetime, timedelta

MOCK_ATTENDEES = [
    # Complex 1 — 12935 TX-249 (multiple units, sorted by apt#)
    {
        "person_id": "1",
        "first_name": "Ashton",       "last_name": "Diego",
        "birthday":   "1985-12-16",   "phone": "(281) 445-6177",
        "grade": "",
        "address": "12935 TX-249, APT 102, Houston, TX, 77086",
        "is_visitor": False,          "attendance": "5/5",
        "route": "Ruta 1 - Bus",      "is_helper": False,
    },
    {
        "person_id": "2",
        "first_name": "Lixi",         "last_name": "Pastor",
        "birthday":   "2016-09-04",   "phone": "(281) 445-6177",
        "grade": "4°",
        "address": "12935 TX-249, APT 204, Houston, TX, 77086",
        "is_visitor": False,          "attendance": "4/5",
        "route": "Ruta 1 - Bus",      "is_helper": False,
    },
    {
        "person_id": "3",
        "first_name": "Andina",       "last_name": "Pastor",
        "birthday":   "",             "phone": "(281) 445-6177",   # missing birthday
        "grade": "",
        "address": "12935 TX-249, APT 506, Houston, TX, 77086",
        "is_visitor": False,          "attendance": "3/5",
        "route": "Ruta 2 - Van",      "is_helper": False,
    },
    # Complex 2 — 430 Cypress Creek Pkwy (two units)
    {
        "person_id": "4",
        "first_name": "Chalott",      "last_name": "Diaz",
        "birthday":   "2012-10-06",   "phone": "(281) 444-4736",
        "grade": "5°",
        "address": "430 Cypress Creek Pkwy, 46, Houston, TX, 77090",
        "is_visitor": False,          "attendance": "5/5",
        "route": "Ruta 2 - Van",      "is_helper": False,
    },
    {
        "person_id": "5",
        "first_name": "Azaf",         "last_name": "Diaz",
        "birthday":   "2015-08-19",   "phone": "(281) 444-4736",
        "grade": "",                  # minor with no grade → yellow
        "address": "430 Cypress Creek Pkwy, 46, Houston, TX, 77090",
        "is_visitor": False,          "attendance": "2/5",
        "route": "Ruta 2 - Van",      "is_helper": False,
    },
    # Helper (age 16+, attends Junta de Rutas) — filtered out of Escuela roster
    {
        "person_id": "6",
        "first_name": "Ingrid",       "last_name": "Rivero",
        "birthday":   "1986-05-08",   "phone": "(281) 444-4736",
        "grade": "",
        "address": "430 Cypress Creek Pkwy, 13A, Houston, TX, 77090",
        "is_visitor": False,          "attendance": "5/5",
        "route": "",                  "is_helper": True,
    },
    # New visitors this week — visitor icon, 165 West Road
    {
        "person_id": "7",
        "first_name": "Marco",        "last_name": "Espinal",
        "birthday":   "1995-02-16",   "phone": "(281) 402-4005",
        "grade": "",
        "address": "165 West Road, Apt 41B, Houston, TX, 77037",
        "is_visitor": True,           "attendance": "1/5",
        "route": "Ruta 1 - Bus",      "is_helper": False,
        "created_at": "2026-05-01T00:00:00Z",
    },
    {
        "person_id": "8",
        "first_name": "Tania",        "last_name": "Espinal Quintanilla",
        "birthday":   "1970-04-12",   "phone": "(281) 402-4005",
        "grade": "",
        "address": "165 West Road, Apt 41B, Houston, TX, 77037",
        "is_visitor": True,           "attendance": "1/5",
        "route": "Ruta 1 - Bus",      "is_helper": False,
        "created_at": "2026-05-01T00:00:00Z",
    },
    # Single-family — 20608 I-45
    {
        "person_id": "9",
        "first_name": "Samantha",     "last_name": "Lainez",
        "birthday":   "2017-01-22",   "phone": "(281) 353-4336",
        "grade": "",
        "address": "20608 I-45, Spring, TX, 77373",
        "is_visitor": False,          "attendance": "4/5",
        "route": "Ruta 3 - Carro",    "is_helper": False,
    },
    # Bad/missing address → yellow highlight
    {
        "person_id": "10",
        "first_name": "Carlos",       "last_name": "Gomez",
        "birthday":   "1990-05-10",   "phone": "(281) 353-7500",
        "grade": "",
        "address": "Houston, TX",
        "is_visitor": False,          "attendance": "3/5",
        "route": "",                  "is_helper": False,
    },
    # Missing phone AND birthday → yellow on both cells
    {
        "person_id": "11",
        "first_name": "Maria",        "last_name": "Torres",
        "birthday":   "",             "phone": "",
        "grade": "",
        "address": "8510 Spring Cypress Rd, Spring, TX, 77379",
        "is_visitor": False,          "attendance": "2/5",
        "route": "Ruta 3 - Carro",    "is_helper": False,
    },
    # Toddlers — age-based grade labels (Nursery / 3 años / 4 años)
    {
        "person_id": "12",
        "first_name": "Sofia",        "last_name": "Mendez",
        "birthday":   "2023-06-15",   "phone": "(281) 251-0996",
        "grade": "",
        "address": "8510 Spring Cypress Rd, Spring, TX, 77379",
        "is_visitor": False,          "attendance": "5/5",
        "route": "Ruta 2 - Van",      "is_helper": False,
    },
    {
        "person_id": "13",
        "first_name": "Lucas",        "last_name": "Preciado",
        "birthday":   "2022-03-01",   "phone": "(281) 251-0996",
        "grade": "",
        "address": "8510 Spring Cypress Rd, Apt 8B, Spring, TX, 77379",
        "is_visitor": False,          "attendance": "1/5",
        "route": "Ruta 1 - Bus",      "is_helper": False,
    },
    {
        "person_id": "14",
        "first_name": "Camila",       "last_name": "Lagos",
        "birthday":   "2020-05-21",   "phone": "(281) 251-0996",
        "grade": "",
        "address": "8510 Spring Cypress Rd, Apt 8B, Spring, TX, 77379",
        "is_visitor": False,          "attendance": "5/5",
        "route": "Ruta 2 - Van",      "is_helper": False,
    },
]



# ── Builders ──────────────────────────────────────────────────────────────────

_SUNDAYS = 8
_WINDOW  = 6


def _mock_periods():
    from planning_center_reports.roster_data import Period
    last = date(2026, 10, 11)
    return [
        Period(f"demo-{i}", datetime.combine(last - timedelta(weeks=_SUNDAYS - 1 - i),
                                             datetime.min.time(), tzinfo=UTC).replace(hour=15))
        for i in range(_SUNDAYS)
    ]


def mock_roster(location: str, show_route: bool = True):
    """A LocationRoster built from MOCK_ATTENDEES covering every PDF section."""
    from planning_center_reports.roster_data import LocationRoster, Member, SundayCount

    periods = _mock_periods()
    roster = LocationRoster(
        location=location,
        history_start=periods[0].local_date,
        history_sundays=_SUNDAYS,
        window_start=periods[_SUNDAYS - _WINDOW].local_date,
        sundays=[SundayCount(p.label, r, v) for p, (r, v) in zip(
            periods[-_WINDOW:], [(9, 1), (8, 0), (10, 2), (7, 0), (11, 1), (10, 3)], strict=True)],
    )
    for i, a in enumerate(MOCK_ATTENDEES):
        attended = int(a.get("attendance", "0/5").split("/")[0]) + (1 if i % 3 == 0 else 0)
        m = Member(
            person_id=a["person_id"],
            first_name=a["first_name"],
            last_name=a["last_name"],
            phone=a.get("phone", ""),
            address=a.get("address", ""),
            birthday=a.get("birthday", ""),
            grade=a.get("grade", ""),
            route=a.get("route", "") if show_route else "",
            attended=min(attended, _WINDOW),
            window=_WINDOW,
            times_total=attended + 1,
            date_added=periods[-1 if a.get("is_visitor") else (i % _SUNDAYS)].local_date
            if i % _SUNDAYS else None,
            last_seen=periods[-1].local_date,
            is_new=bool(a.get("is_visitor")),
            is_worker=bool(a.get("is_helper")),
        )
        if i % 4 == 1:
            m.guardian = {"name": f"Mamá {a['last_name']}", "phone": "(281) 555-0142",
                          "address": "" if i % 8 == 1 else "1200 Example Rd, Apt 4, Houston"}
        if m.is_worker:
            roster.workers.append(m)
        elif i % 5 == 4:
            m.attended, m.weeks_absent = 0, 6 + i % 4
            m.last_seen = periods[_SUNDAYS - 1 - m.weeks_absent].local_date
            roster.inactive.append(m)
        else:
            roster.active.append(m)
    roster.active.sort(key=lambda m: m.sort_key)
    return roster


def mock_volunteers(title: str = "Asistencia de voluntarios"):
    """A VolunteerReport with varied check-in times and a few absences."""
    from planning_center_reports.roster_data import Arrival, VolunteerReport, VolunteerRow, format_clock

    periods = _mock_periods()[-4:]
    names = [("Clase Primaria", "Ingrid Rivero"), ("Clase Primaria", "Carlos Gomez"),
             ("Clase Secundaria", "Maria Torres"), ("Clase Secundaria", "Samantha Lainez")]
    times = [[575, 582, 570, None], [595, 603, 598, 592], [612, 620, None, 609], [560, 565, 555, 562]]
    rows = [
        VolunteerRow(name, name, group,
                     [None if m is None else Arrival(m, format_clock(m)) for m in mins])
        for (group, name), mins in zip(names, times, strict=True)
    ]
    return VolunteerReport(title=title, periods=periods, rows=rows)
