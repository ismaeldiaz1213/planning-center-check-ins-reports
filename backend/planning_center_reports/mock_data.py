# Mock attendees and attendance data for preview.py and demo_run.py.
# Addresses and phone numbers use public Chick-fil-A locations near the church.

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

MOCK_SUNDAY_DATA = [
    {"label": "Abr 6",  "regular":  9, "visitors": 2},
    {"label": "Abr 13", "regular":  8, "visitors": 0},
    {"label": "Abr 20", "regular": 10, "visitors": 1},
    {"label": "Abr 27", "regular":  7, "visitors": 0},
    {"label": "May 4",  "regular": 11, "visitors": 3},
]
