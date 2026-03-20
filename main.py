import os
import sys
import time
import argparse
import requests
from requests.auth import HTTPBasicAuth
from collections import defaultdict
from datetime import datetime, timezone

# Cache so each unique person_id is only fetched once
_person_cache = {}

from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas as rl_canvas
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

load_dotenv()

PCO_APP_ID                    = os.getenv("PCO_APP_ID")
PCO_SECRET                    = os.getenv("PCO_SECRET")
GOOGLE_DRIVE_PARENT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID")

BASE_URL = "https://api.planningcenteronline.com"
auth     = HTTPBasicAuth(PCO_APP_ID, PCO_SECRET)

# ── Layout constants ──────────────────────────────────────────────────────────
PAGE_W, PAGE_H = landscape(letter)       # 792 x 612 pts
MARGIN         = 36
USABLE_W       = PAGE_W - 2 * MARGIN     # 720 pts
LOGO_PATH      = os.path.join(os.path.abspath(os.path.dirname(__file__)), "ibl_logo.png")

HEADER_H       = 46
ADDR_BAR_H     = 20
COL_HDR_H      = 18
ROW_H          = 18
MIN_EMPTY_ROWS = 5
FOOTER_H       = 24

# Address-grouped PDF columns (sum = 720)
# Star | Nombre | Apellido | Cumpleaños | Teléfono | Grado | Apto. | Asistencia | Dirección
COL_WIDTHS = [16, 95, 95, 65, 90, 44, 44, 36, 235]
HEADERS_ES = ["", "Nombre", "Apellido", "Cumpleaños", "Teléfono", "Grado", "Apto.", "Asist.", "Dirección"]

# Simple roster PDF columns (sum = 720)
SR_COL_WIDTHS = [16, 100, 100, 65, 95, 44, 44, 36, 220]
SR_HEADERS    = ["", "Nombre", "Apellido", "Cumpleaños", "Teléfono", "Grado", "Apto.", "Asist.", "Dirección"]

# ── Colour palettes ───────────────────────────────────────────────────────────
WHITE      = colors.white
GREY_LINE  = colors.HexColor("#CCCCCC")
YELLOW_WARN = colors.HexColor("#FFF176")   # always yellow — never themed
GOLD_STAR   = colors.HexColor("#F5A623")   # visitor dot — always gold

THEMES = {
    # Default IBL blue
    None: {
        "title":      colors.HexColor("#0D1F5C"),
        "subtitle":   colors.HexColor("#1a4b9c"),
        "col_header": colors.HexColor("#4A90D9"),
        "row_alt":    colors.HexColor("#EEF4FB"),
        "addr_bar":   colors.HexColor("#2255aa"),
        "rule":       colors.HexColor("#4A90D9"),
        "footer_text":colors.HexColor("#0D1F5C"),
        "campaign":   None,
        "emoji":      "",
    },
    "primavera": {
        "title":      colors.HexColor("#1B5E20"),
        "subtitle":   colors.HexColor("#388E3C"),
        "col_header": colors.HexColor("#43A047"),
        "row_alt":    colors.HexColor("#E8F5E9"),
        "addr_bar":   colors.HexColor("#2E7D32"),
        "rule":       colors.HexColor("#81C784"),
        "footer_text":colors.HexColor("#1B5E20"),
        "campaign":   "Campaña de Primavera",
        "emoji":      "🌿",
    },
    "verano": {
        "title":      colors.HexColor("#BF360C"),
        "subtitle":   colors.HexColor("#E64A19"),
        "col_header": colors.HexColor("#FF7043"),
        "row_alt":    colors.HexColor("#FBE9E7"),
        "addr_bar":   colors.HexColor("#D84315"),
        "rule":       colors.HexColor("#FFAB91"),
        "footer_text":colors.HexColor("#BF360C"),
        "campaign":   "Campaña de Verano",
        "emoji":      "☀️",
    },
    "otono": {
        "title":      colors.HexColor("#4E342E"),
        "subtitle":   colors.HexColor("#6D4C41"),
        "col_header": colors.HexColor("#8D6E63"),
        "row_alt":    colors.HexColor("#EFEBE9"),
        "addr_bar":   colors.HexColor("#5D4037"),
        "rule":       colors.HexColor("#BCAAA4"),
        "footer_text":colors.HexColor("#4E342E"),
        "campaign":   "Campaña de Otoño",
        "emoji":      "🍂",
    },
    "invierno": {
        "title":      colors.HexColor("#1A237E"),
        "subtitle":   colors.HexColor("#3949AB"),
        "col_header": colors.HexColor("#5C6BC0"),
        "row_alt":    colors.HexColor("#E8EAF6"),
        "addr_bar":   colors.HexColor("#283593"),
        "rule":       colors.HexColor("#9FA8DA"),
        "footer_text":colors.HexColor("#1A237E"),
        "campaign":   "Campaña de Invierno",
        "emoji":      "❄️",
    },
}

# Active theme — set in main() from --theme arg
_theme = THEMES[None]

def T(key):
    """Shorthand to get a colour from the active theme."""
    return _theme[key]

VERSE_TEXT = "\"Id por todo el mundo y predicad el evangelio a toda criatura\""
VERSE_REF  = "Marcos 16:15 — RV1960"

MESES_ES = {
    1:"enero", 2:"febrero", 3:"marzo", 4:"abril", 5:"mayo", 6:"junio",
    7:"julio", 8:"agosto", 9:"septiembre", 10:"octubre", 11:"noviembre", 12:"diciembre"
}


# ── Planning Center helpers ───────────────────────────────────────────────────

def get_event_id(event_name):
    url = f"{BASE_URL}/check-ins/v2/events"
    response = requests.get(url, auth=auth)
    response.raise_for_status()
    for event in response.json()["data"]:
        if event["attributes"]["name"] == event_name:
            return event["id"]
    raise Exception(f"Event '{event_name}' not found")


def get_recent_event_periods(event_id, weeks=5):
    url    = f"{BASE_URL}/check-ins/v2/events/{event_id}/event_periods"
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
    url    = f"{BASE_URL}/check-ins/v2/check_ins"
    params = {"where[event_id]": event_id, "include": "locations,person", "per_page": 100}
    page   = 1
    while url:
        print(f"    Page {page}...", flush=True)
        response = requests.get(url, auth=auth, params=params)
        print(f"    Status: {response.status_code}", flush=True)
        response.raise_for_status()
        body  = response.json()
        batch = body["data"]
        kept  = 0
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
        url    = next_url
        params = {}
        page  += 1
    print(f"  Total matching check-ins: {len(all_checkins)}", flush=True)
    return all_checkins, all_included


def get_person_details(person_id):
    if person_id in _person_cache:
        return _person_cache[person_id]

    url    = f"{BASE_URL}/people/v2/people/{person_id}"
    params = {"include": "emails,phone_numbers,addresses"}
    max_retries = 7
    response    = None

    for attempt in range(max_retries):
        try:
            response = requests.get(url, auth=auth, params=params, timeout=60)
        except (requests.exceptions.SSLError,
                requests.exceptions.ReadTimeout,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            err_type = type(e).__name__
            wait = 2 ** attempt
            print(f"  {err_type} — waiting {wait}s before retry ({attempt+1}/{max_retries})...", flush=True)
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

    body         = response.json()
    person_attrs = body["data"]["attributes"]
    included     = body.get("included", [])

    phones    = [i for i in included if i["type"] == "PhoneNumber"]
    addresses = [i for i in included if i["type"] == "Address"]

    primary_phone = next(
        (p["attributes"]["number"] for p in phones if p["attributes"].get("primary")),
        phones[0]["attributes"]["number"] if phones else ""
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

    GRADE_MAP = {
        -2: "Nursery", -1: "Pre-K", 0: "Kinder",
        1: "1°",  2: "2°",  3: "3°",  4: "4°",  5: "5°",  6: "6°",
        7: "7°",  8: "8°",  9: "9°", 10: "10°", 11: "11°", 12: "12°",
    }
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


# ── Data helpers ──────────────────────────────────────────────────────────────

def _fecha_es(dt=None):
    dt = dt or datetime.now()
    return (f"Generado el {dt.day} de {MESES_ES[dt.month]} de {dt.year} "
            f"a las {dt.strftime('%H:%M')}")


def _fmt_birthday(raw):
    if not raw:
        return ""
    import re
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', raw.strip())
    return f"{m.group(2)}/{m.group(3)}/{m.group(1)}" if m else raw


def _age_from_birthday(birthday_raw):
    if not birthday_raw:
        return None
    import re
    from datetime import date
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', birthday_raw.strip())
    if not m:
        return None
    try:
        dob   = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except ValueError:
        return None


def _is_minor(birthday_raw):
    age = _age_from_birthday(birthday_raw)
    return age is not None and age < 18


def _resolve_grade(pco_grade, birthday_raw):
    age = _age_from_birthday(birthday_raw)
    if age is not None:
        if age <= 2: return "Nursery"
        if age == 3: return "3 años"
        if age == 4: return "4 años"
    return pco_grade or ""


def _is_bad_address(addr):
    if not addr or not addr.strip():
        return True
    import re
    if re.fullmatch(r'[\w\s]+,?\s*tx[\s,]*\d*', addr.strip().lower()):
        return True
    return False


def _extract_apt(address):
    import re
    if not address:
        return ""
    m = re.search(r'(?:apto?\.?\s*#?\s*|#\s*)(\d+\w*)', address, re.IGNORECASE)
    if m:
        return m.group(1)
    m2 = re.search(r',\s*(\d+[A-Za-z]?)\s*,', address)
    return m2.group(1) if m2 else ""


def _parse_apt_number(address):
    import re
    token = _extract_apt(address)
    if token:
        digits = re.match(r'(\d+)', token)
        return (int(digits.group(1)) if digits else 9999, token)
    return (9999, "")


def _complex_key(address):
    import re
    if not address:
        return ""
    cleaned = re.sub(r',?\s*(?:apto?\.?\s*#?\s*|#\s*)?\d+\w*\s*(?=,)', ',',
                     address, flags=re.IGNORECASE)
    parts = [p.strip() for p in cleaned.split(',')]
    return parts[0].lower() if parts else address.lower()


def _street_only(address):
    import re
    if not address:
        return ""
    cleaned = re.sub(r',\s*(?:apto?\.?\s*#?\s*|#\s*)?\d+\w*(?=\s*,)', '',
                     address, flags=re.IGNORECASE)
    return cleaned.strip().strip(',').strip()


def _rows_available(is_first_page):
    if is_first_page:
        content_h = PAGE_H - 2*MARGIN - HEADER_H - ADDR_BAR_H - COL_HDR_H - FOOTER_H
    else:
        content_h = PAGE_H - 2*MARGIN - ADDR_BAR_H - COL_HDR_H - FOOTER_H
    return int(content_h / ROW_H)


# ── PDF draw primitives ───────────────────────────────────────────────────────

def _draw_page_header(c, title, subtitle, gen_dt, visitor_count=0):
    top    = PAGE_H - MARGIN
    logo_h = 22
    logo_w = logo_h * (300 / 58)
    if os.path.exists(LOGO_PATH):
        c.drawImage(LOGO_PATH, MARGIN, top - logo_h,
                    width=logo_w, height=logo_h, mask='auto')
        title_x = MARGIN + logo_w + 12
    else:
        title_x = MARGIN

    # Campaign: tinted background strip across header area
    campaign = _theme["campaign"]
    if campaign:
        c.setFillColor(T("col_header"))
        c.setFillAlpha(0.10)
        c.rect(0, PAGE_H - MARGIN - HEADER_H - 2, PAGE_W, HEADER_H + 2, fill=1, stroke=0)
        c.setFillAlpha(1)

    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(T("title"))
    c.drawString(title_x, top - 15, title)

    c.setFont("Helvetica", 8)
    c.setFillColor(T("subtitle"))
    c.drawString(title_x, top - 27, subtitle)

    # Campaign name — centered, larger
    if campaign:
        emoji = _theme["emoji"]
        label = f"{emoji}  {campaign}  {emoji}".strip()
        c.setFont("Helvetica-BoldOblique", 11)
        c.setFillColor(T("addr_bar"))
        c.drawCentredString(PAGE_W / 2, top - 20, label)

    # Visitor count top-right
    if visitor_count:
        vlabel = (f"★  {visitor_count} "
                  f"visitante{'s' if visitor_count != 1 else ''} "
                  f"nuevo{'s' if visitor_count != 1 else ''} esta semana")
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(GOLD_STAR)
        c.drawRightString(PAGE_W - MARGIN, top - 10, vlabel)
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#888888"))
        c.drawRightString(PAGE_W - MARGIN, top - 21, _fecha_es(gen_dt))
    else:
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#888888"))
        c.drawRightString(PAGE_W - MARGIN, top - 10, _fecha_es(gen_dt))

    # Single clean rule
    rule_y = top - HEADER_H + 4
    c.setStrokeColor(T("rule"))
    c.setLineWidth(1.5)
    c.line(MARGIN, rule_y, PAGE_W - MARGIN, rule_y)
    return rule_y - 4


def _draw_page_footer(c, page_num):
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(T("footer_text"))
    c.drawString(MARGIN, MARGIN - 14, VERSE_TEXT)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(MARGIN, MARGIN - 23, VERSE_REF)
    c.setFillColor(GOLD_STAR)
    c.circle(PAGE_W - MARGIN - 120, MARGIN - 15, 3, fill=1, stroke=0)
    c.setFont("Helvetica-Oblique", 6.5)
    c.setFillColor(colors.HexColor("#888888"))
    c.drawString(PAGE_W - MARGIN - 114, MARGIN - 18, "= nuevo esta semana")
    c.setFont("Helvetica", 7)
    c.drawRightString(PAGE_W - MARGIN, MARGIN - 18, f"Página {page_num}")
    c.setStrokeColor(T("rule"))
    c.setLineWidth(0.8)
    c.line(MARGIN, MARGIN - 4, PAGE_W - MARGIN, MARGIN - 4)


def _draw_address_bar(c, display_addr, y):
    c.setFillColor(T("addr_bar"))
    c.roundRect(MARGIN, y - ADDR_BAR_H, USABLE_W, ADDR_BAR_H, 3, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(WHITE)
    label = (f"Grupo de Dirección: {display_addr}"
             if display_addr else "Grupo de Dirección: (sin dirección registrada)")
    c.drawString(MARGIN + 8, y - ADDR_BAR_H + 6, label)
    return y - ADDR_BAR_H


def _draw_column_headers(c, y, col_widths=None, headers=None):
    col_widths = col_widths or COL_WIDTHS
    headers    = headers    or HEADERS_ES
    c.setFillColor(T("col_header"))
    c.rect(MARGIN, y - COL_HDR_H, USABLE_W, COL_HDR_H, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(WHITE)
    x = MARGIN
    for header, col_w in zip(headers, col_widths):
        if header:
            c.drawString(x + 4, y - COL_HDR_H + 5, header)
        x += col_w
    return y - COL_HDR_H


def _draw_data_row(c, y, row_data, row_index, warn_flags,
                   is_visitor=False, col_widths=None):
    col_widths = col_widths or COL_WIDTHS
    base_bg    = WHITE if row_index % 2 == 0 else T("row_alt")
    x = MARGIN

    for i, (col_w, warn) in enumerate(zip(col_widths, warn_flags)):
        c.setFillColor(base_bg if i == 0 else (YELLOW_WARN if warn else base_bg))
        c.rect(x, y - ROW_H, col_w, ROW_H, fill=1, stroke=0)
        x += col_w

    c.setStrokeColor(GREY_LINE)
    c.setLineWidth(0.3)
    c.rect(MARGIN, y - ROW_H, USABLE_W, ROW_H, fill=0, stroke=1)
    x = MARGIN
    for col_w in col_widths[:-1]:
        x += col_w
        c.line(x, y, x, y - ROW_H)

    if is_visitor:
        c.setFillColor(GOLD_STAR)
        c.circle(MARGIN + col_widths[0] / 2, y - ROW_H / 2, 4, fill=1, stroke=0)

    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)
    x = MARGIN + col_widths[0]
    for val, col_w in zip(row_data[1:], col_widths[1:]):
        text = str(val) if val else ""
        c.drawString(x + 4, y - ROW_H + 5, text[:int(col_w / 5.2)])
        x += col_w

    return y - ROW_H



# ── Address-grouped PDF (Rutas → Direcciones-Roster.pdf) ─────────────────────

def generate_address_pdf(location_name, attendees, filename="Direcciones-Roster.pdf"):
    visitor_count = sum(1 for p in attendees if p.get("is_visitor"))
    c      = rl_canvas.Canvas(filename, pagesize=landscape(letter))
    gen_dt = datetime.now()

    complex_groups = defaultdict(list)
    for person in attendees:
        addr = (person.get("address") or "").strip()
        complex_groups[_complex_key(addr)].append(person)
    for key in complex_groups:
        complex_groups[key].sort(key=lambda p: _parse_apt_number(p.get("address") or ""))
    sorted_groups = sorted(
        complex_groups.items(),
        key=lambda kv: (0, kv[0]) if kv[0] else (1, "")
    )

    page_num    = 1
    first_group = True

    def new_page(is_first):
        if not is_first:
            c.showPage()
        return _draw_page_header(c, location_name, "Ministerio de Autobuses",
                                 gen_dt, visitor_count)

    cursor_y  = new_page(is_first=True)
    rows_left = _rows_available(is_first_page=True)

    for group_key, group_people in sorted_groups:
        raw_addr = (group_people[0].get("address") or "").strip() if group_people else ""
        bar_addr = _street_only(raw_addr)
        needed   = len(group_people) + MIN_EMPTY_ROWS + 1

        if rows_left < needed and not first_group:
            _draw_page_footer(c, page_num)
            page_num += 1
            cursor_y  = new_page(is_first=False)
            rows_left = _rows_available(is_first_page=False)

        first_group = False
        cursor_y    = _draw_address_bar(c, bar_addr, cursor_y)
        cursor_y    = _draw_column_headers(c, cursor_y)
        rows_left  -= 1
        row_index   = 0

        for person in group_people:
            if rows_left <= 0:
                _draw_page_footer(c, page_num)
                page_num  += 1
                cursor_y   = new_page(is_first=False)
                cursor_y   = _draw_address_bar(c, bar_addr, cursor_y)
                cursor_y   = _draw_column_headers(c, cursor_y)
                rows_left  = _rows_available(is_first_page=False) - 1
                row_index  = 0

            fn, ln   = person.get("first_name",""), person.get("last_name","")
            addr     = person.get("address","")
            bday_raw = person.get("birthday","")
            bday     = _fmt_birthday(bday_raw)
            ph       = person.get("phone","")
            grade    = _resolve_grade(person.get("grade",""), bday_raw)
            apt      = _extract_apt(addr)
            addr_d   = _street_only(addr)
            attend   = person.get("attendance", "")
            is_v     = person.get("is_visitor", False)

            grade_warn = _is_minor(bday_raw) and not grade
            warn = [False, not fn, not ln, not bday, not ph,
                    grade_warn, False, False, _is_bad_address(addr)]

            cursor_y  = _draw_data_row(c, cursor_y,
                                       ["", fn, ln, bday, ph, grade, apt, attend, addr_d],
                                       row_index, warn, is_visitor=is_v)
            rows_left -= 1
            row_index += 1

        if rows_left < MIN_EMPTY_ROWS:
            _draw_page_footer(c, page_num)
            page_num  += 1
            cursor_y   = new_page(is_first=False)
            cursor_y   = _draw_address_bar(c, bar_addr, cursor_y)
            cursor_y   = _draw_column_headers(c, cursor_y)
            rows_left  = _rows_available(is_first_page=False) - 1
            row_index  = 0

        for _ in range(min(MIN_EMPTY_ROWS, rows_left)):
            cursor_y  = _draw_data_row(c, cursor_y,
                                       ["","","","","","","","", bar_addr],
                                       row_index, [False]*9)
            row_index += 1
            rows_left -= 1

    _draw_page_footer(c, page_num)
    c.save()
    return filename


# ── Simple alphabetical roster PDF (Rutas → Lista.pdf + Escuela Dominical) ───

def generate_simple_roster_pdf(location_name, subtitle, attendees,
                                filename="Lista.pdf"):
    """
    Alphabetical roster — no address grouping, no empty rows.
    Gold dot marks people added to PCO within the last 7 days (visitors).
    """
    visitor_count = sum(1 for p in attendees if p.get("is_visitor"))
    c      = rl_canvas.Canvas(filename, pagesize=landscape(letter))
    gen_dt = datetime.now()

    rows_per_page = int((PAGE_H - 2*MARGIN - HEADER_H - COL_HDR_H - FOOTER_H) / ROW_H)

    sorted_attendees = sorted(
        attendees,
        key=lambda p: (p.get("last_name","").lower(), p.get("first_name","").lower())
    )

    def new_page(is_first):
        if not is_first:
            c.showPage()
        return _draw_page_header(c, location_name, subtitle, gen_dt, visitor_count)

    cursor_y  = new_page(is_first=True)
    cursor_y  = _draw_column_headers(c, cursor_y, SR_COL_WIDTHS, SR_HEADERS)
    rows_left = rows_per_page
    page_num  = 1
    row_index = 0

    for person in sorted_attendees:
        if rows_left <= 0:
            _draw_page_footer(c, page_num)
            page_num  += 1
            cursor_y   = new_page(is_first=False)
            cursor_y   = _draw_column_headers(c, cursor_y, SR_COL_WIDTHS, SR_HEADERS)
            rows_left  = rows_per_page
            row_index  = 0

        fn, ln   = person.get("first_name",""), person.get("last_name","")
        addr     = person.get("address","")
        bday_raw = person.get("birthday","")
        bday     = _fmt_birthday(bday_raw)
        ph       = person.get("phone","")
        grade    = _resolve_grade(person.get("grade",""), bday_raw)
        apt      = _extract_apt(addr)
        addr_d   = _street_only(addr)
        attend   = person.get("attendance", "")
        is_v     = person.get("is_visitor", False)

        grade_warn = _is_minor(bday_raw) and not grade
        warn = [False, not fn, not ln, not bday, not ph,
                grade_warn, False, False, _is_bad_address(addr)]

        cursor_y  = _draw_data_row(c, cursor_y,
                                   ["", fn, ln, bday, ph, grade, apt, attend, addr_d],
                                   row_index, warn, is_visitor=is_v,
                                   col_widths=SR_COL_WIDTHS)
        rows_left -= 1
        row_index += 1

    _draw_page_footer(c, page_num)
    c.save()
    return filename


# ── Google Drive helpers ──────────────────────────────────────────────────────

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
    results = service.files().list(
        q=query, supportsAllDrives=True, includeItemsFromAllDrives=True
    ).execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']
    metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    return service.files().create(
        body=metadata, fields='id', supportsAllDrives=True
    ).execute()['id']


def upload_and_replace(service, folder_id, local_path, drive_name=None):
    """Upload local_path to Drive, overwriting any existing file with the same name."""
    drive_name = drive_name or os.path.basename(local_path)
    query      = f"name='{drive_name}' and '{folder_id}' in parents and trashed=false"
    results    = service.files().list(
        q=query, supportsAllDrives=True, includeItemsFromAllDrives=True
    ).execute()
    files = results.get('files', [])
    media = MediaFileUpload(local_path, mimetype='application/pdf')
    if files:
        service.files().update(
            fileId=files[0]['id'], media_body=media, supportsAllDrives=True
        ).execute()
    else:
        service.files().create(
            body={'name': drive_name, 'parents': [folder_id]},
            media_body=media, supportsAllDrives=True
        ).execute()


# ── Check-in processing ───────────────────────────────────────────────────────

def _build_attendees(checkins, included, total_weeks=5):
    location_lookup = {
        item["id"]: item["attributes"]["name"]
        for item in included if item["type"] == "Location"
    }
    person_lookup = {
        item["id"]: item
        for item in included if item["type"] == "Person"
    }

    # First pass: count distinct event periods per (person_id, location)
    attendance_counts = defaultdict(set)  # (person_id, location_name) → set of ep_ids
    for checkin in checkins:
        location_data = checkin["relationships"]["locations"]["data"]
        if not location_data:
            continue
        location_id   = location_data[0]["id"]
        location_name = location_lookup.get(location_id, "Unknown Location")
        person_rel    = checkin["relationships"].get("person", {}).get("data")
        person_id     = person_rel["id"] if person_rel else None
        ep_id = checkin.get("relationships", {}).get("event_period", {}).get("data", {}).get("id")
        if person_id and ep_id:
            attendance_counts[(person_id, location_name)].add(ep_id)

    # Second pass: build deduplicated records
    grouped      = defaultdict(list)
    seen         = defaultdict(set)
    unique_count = 0
    skip_count   = 0

    for checkin in checkins:
        location_data = checkin["relationships"]["locations"]["data"]
        if not location_data:
            continue

        location_id   = location_data[0]["id"]
        location_name = location_lookup.get(location_id, "Unknown Location")

        person_rel = checkin["relationships"].get("person", {}).get("data")
        person_id  = person_rel["id"] if person_rel else None

        if person_id and person_id in seen[location_name]:
            skip_count += 1
            continue
        if person_id:
            seen[location_name].add(person_id)

        # Attendance rate: how many of the N weeks did they show up?
        weeks_attended = len(attendance_counts.get((person_id, location_name), set()))
        attendance_str = f"{weeks_attended}/{total_weeks}" if person_id else ""

        record = {
            "person_id":   person_id,
            "first_name":  checkin["attributes"]["first_name"],
            "last_name":   checkin["attributes"]["last_name"],
            "phone":       "",
            "address":     "",
            "birthday":    "",
            "grade":       "",
            "created_at":  "",
            "is_visitor":  False,
            "attendance":  attendance_str,
        }

        if person_id:
            sideloaded = person_lookup.get(person_id)
            if sideloaded:
                record["birthday"] = sideloaded["attributes"].get("birthdate") or ""

            if person_id not in _person_cache:
                print(f"  [{unique_count + 1}] Fetching {record['first_name']} "
                      f"{record['last_name']} (id: {person_id})...", flush=True)
                time.sleep(0.5)
            else:
                print(f"  [{unique_count + 1}] Cached: "
                      f"{record['first_name']} {record['last_name']}", flush=True)

            details = get_person_details(person_id)
            record.update({k: v for k, v in details.items()})
            # Restore attendance after update (get_person_details doesn't return it)
            record["attendance"] = attendance_str

            # Visitor = added to PCO within the last 7 days
            created_str = record.get("created_at", "")
            if created_str:
                try:
                    created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    record["is_visitor"] = (datetime.now(timezone.utc) - created_dt).days < 7
                except Exception:
                    pass

        unique_count += 1
        grouped[location_name].append(record)

    print(f"  Processed {unique_count} unique, skipped {skip_count} duplicates.", flush=True)
    return grouped, location_lookup


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate PCO check-in rosters and upload to Google Drive."
    )
    parser.add_argument(
        "event_name",
        help="PCO event name: 'Rutas' or 'Escuela Dominical'"
    )
    parser.add_argument(
        "--weeks", type=int, default=5,
        help="Number of recent weeks to include (default: 5)"
    )
    parser.add_argument(
        "--theme",
        choices=["primavera", "verano", "otono", "invierno"],
        default=None,
        help="Optional campaign theme: primavera, verano, otono, invierno"
    )
    args = parser.parse_args()

    # Apply theme globally before any PDF generation
    global _theme
    _theme = THEMES[args.theme]
    if args.theme:
        print(f"Theme: {_theme['campaign']}", flush=True)

    event_name = args.event_name

    # ── RUTAS ──────────────────────────────────────────────────────────────────
    if event_name == "Rutas":
        print("Finding event 'Rutas'...", flush=True)
        event_id = get_event_id("Rutas")
        print("Event ID:", event_id, flush=True)

        print(f"Finding recent event periods (last {args.weeks} weeks)...", flush=True)
        event_period_ids = get_recent_event_periods(event_id, weeks=args.weeks)

        print("Fetching check-ins...", flush=True)
        checkins, included = get_checkins_for_event_periods(event_id, event_period_ids)

        grouped, location_lookup = _build_attendees(checkins, included, args.weeks)
        print(f"Locations found: {list(location_lookup.values())}", flush=True)

        print("\nConnecting to Google Drive...", flush=True)
        drive_service = get_drive_service()

        for location_name, attendees in grouped.items():
            vc = sum(1 for p in attendees if p.get("is_visitor"))
            print(f"\nGenerating PDFs for {location_name} "
                  f"({len(attendees)} attendees, {vc} new this week)...", flush=True)

            addr_pdf  = generate_address_pdf(location_name, attendees, "Direcciones-Roster.pdf")
            lista_pdf = generate_simple_roster_pdf(
                location_name, "Ministerio de Autobuses", attendees, "Roster.pdf"
            )

            folder_id = get_or_create_folder(
                drive_service, GOOGLE_DRIVE_PARENT_FOLDER_ID, location_name
            )
            upload_and_replace(drive_service, folder_id, addr_pdf,  "Direcciones-Roster.pdf")
            upload_and_replace(drive_service, folder_id, lista_pdf, "Roster.pdf")
            os.remove(addr_pdf)
            os.remove(lista_pdf)
            print(f"  ✓ Uploaded Direcciones-Roster.pdf + Roster.pdf for {location_name}", flush=True)

    # ── ESCUELA DOMINICAL ──────────────────────────────────────────────────────
    elif event_name == "Escuela Dominical":
        print("Finding event 'Escuela Dominical'...", flush=True)
        ed_event_id = get_event_id("Escuela Dominical")
        print("Event ID:", ed_event_id, flush=True)

        print(f"Finding recent event periods (last {args.weeks} weeks)...", flush=True)
        ed_period_ids = get_recent_event_periods(ed_event_id, weeks=args.weeks)

        print("Fetching Escuela Dominical check-ins...", flush=True)
        ed_checkins, ed_included = get_checkins_for_event_periods(
            ed_event_id, ed_period_ids
        )
        ed_grouped, ed_loc_lookup = _build_attendees(ed_checkins, ed_included, args.weeks)
        print(f"Locations found: {list(ed_loc_lookup.values())}", flush=True)

        print("\nConnecting to Google Drive...", flush=True)
        drive_service = get_drive_service()

        for location_name, attendees in ed_grouped.items():
            vc = sum(1 for p in attendees if p.get("is_visitor"))
            print(f"\nGenerating roster for {location_name} "
                  f"({len(attendees)} attendees, {vc} new this week)...", flush=True)

            pdf_file = generate_simple_roster_pdf(
                location_name, "Escuela Dominical", attendees, "Roster.pdf"
            )
            folder_id = get_or_create_folder(
                drive_service, GOOGLE_DRIVE_PARENT_FOLDER_ID, location_name
            )
            upload_and_replace(drive_service, folder_id, pdf_file, "Roster.pdf")
            os.remove(pdf_file)
            print(f"  ✓ Uploaded Roster.pdf for {location_name}", flush=True)

    else:
        print(f"Unknown event '{event_name}'. Supported: 'Rutas', 'Escuela Dominical'",
              flush=True)
        sys.exit(1)

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()