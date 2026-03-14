import os
import sys
import time
import argparse
import requests
from requests.auth import HTTPBasicAuth
from collections import defaultdict
from datetime import datetime

# Cache so each unique person_id is only fetched once
_person_cache = {}

from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

load_dotenv()

PCO_APP_ID = os.getenv("PCO_APP_ID")
PCO_SECRET = os.getenv("PCO_SECRET")
GOOGLE_DRIVE_PARENT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID")

BASE_URL = "https://api.planningcenteronline.com"
auth = HTTPBasicAuth(PCO_APP_ID, PCO_SECRET)

# ── Layout constants ─────────────────────────────────────────────────────────
PAGE_W, PAGE_H = landscape(letter)   # 792 x 612 pts (landscape)
MARGIN        = 36
USABLE_W      = PAGE_W - 2 * MARGIN   # 720 pts
LOGO_PATH     = os.path.join(os.path.abspath(os.path.dirname(__file__)), "ibl_logo.png")

HEADER_H      = 46               # tighter header
ADDR_BAR_H    = 20
COL_HDR_H     = 18
ROW_H         = 18
MIN_EMPTY_ROWS = 5
FOOTER_H      = 24

# Columns: Nombre, Apellido, Cumpleaños, Teléfono, Grado, Apto., Dirección  → must sum to 720
COL_WIDTHS   = [105, 105, 68, 100, 44, 48, 250]
HEADERS_ES   = ["Nombre", "Apellido", "Cumpleaños", "Teléfono", "Grado", "Apto.", "Dirección"]

def _rows_available(is_first_page):
    """How many data rows fit in the content area of a page."""
    if is_first_page:
        content_h = PAGE_H - 2*MARGIN - HEADER_H - ADDR_BAR_H - COL_HDR_H - FOOTER_H
    else:
        content_h = PAGE_H - 2*MARGIN - ADDR_BAR_H - COL_HDR_H - FOOTER_H
    return int(content_h / ROW_H)

# Colours
NAVY          = colors.HexColor("#0D1F5C")
BLUE_MID      = colors.HexColor("#1a4b9c")
BLUE_LIGHT    = colors.HexColor("#4A90D9")
BLUE_PALE     = colors.HexColor("#EEF4FB")
BLUE_ADDR_BAR = colors.HexColor("#2255aa")
WHITE         = colors.white
GREY_LINE     = colors.HexColor("#CCCCCC")
GREEN_TEXT    = colors.HexColor("#1a7a1a")
ORANGE_TEXT   = colors.HexColor("#b85c00")


# ── Planning Center helpers ──────────────────────────────────────────────────

def get_event_id(event_name):
    url = f"{BASE_URL}/check-ins/v2/events"
    response = requests.get(url, auth=auth)
    response.raise_for_status()
    for event in response.json()["data"]:
        if event["attributes"]["name"] == event_name:
            return event["id"]
    raise Exception(f"Event '{event_name}' not found")


def get_recent_event_periods(event_id, weeks=5):
    url = f"{BASE_URL}/check-ins/v2/events/{event_id}/event_periods"
    params = {"order": "-created_at", "per_page": weeks}
    response = requests.get(url, auth=auth, params=params)
    response.raise_for_status()
    data = response.json()["data"]
    if not data:
        raise Exception("No event periods found")
    print(f"  Using {len(data)} event period(s):", flush=True)
    for ep in data:
        print(f"    - {ep['id']} ({ep['attributes'].get('starts_at', 'unknown date')})", flush=True)
    return [ep["id"] for ep in data]


def get_checkins_for_event_periods(event_id, event_period_ids):
    all_checkins, all_included = [], []
    valid_period_ids = set(event_period_ids)
    print(f"  Fetching all check-ins for event {event_id}...", flush=True)
    url = f"{BASE_URL}/check-ins/v2/check_ins"
    params = {"where[event_id]": event_id, "include": "locations,person", "per_page": 100}
    page = 1
    while url:
        print(f"    Page {page}...", flush=True)
        response = requests.get(url, auth=auth, params=params)
        print(f"    Status: {response.status_code}", flush=True)
        response.raise_for_status()
        body = response.json()
        batch = body["data"]
        kept = 0
        for checkin in batch:
            ep_id = checkin.get("relationships", {}).get("event_period", {}).get("data", {}).get("id")
            if ep_id in valid_period_ids:
                all_checkins.append(checkin)
                kept += 1
        all_included.extend(body.get("included", []))
        print(f"    Got {len(batch)}, kept {kept}", flush=True)
        next_url = body.get("links", {}).get("next")
        if next_url == url:
            break
        url = next_url
        params = {}
        page += 1
    print(f"  Total matching check-ins: {len(all_checkins)}", flush=True)
    return all_checkins, all_included


def get_person_details(person_id):
    if person_id in _person_cache:
        return _person_cache[person_id]
    url = f"{BASE_URL}/people/v2/people/{person_id}"
    params = {"include": "emails,phone_numbers,addresses"}
    max_retries = 7
    response = None
    for attempt in range(max_retries):
        try:
            response = requests.get(url, auth=auth, params=params, timeout=60)
        except (requests.exceptions.SSLError,
                requests.exceptions.ReadTimeout,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            err_type = type(e).__name__
            wait = 2 ** attempt
            print(f"  {err_type} — connection issue. Waiting {wait}s before retry ({attempt+1}/{max_retries})...", flush=True)
            for remaining in range(wait, 0, -1):
                print(f"  Retrying in {remaining}s...  ", end="\r", flush=True)
                time.sleep(1)
            print(f"  Retrying now...                   ", flush=True)
            continue

        if response.status_code == 404:
            _person_cache[person_id] = {}
            return {}
        if response.status_code == 429:
            wait = 2 ** attempt
            for remaining in range(wait, 0, -1):
                print(f"  Rate limited — retrying in {remaining}s...  ", end="\r", flush=True)
                time.sleep(1)
            print(f"  Rate limit wait done, retrying...          ", flush=True)
            continue
        response.raise_for_status()
        break
    else:
        print(f"  Giving up on person {person_id} after {max_retries} retries.", flush=True)
        _person_cache[person_id] = {}
        return {}

    body = response.json()
    person_attrs = body["data"]["attributes"]
    included = body.get("included", [])

    emails  = [i for i in included if i["type"] == "Email"]
    phones  = [i for i in included if i["type"] == "PhoneNumber"]
    addresses = [i for i in included if i["type"] == "Address"]

    primary_phone = next(
        (p["attributes"]["number"] for p in phones if p["attributes"].get("primary")),
        phones[0]["attributes"]["number"] if phones else ""
    )

    primary_address = ""
    if addresses:
        addr = next((a for a in addresses if a["attributes"].get("primary")), addresses[0])
        a = addr["attributes"]
        parts = filter(None, [
            a.get("street_line_1"), a.get("street_line_2"),
            a.get("city"), a.get("state"), a.get("zip"),
        ])
        primary_address = ", ".join(parts)

    GRADE_MAP = {
        -2: "Nursery", -1: "Pre-K", 0: "Kinder",
        1: "1°", 2: "2°", 3: "3°", 4: "4°", 5: "5°", 6: "6°",
        7: "7°", 8: "8°", 9: "9°", 10: "10°", 11: "11°", 12: "12°",
    }
    grade_raw = person_attrs.get("grade")
    grade = GRADE_MAP.get(grade_raw, "") if grade_raw is not None else ""

    result = {
        "phone":   primary_phone,
        "address": primary_address,
        "birthday": person_attrs.get("birthdate") or "",
        "grade": grade,
    }
    _person_cache[person_id] = result
    return result


# ── PDF Generation ───────────────────────────────────────────────────────────

VERSE_TEXT  = "\"Id por todo el mundo y predicad el evangelio a toda criatura\""
VERSE_REF   = "Marcos 16:15 — RV1960"
YELLOW_WARN = colors.HexColor("#FFF176")

MESES_ES = {
    1:"enero", 2:"febrero", 3:"marzo", 4:"abril", 5:"mayo", 6:"junio",
    7:"julio", 8:"agosto", 9:"septiembre", 10:"octubre", 11:"noviembre", 12:"diciembre"
}

def _fecha_es(dt=None):
    """Return 'Generado el DD de mes de YYYY a las HH:MM' fully in Spanish."""
    dt = dt or datetime.now()
    return (f"Generado el {dt.day} de {MESES_ES[dt.month]} de {dt.year} "
            f"a las {dt.strftime('%H:%M')}")

def _fmt_birthday(raw):
    """Convert 'YYYY-MM-DD' → 'MM/DD/YYYY'. Passes through anything else."""
    if not raw:
        return ""
    import re
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', raw.strip())
    if m:
        return f"{m.group(2)}/{m.group(3)}/{m.group(1)}"
    return raw

def _age_from_birthday(birthday_raw):
    """Return integer age, or None if birthday is missing/unparseable."""
    if not birthday_raw:
        return None
    import re
    from datetime import date
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', birthday_raw.strip())
    if not m:
        return None
    try:
        dob = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except ValueError:
        return None

def _is_minor(birthday_raw):
    age = _age_from_birthday(birthday_raw)
    return age is not None and age < 18

def _resolve_grade(pco_grade, birthday_raw):
    """
    Return the display grade string, using age for children 4 and under
    since PCO often doesn't set the grade field for toddlers/preschoolers.
    Age 0-2  → 'Nursery'
    Age 3    → '3 años'
    Age 4    → '4 años'
    Age 5+   → use PCO grade field (Pre-K, Kinder, 1°…12°)
    """
    age = _age_from_birthday(birthday_raw)

    # Age-based override for young children
    if age is not None:
        if age <= 2:
            return "Nursery"
        if age == 3:
            return "3 años"
        if age == 4:
            return "4 años"

    # Fall back to PCO grade field for older kids
    return pco_grade or ""

def _is_bad_address(addr):
    """True if address is blank or only city-level (e.g. 'Houston, TX')."""
    if not addr or not addr.strip():
        return True
    import re
    stripped = addr.strip().lower()
    if re.fullmatch(r'[\w\s]+,?\s*tx[\s,]*\d*', stripped):
        return True
    return False

def _extract_apt(address):
    """
    Pull the apartment/unit identifier out of an address string.
    Handles: '506', '#10B', 'APT 13A', 'Apto#20A', 'Apto. 202', bare comma-number, etc.
    Returns the display string (e.g. '10B', '13A', '506') or ''.
    """
    import re
    if not address:
        return ""
    # Explicit keyword patterns: APT, Apt., Apto, Apto., #
    m = re.search(r'(?:apto?\.?\s*#?\s*|#\s*)(\d+\w*)', address, re.IGNORECASE)
    if m:
        return m.group(1)
    # Bare number between commas: "... Rd, 506, Houston ..."
    m2 = re.search(r',\s*(\d+[A-Za-z]?)\s*,', address)
    if m2:
        return m2.group(1)
    return ""

def _parse_apt_number(address):
    """Sortable tuple (int, str) for the apt number."""
    import re
    token = _extract_apt(address)
    if token:
        digits = re.match(r'(\d+)', token)
        return (int(digits.group(1)) if digits else 9999, token)
    return (9999, "")

def _complex_key(address):
    """Street/complex portion stripped of apt number, lowercased."""
    import re
    if not address:
        return ""
    cleaned = re.sub(r',?\s*(?:apto?\.?\s*#?\s*|#\s*)?\d+\w*\s*(?=,)', ',',
                     address, flags=re.IGNORECASE)
    parts = [p.strip() for p in cleaned.split(',')]
    return parts[0].lower() if parts else address.lower()

def _street_only(address):
    """Remove the apt portion for display in the address column."""
    import re
    if not address:
        return ""
    # Remove ', 506,' or ', APT 13A,' style segments
    cleaned = re.sub(r',\s*(?:apto?\.?\s*#?\s*|#\s*)?\d+\w*(?=\s*,)', '',
                     address, flags=re.IGNORECASE)
    return cleaned.strip().strip(',').strip()


def _draw_page_header(c, route_name, subtitle, gen_dt):
    """Draw logo + titles. route_name is big; subtitle ('Ministerio de Autobuses') is small."""
    top = PAGE_H - MARGIN

    logo_h = 22
    logo_w = logo_h * (300 / 58)
    if os.path.exists(LOGO_PATH):
        c.drawImage(LOGO_PATH, MARGIN, top - logo_h, width=logo_w, height=logo_h, mask='auto')
        title_x = MARGIN + logo_w + 12
    else:
        title_x = MARGIN

    # Route name — prominent
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(NAVY)
    c.drawString(title_x, top - 15, route_name)

    # "Ministerio de Autobuses" — smaller, below
    c.setFont("Helvetica", 8)
    c.setFillColor(BLUE_MID)
    c.drawString(title_x, top - 26, subtitle)

    # Generated date top-right, fully in Spanish with time
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#888888"))
    c.drawRightString(PAGE_W - MARGIN, top - 10, _fecha_es(gen_dt))

    rule_y = top - HEADER_H + 4
    c.setStrokeColor(BLUE_LIGHT)
    c.setLineWidth(1.5)
    c.line(MARGIN, rule_y, PAGE_W - MARGIN, rule_y)
    return rule_y - 4


def _draw_page_footer(c, page_num):
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, MARGIN - 14, VERSE_TEXT)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(MARGIN, MARGIN - 23, VERSE_REF)
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#888888"))
    c.drawRightString(PAGE_W - MARGIN, MARGIN - 18, f"Página {page_num}")
    c.setStrokeColor(BLUE_LIGHT)
    c.setLineWidth(0.8)
    c.line(MARGIN, MARGIN - 4, PAGE_W - MARGIN, MARGIN - 4)


def _draw_address_bar(c, display_addr, y):
    c.setFillColor(BLUE_ADDR_BAR)
    c.roundRect(MARGIN, y - ADDR_BAR_H, USABLE_W, ADDR_BAR_H, 3, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(WHITE)
    label = (f"Grupo de Dirección: {display_addr}"
             if display_addr else "Grupo de Dirección: (sin dirección registrada)")
    c.drawString(MARGIN + 8, y - ADDR_BAR_H + 6, label)
    return y - ADDR_BAR_H


def _draw_column_headers(c, y):
    c.setFillColor(BLUE_LIGHT)
    c.rect(MARGIN, y - COL_HDR_H, USABLE_W, COL_HDR_H, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(WHITE)
    x = MARGIN
    for header, col_w in zip(HEADERS_ES, COL_WIDTHS):
        c.drawString(x + 4, y - COL_HDR_H + 5, header)
        x += col_w
    return y - COL_HDR_H


def _draw_data_row(c, y, row_data, row_index, warn_flags):
    """
    row_data   : [nombre, apellido, apto, cumpleaños, teléfono, grado, dirección]
    warn_flags : parallel booleans — True = highlight yellow
    """
    base_bg = WHITE if row_index % 2 == 0 else BLUE_PALE
    x = MARGIN
    for col_w, warn in zip(COL_WIDTHS, warn_flags):
        c.setFillColor(YELLOW_WARN if warn else base_bg)
        c.rect(x, y - ROW_H, col_w, ROW_H, fill=1, stroke=0)
        x += col_w

    # Grid
    c.setStrokeColor(GREY_LINE)
    c.setLineWidth(0.3)
    c.rect(MARGIN, y - ROW_H, USABLE_W, ROW_H, fill=0, stroke=1)
    x = MARGIN
    for col_w in COL_WIDTHS[:-1]:
        x += col_w
        c.line(x, y, x, y - ROW_H)

    # Text
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)
    x = MARGIN
    for val, col_w in zip(row_data, COL_WIDTHS):
        text = str(val) if val else ""
        max_chars = int(col_w / 5.2)
        c.drawString(x + 4, y - ROW_H + 5, text[:max_chars])
        x += col_w
    return y - ROW_H


def _rows_available(is_first_page):
    if is_first_page:
        content_h = PAGE_H - 2*MARGIN - HEADER_H - ADDR_BAR_H - COL_HDR_H - FOOTER_H
    else:
        content_h = PAGE_H - 2*MARGIN - ADDR_BAR_H - COL_HDR_H - FOOTER_H
    return int(content_h / ROW_H)


def generate_pdf(event_name, location_name, attendees):
    filename = "Roster.pdf"
    c = rl_canvas.Canvas(filename, pagesize=landscape(letter))
    gen_dt = datetime.now()   # single timestamp for the whole document

    # ── Group by complex (ignore apt#), sort within group by apt# ─────────────
    complex_groups = defaultdict(list)
    for person in attendees:
        addr = (person.get("address") or "").strip()
        complex_groups[_complex_key(addr)].append(person)

    for key in complex_groups:
        complex_groups[key].sort(key=lambda p: _parse_apt_number(p.get("address") or ""))

    def group_sort(item):
        k, _ = item
        return (0, k) if k else (1, "")
    sorted_groups = sorted(complex_groups.items(), key=group_sort)

    page_num    = 1
    first_group = True

    def new_page(is_first):
        if not is_first:
            c.showPage()
        _draw_page_header(c, location_name, "Ministerio de Autobuses", gen_dt)
        return PAGE_H - MARGIN - HEADER_H - 4

    cursor_y  = new_page(is_first=True)
    rows_left = _rows_available(is_first_page=True)

    for group_key, group_people in sorted_groups:
        # Display address = street only (no apt#) from first person in group
        raw_addr    = (group_people[0].get("address") or "").strip() if group_people else ""
        bar_addr    = _street_only(raw_addr)

        needed = len(group_people) + MIN_EMPTY_ROWS + 1
        if rows_left < needed and not first_group:
            _draw_page_footer(c, page_num)
            page_num += 1
            cursor_y  = new_page(is_first=False)
            rows_left = _rows_available(is_first_page=False)

        first_group = False
        cursor_y  = _draw_address_bar(c, bar_addr, cursor_y)
        cursor_y  = _draw_column_headers(c, cursor_y)
        rows_left -= 1
        row_index  = 0

        for person in group_people:
            if rows_left <= 0:
                _draw_page_footer(c, page_num)
                page_num += 1
                cursor_y  = new_page(is_first=False)
                cursor_y  = _draw_address_bar(c, bar_addr, cursor_y)
                cursor_y  = _draw_column_headers(c, cursor_y)
                rows_left = _rows_available(is_first_page=False) - 1
                row_index = 0

            fn   = person.get("first_name", "")
            ln   = person.get("last_name",  "")
            addr = person.get("address",    "")
            apt  = _extract_apt(addr)
            bday_raw = person.get("birthday", "")
            bday = _fmt_birthday(bday_raw)
            ph   = person.get("phone", "")
            grade = _resolve_grade(person.get("grade", ""), bday_raw)
            addr_display = _street_only(addr)

            # Grade cell yellow only if person is a minor but grade is missing
            is_child = _is_minor(bday_raw)
            grade_warn = is_child and not grade

            # Column order: Nombre, Apellido, Cumpleaños, Teléfono, Grado, Apto., Dirección
            warn = [
                not fn,
                not ln,
                not bday,
                not ph,
                grade_warn,
                False,                   # Apto — always optional
                _is_bad_address(addr),
            ]
            cursor_y  = _draw_data_row(
                c, cursor_y,
                [fn, ln, bday, ph, grade, apt, addr_display],
                row_index, warn
            )
            rows_left -= 1
            row_index += 1

        # ── Empty writable rows ────────────────────────────────────────────
        if rows_left < MIN_EMPTY_ROWS:
            _draw_page_footer(c, page_num)
            page_num += 1
            cursor_y  = new_page(is_first=False)
            cursor_y  = _draw_address_bar(c, bar_addr, cursor_y)
            cursor_y  = _draw_column_headers(c, cursor_y)
            rows_left = _rows_available(is_first_page=False) - 1
            row_index = 0

        empty_to_draw = min(MIN_EMPTY_ROWS, rows_left)
        for _ in range(empty_to_draw):
            cursor_y  = _draw_data_row(
                c, cursor_y,
                ["", "", "", "", "", "", bar_addr],
                row_index, [False]*7
            )
            row_index += 1
            rows_left -= 1

    _draw_page_footer(c, page_num)
    c.save()
    return filename


# ── Google Drive helpers ─────────────────────────────────────────────────────

def get_drive_service():
    credentials = service_account.Credentials.from_service_account_file(
        "credentials.json",
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=credentials)


def get_or_create_folder(service, parent_id, folder_name):
    query = (
        f"name='{folder_name}' and "
        f"mimeType='application/vnd.google-apps.folder' and "
        f"'{parent_id}' in parents and trashed=false"
    )
    results = service.files().list(q=query, supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']
    metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
    folder = service.files().create(body=metadata, fields='id', supportsAllDrives=True).execute()
    return folder['id']


def upload_and_replace(service, folder_id, filename):
    query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    files = results.get('files', [])
    media = MediaFileUpload(filename, mimetype='application/pdf')
    if files:
        service.files().update(fileId=files[0]['id'], media_body=media, supportsAllDrives=True).execute()
    else:
        metadata = {'name': filename, 'parents': [folder_id]}
        service.files().create(body=metadata, media_body=media, supportsAllDrives=True).execute()


# ── Sunday School (Escuela Dominical) PDF ────────────────────────────────────

ED_COL_WIDTHS = [115, 115, 72, 110, 48, 52, 208]
ED_HEADERS    = ["Nombre", "Apellido", "Cumpleaños", "Teléfono", "Grado", "Apto.", "Dirección"]


def generate_escuela_pdf(location_name, attendees, bus_rider_ids):
    """
    Simple roster for Sunday school teachers.
    attendees     : list of person records
    bus_rider_ids : set of person_ids who rode the bus in the last 5 weeks
    """
    filename = "Roster.pdf"
    c = rl_canvas.Canvas(filename, pagesize=landscape(letter))
    gen_dt = datetime.now()

    def new_page(is_first):
        if not is_first:
            c.showPage()
        _draw_page_header(c, location_name, "Escuela Dominical", gen_dt)
        return PAGE_H - MARGIN - HEADER_H - 4

    # Column header row (reuse draw helper with ED headers/widths)
    def draw_ed_col_headers(y):
        c.setFillColor(BLUE_LIGHT)
        c.rect(MARGIN, y - COL_HDR_H, USABLE_W, COL_HDR_H, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(WHITE)
        x = MARGIN
        for header, col_w in zip(ED_HEADERS, ED_COL_WIDTHS):
            c.drawString(x + 4, y - COL_HDR_H + 5, header)
            x += col_w
        return y - COL_HDR_H

    def draw_ed_row(y, row_data, row_index, warn_flags):
        base_bg = WHITE if row_index % 2 == 0 else BLUE_PALE
        x = MARGIN
        for col_w, warn in zip(ED_COL_WIDTHS, warn_flags):
            c.setFillColor(YELLOW_WARN if warn else base_bg)
            c.rect(x, y - ROW_H, col_w, ROW_H, fill=1, stroke=0)
            x += col_w
        c.setStrokeColor(GREY_LINE)
        c.setLineWidth(0.3)
        c.rect(MARGIN, y - ROW_H, USABLE_W, ROW_H, fill=0, stroke=1)
        x = MARGIN
        for col_w in ED_COL_WIDTHS[:-1]:
            x += col_w
            c.line(x, y, x, y - ROW_H)
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.black)
        x = MARGIN
        for val, col_w in zip(row_data, ED_COL_WIDTHS):
            text = str(val) if val else ""
            max_chars = int(col_w / 5.2)
            c.drawString(x + 4, y - ROW_H + 5, text[:max_chars])
            x += col_w
        return y - ROW_H

    # Sort attendees alphabetically by last name, then first name
    sorted_attendees = sorted(attendees, key=lambda p: (p.get("last_name","").lower(),
                                                         p.get("first_name","").lower()))

    rows_per_page = int((PAGE_H - 2*MARGIN - HEADER_H - COL_HDR_H - FOOTER_H) / ROW_H)

    cursor_y  = new_page(is_first=True)
    cursor_y  = draw_ed_col_headers(cursor_y)
    rows_left = rows_per_page
    page_num  = 1
    row_index = 0

    for person in sorted_attendees:
        if rows_left <= 0:
            _draw_page_footer(c, page_num)
            page_num += 1
            cursor_y  = new_page(is_first=False)
            cursor_y  = draw_ed_col_headers(cursor_y)
            rows_left = rows_per_page
            row_index = 0

        fn       = person.get("first_name", "")
        ln       = person.get("last_name",  "")
        bday_raw = person.get("birthday",   "")
        bday     = _fmt_birthday(bday_raw)
        ph       = person.get("phone",      "")
        addr     = person.get("address",    "")
        apt      = _extract_apt(addr)
        addr_display = _street_only(addr)
        grade    = _resolve_grade(person.get("grade",""), bday_raw)

        pid      = person.get("person_id")
        is_bus   = pid in bus_rider_ids if pid else False

        is_child   = _is_minor(bday_raw)
        grade_warn = is_child and not grade

        warn = [
            not fn,
            not ln,
            not bday,
            not ph,
            grade_warn,
            False,
            _is_bad_address(addr),
        ]

        cursor_y  = draw_ed_row(cursor_y, [fn, ln, bday, ph, grade, apt, addr_display],
                                row_index, warn)
        rows_left -= 1
        row_index += 1

    _draw_page_footer(c, page_num)
    c.save()
    return filename


# ── Main ─────────────────────────────────────────────────────────────────────

def _build_attendees(checkins, included, weeks):
    """
    Shared helper: deduplicate check-ins, fetch person details, return
    (grouped_by_location, person_id_set_with_kind).
    Also returns a flat dict: person_id → record, and kind tracking.
    """
    location_lookup = {
        item["id"]: item["attributes"]["name"]
        for item in included if item["type"] == "Location"
    }
    person_lookup = {
        item["id"]: item
        for item in included if item["type"] == "Person"
    }

    grouped       = defaultdict(list)
    seen          = defaultdict(set)
    # person_id → set of kinds seen (e.g. {'Regular', 'Guest'})
    person_kinds  = defaultdict(set)
    unique_count  = 0
    skipped_count = 0

    for checkin in checkins:
        location_data = checkin["relationships"]["locations"]["data"]
        if not location_data:
            continue

        location_id   = location_data[0]["id"]
        location_name = location_lookup.get(location_id, "Unknown Location")

        person_rel = checkin["relationships"].get("person", {}).get("data")
        person_id  = person_rel["id"] if person_rel else None

        kind = checkin["attributes"].get("kind", "")
        if person_id:
            person_kinds[person_id].add(kind)

        if person_id and person_id in seen[location_name]:
            skipped_count += 1
            continue
        if person_id:
            seen[location_name].add(person_id)

        record = {
            "person_id":  person_id,
            "first_name": checkin["attributes"]["first_name"],
            "last_name":  checkin["attributes"]["last_name"],
            "phone":    "",
            "address":  "",
            "birthday": "",
            "grade":    "",
        }

        if person_id:
            sideloaded = person_lookup.get(person_id)
            if sideloaded:
                record["birthday"] = sideloaded["attributes"].get("birthdate") or ""

            if person_id not in _person_cache:
                print(f"  [{unique_count + 1}] Fetching {record['first_name']} {record['last_name']} (id: {person_id})...", flush=True)
                time.sleep(0.5)
            else:
                print(f"  [{unique_count + 1}] Cached: {record['first_name']} {record['last_name']}", flush=True)

            details = get_person_details(person_id)
            record.update(details)

        unique_count += 1
        grouped[location_name].append(record)

    print(f"  Processed {unique_count} unique, skipped {skipped_count} duplicates.", flush=True)
    return grouped, location_lookup, person_kinds


def main():
    parser = argparse.ArgumentParser(description="Generate PCO check-in rosters and upload to Google Drive.")
    parser.add_argument("event_name", help="PCO event name: 'Rutas' or 'Escuela Dominical'")
    parser.add_argument("--weeks", type=int, default=5, help="Number of recent weeks (default: 5)")
    args = parser.parse_args()

    event_name = args.event_name

    # ── RUTAS ─────────────────────────────────────────────────────────────────
    if event_name == "Rutas":
        print(f"Finding event 'Rutas'...", flush=True)
        event_id = get_event_id("Rutas")
        print("Event ID:", event_id, flush=True)

        print(f"Finding recent event periods (last {args.weeks} weeks)...", flush=True)
        event_period_ids = get_recent_event_periods(event_id, weeks=args.weeks)

        print("Fetching check-ins...", flush=True)
        checkins, included = get_checkins_for_event_periods(event_id, event_period_ids)

        grouped, location_lookup, _ = _build_attendees(checkins, included, args.weeks)
        print(f"Locations found: {list(location_lookup.values())}", flush=True)

        print("\nConnecting to Google Drive...", flush=True)
        drive_service = get_drive_service()

        for location_name, attendees in grouped.items():
            print(f"\nGenerating PDF for {location_name} ({len(attendees)} attendees)...", flush=True)
            pdf_file = generate_pdf("Rutas", location_name, attendees)
            location_folder_id = get_or_create_folder(drive_service, GOOGLE_DRIVE_PARENT_FOLDER_ID, location_name)
            upload_and_replace(drive_service, location_folder_id, pdf_file)
            os.remove(pdf_file)
            print(f"  ✓ Uploaded roster for {location_name}", flush=True)

    # ── ESCUELA DOMINICAL ─────────────────────────────────────────────────────
    elif event_name == "Escuela Dominical":

        # Step 1: fetch Escuela Dominical check-ins
        print("Finding event 'Escuela Dominical'...", flush=True)
        ed_event_id = get_event_id("Escuela Dominical")
        print("Event ID:", ed_event_id, flush=True)

        print(f"Finding recent event periods (last {args.weeks} weeks)...", flush=True)
        ed_period_ids = get_recent_event_periods(ed_event_id, weeks=args.weeks)

        print("Fetching Escuela Dominical check-ins...", flush=True)
        ed_checkins, ed_included = get_checkins_for_event_periods(ed_event_id, ed_period_ids)
        ed_grouped, ed_location_lookup, _ = _build_attendees(ed_checkins, ed_included, args.weeks)
        print(f"Locations found: {list(ed_location_lookup.values())}", flush=True)

        # Step 2: generate one PDF per Sunday school class location
        print("\nConnecting to Google Drive...", flush=True)
        drive_service = get_drive_service()

        for location_name, attendees in ed_grouped.items():
            print(f"\nGenerating Sunday school roster for {location_name} ({len(attendees)} attendees)...", flush=True)
            pdf_file = generate_escuela_pdf(location_name, attendees, set())
            location_folder_id = get_or_create_folder(drive_service, GOOGLE_DRIVE_PARENT_FOLDER_ID, location_name)
            upload_and_replace(drive_service, location_folder_id, pdf_file)
            os.remove(pdf_file)
            print(f"  ✓ Uploaded roster for {location_name}", flush=True)

    else:
        print(f"Unknown event '{event_name}'. Supported: 'Rutas', 'Escuela Dominical'", flush=True)
        sys.exit(1)

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()