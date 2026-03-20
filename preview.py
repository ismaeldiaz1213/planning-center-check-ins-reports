#!/usr/bin/env python3
"""
preview.py — Generate sample PDFs locally for layout and theme testing.
No Planning Center or Google Drive credentials needed.

Usage:
    python preview.py                    # all themes, both PDF types
    python preview.py --theme primavera  # one specific theme
    python preview.py --type roster      # only the simple roster PDF
    python preview.py --type direcciones # only the address-grouped PDF
    python preview.py --open             # open PDFs in your viewer after generating

Output folder: ./previews/
"""

import argparse
import os
import subprocess
import sys

# ── Mock data ─────────────────────────────────────────────────────────────────
# Addresses and phone numbers use real Chick-fil-A locations near the church
# so this data is safe to commit publicly.
# Edit this list freely to test edge cases.

MOCK_ATTENDEES = [
    # Complex 1 — 12935 TX-249 (multiple units, sorted by apt#)
    {
        "person_id": "1",
        "first_name": "Ashton",       "last_name": "Diego",
        "birthday":   "1985-12-16",   "phone": "(281) 445-6177",
        "grade": "",
        "address": "12935 TX-249, APT 102, Houston, TX, 77086",
        "is_visitor": False,          "attendance": "5/5",
    },
    {
        "person_id": "2",
        "first_name": "Lixi",         "last_name": "Pastor",
        "birthday":   "2016-09-04",   "phone": "(281) 445-6177",
        "grade": "4°",
        "address": "12935 TX-249, APT 204, Houston, TX, 77086",
        "is_visitor": False,          "attendance": "4/5",
    },
    {
        "person_id": "3",
        "first_name": "Andina",       "last_name": "Pastor",
        "birthday":   "",             "phone": "(281) 445-6177",   # missing birthday
        "grade": "",
        "address": "12935 TX-249, APT 506, Houston, TX, 77086",
        "is_visitor": False,          "attendance": "3/5",
    },
    # Complex 2 — 430 Cypress Creek Pkwy (two units)
    {
        "person_id": "4",
        "first_name": "Chalott",      "last_name": "Diaz",
        "birthday":   "2012-10-06",   "phone": "(281) 444-4736",
        "grade": "5°",
        "address": "430 Cypress Creek Pkwy, 46, Houston, TX, 77090",
        "is_visitor": False,          "attendance": "5/5",
    },
    {
        "person_id": "5",
        "first_name": "Azaf",         "last_name": "Diaz",
        "birthday":   "2015-08-19",   "phone": "(281) 444-4736",
        "grade": "",                  # minor with no grade → yellow
        "address": "430 Cypress Creek Pkwy, 46, Houston, TX, 77090",
        "is_visitor": False,          "attendance": "2/5",
    },
    {
        "person_id": "6",
        "first_name": "Ingrid",       "last_name": "Rivero",
        "birthday":   "1986-05-08",   "phone": "(281) 444-4736",
        "grade": "",
        "address": "430 Cypress Creek Pkwy, 13A, Houston, TX, 77090",
        "is_visitor": False,          "attendance": "5/5",
    },
    # New visitors this week — gold dot, 165 West Road
    {
        "person_id": "7",
        "first_name": "Marco",        "last_name": "Espinal",
        "birthday":   "1995-02-16",   "phone": "(281) 402-4005",
        "grade": "",
        "address": "165 West Road, Apt 41B, Houston, TX, 77037",
        "is_visitor": True,           "attendance": "1/5",
    },
    {
        "person_id": "8",
        "first_name": "Tania",        "last_name": "Espinal Quintanilla",
        "birthday":   "1970-04-12",   "phone": "(281) 402-4005",
        "grade": "",
        "address": "165 West Road, Apt 41B, Houston, TX, 77037",
        "is_visitor": True,           "attendance": "1/5",
    },
    # Single-family — 20608 I-45
    {
        "person_id": "9",
        "first_name": "Samantha",     "last_name": "Lainez",
        "birthday":   "2017-01-22",   "phone": "(281) 353-4336",
        "grade": "",
        "address": "20608 I-45, Spring, TX, 77373",
        "is_visitor": False,          "attendance": "4/5",
    },
    # Bad/missing address → yellow highlight
    {
        "person_id": "10",
        "first_name": "Carlos",       "last_name": "Gomez",
        "birthday":   "1990-05-10",   "phone": "(281) 353-7500",
        "grade": "",
        "address": "Houston, TX",
        "is_visitor": False,          "attendance": "3/5",
    },
    # Missing phone AND birthday → yellow on both cells
    {
        "person_id": "11",
        "first_name": "Maria",        "last_name": "Torres",
        "birthday":   "",             "phone": "",
        "grade": "",
        "address": "8510 Spring Cypress Rd, Spring, TX, 77379",
        "is_visitor": False,          "attendance": "2/5",
    },
    # Toddlers — age-based grade labels (Nursery / 3 años / 4 años)
    {
        "person_id": "12",
        "first_name": "Sofia",        "last_name": "Mendez",
        "birthday":   "2023-06-15",   "phone": "(281) 251-0996",
        "grade": "",
        "address": "8510 Spring Cypress Rd, Spring, TX, 77379",
        "is_visitor": False,          "attendance": "5/5",
    },
    {
        "person_id": "13",
        "first_name": "Lucas",        "last_name": "Preciado",
        "birthday":   "2022-03-01",   "phone": "(281) 251-0996",
        "grade": "",
        "address": "8510 Spring Cypress Rd, Apt 8B, Spring, TX, 77379",
        "is_visitor": False,          "attendance": "1/5",
    },
    {
        "person_id": "14",
        "first_name": "Camila",       "last_name": "Lagos",
        "birthday":   "2020-05-21",   "phone": "(281) 251-0996",
        "grade": "",
        "address": "8510 Spring Cypress Rd, Apt 8B, Spring, TX, 77379",
        "is_visitor": False,          "attendance": "5/5",
    },
]

THEMES_AVAILABLE = [None, "primavera", "verano", "otono", "invierno"]
THEME_LABELS     = {
    None:         "default (azul)",
    "primavera":  "Campaña de Primavera",
    "verano":     "Campaña de Verano",
    "otono":      "Campaña de Otoño",
    "invierno":   "Campaña de Invierno",
}

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate PDF previews with mock data.")
    parser.add_argument(
        "--theme",
        choices=["default", "primavera", "verano", "otono", "invierno"],
        default=None,
        help="Generate only this theme (default: all themes)"
    )
    parser.add_argument(
        "--type",
        choices=["roster", "direcciones", "both"],
        default="both",
        help="Which PDF type to generate (default: both)"
    )
    parser.add_argument(
        "--open", action="store_true",
        help="Open generated PDFs in your default viewer after generating"
    )
    args = parser.parse_args()

    # Stub out the imports that main.py needs but we don't have credentials for
    import types
    for mod in ["google", "google.oauth2", "google.oauth2.service_account",
                "googleapiclient", "googleapiclient.discovery", "googleapiclient.http",
                "dotenv", "requests"]:
        if mod not in sys.modules:
            sys.modules[mod] = types.ModuleType(mod)
    sys.modules["dotenv"].load_dotenv = lambda: None
    sys.modules["requests"].auth = types.ModuleType("auth")
    sys.modules["requests.auth"] = sys.modules["requests"].auth
    sys.modules["requests.auth"].HTTPBasicAuth = lambda a, b: None
    sys.modules["google.oauth2"].service_account = types.ModuleType("sc")
    sys.modules["googleapiclient.discovery"].build = lambda *a, **k: None
    sys.modules["googleapiclient.http"].MediaFileUpload = lambda *a, **k: None
    os.environ.setdefault("PCO_APP_ID", "preview")
    os.environ.setdefault("PCO_SECRET", "preview")
    os.environ.setdefault("GOOGLE_DRIVE_PARENT_FOLDER_ID", "preview")

    import main as m

    # Output folder
    out_dir = os.path.join(os.path.dirname(__file__), "previews")
    os.makedirs(out_dir, exist_ok=True)

    themes_to_run = (
        [None if args.theme == "default" else args.theme]
        if args.theme else THEMES_AVAILABLE
    )

    generated = []

    for theme_key in themes_to_run:
        m._theme = m.THEMES[theme_key]
        slug     = theme_key or "default"
        label    = THEME_LABELS[theme_key]

        print(f"\n── {label} ──")

        if args.type in ("roster", "both"):
            path = os.path.join(out_dir, f"{slug}_Roster.pdf")
            m.generate_simple_roster_pdf(
                "Ruta 1 - Bus", "Ministerio de Autobuses",
                MOCK_ATTENDEES, path
            )
            print(f"  ✓ {os.path.basename(path)}")
            generated.append(path)

        if args.type in ("direcciones", "both"):
            path = os.path.join(out_dir, f"{slug}_Direcciones-Roster.pdf")
            m.generate_address_pdf("Ruta 1 - Bus", MOCK_ATTENDEES, path)
            print(f"  ✓ {os.path.basename(path)}")
            generated.append(path)

    print(f"\nAll previews saved to: {out_dir}/")

    if args.open:
        print("Opening PDFs...")
        for path in generated:
            try:
                subprocess.Popen(["xdg-open", path])
            except Exception:
                print(f"  Could not open {path} — open it manually.")


if __name__ == "__main__":
    main()