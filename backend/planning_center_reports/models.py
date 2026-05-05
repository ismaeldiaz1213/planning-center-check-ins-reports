# planning_center_reports/models.py
#
# Data types and pure helper functions for attendee records.
#
# An "attendee" is a plain dict that flows through the whole pipeline — fetched
# from PCO, enriched with person details, then rendered into PDF rows. The
# Attendee TypedDict below documents every key that code downstream may read.
#
# The helper functions here are all pure (no I/O, no global state) so they are
# straightforward to unit-test. See tests/test_formatting.py,
# tests/test_address_parsing.py, and tests/test_grade_logic.py.

import re
from datetime import date, datetime
from typing import Optional, TypedDict

from planning_center_reports.config import MESES_ES


class Attendee(TypedDict, total=False):
    """Every field that may appear on an attendee record."""

    person_id:  Optional[str]
    first_name: str
    last_name:  str
    phone:      str
    address:    str
    birthday:   str          # raw ISO-8601 from PCO: "YYYY-MM-DD"
    grade:      str          # display string e.g. "5°", "Nursery"
    created_at: str          # ISO-8601 datetime from PCO
    is_visitor: bool         # True if added to PCO within the last 7 days
    attendance: str          # display string e.g. "3/5" (deprecated — use route)
    route:      str          # bus route name e.g. "Ruta 1 - Bus" (for Escuela Dominical)
    is_helper:  bool         # True if age 16+ and checked into Junta de Rutas


# ── Date / display helpers ────────────────────────────────────────────────────

def _fecha_es(dt: Optional[datetime] = None) -> str:
    """Return a Spanish-language date string for the PDF header.

    Example: "Generado el 15 de marzo de 2026 a las 10:32"
    """
    dt = dt or datetime.now()
    return (
        f"Generado el {dt.day} de {MESES_ES[dt.month]} de {dt.year} "
        f"a las {dt.strftime('%H:%M')}"
    )


def _fmt_birthday(raw: str) -> str:
    """Convert PCO's ISO date "YYYY-MM-DD" to display format "MM/DD/YYYY".

    Returns an empty string for missing or malformed input.
    """
    if not raw:
        return ""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw.strip())
    return f"{m.group(2)}/{m.group(3)}/{m.group(1)}" if m else raw


# ── Age / grade helpers ───────────────────────────────────────────────────────

def _age_from_birthday(birthday_raw: str) -> Optional[int]:
    """Calculate current age in years from a "YYYY-MM-DD" string.

    Returns None if the string is missing or unparseable.
    """
    if not birthday_raw:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", birthday_raw.strip())
    if not m:
        return None
    try:
        dob   = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except ValueError:
        return None


def _is_minor(birthday_raw: str) -> bool:
    """Return True if the person is under 18 years old."""
    age = _age_from_birthday(birthday_raw)
    return age is not None and age < 18


def _resolve_grade(pco_grade: str, birthday_raw: str) -> str:
    """Return a display-ready grade string.

    PCO often leaves grade blank for toddlers. For ages 0-4 we infer the
    label from the birthday so the roster doesn't show an empty cell.
    """
    age = _age_from_birthday(birthday_raw)
    if age is not None:
        if age <= 2:
            return "Nursery"
        if age == 3:
            return "3 años"
        if age == 4:
            return "4 años"
    return pco_grade or ""


# ── Address helpers ───────────────────────────────────────────────────────────

def _is_bad_address(addr: str) -> bool:
    """Return True if the address is missing or looks like a city-only entry.

    Examples of bad addresses: "", "Houston, TX", "Houston, TX 77086".
    These trigger a yellow warning cell on the PDF so staff know to update them.
    """
    if not addr or not addr.strip():
        return True
    # Match city/state-only patterns like "Houston, TX" or "Houston, TX 77086"
    return bool(re.fullmatch(r"[\w\s]+,?\s*tx[\s,]*\d*", addr.strip(), re.IGNORECASE))


def _extract_apt(address: str) -> str:
    """Extract the apartment/unit identifier from a full address string.

    Handles formats like:
      - "APT 102" → "102"
      - "Apt 41B" → "41B"
      - "#46"     → "46"
      - ", 506,"  → "506"  (bare numeric unit between commas)
    Returns an empty string if no unit is found.
    """
    if not address:
        return ""
    m = re.search(r"(?:apto?\.?\s*#?\s*|#\s*)(\d+\w*)", address, re.IGNORECASE)
    if m:
        return m.group(1)
    m2 = re.search(r",\s*(\d+[A-Za-z]?)\s*,", address)
    return m2.group(1) if m2 else ""


def _parse_apt_number(address: str) -> tuple:
    """Return a (int, str) sort key for apartment-number ordering.

    Numeric prefix is extracted so that "APT 9" sorts before "APT 10".
    Records without a unit number sort last (key = 9999).
    """
    token = _extract_apt(address)
    if token:
        digits = re.match(r"(\d+)", token)
        return (int(digits.group(1)) if digits else 9999, token)
    return (9999, "")


def _complex_key(address: str) -> str:
    """Return a normalised building identifier used to group addresses.

    Two units at the same complex — e.g. "430 Cypress Creek Pkwy, APT 46"
    and "430 Cypress Creek Pkwy, APT 13A" — should share the same group key
    so they appear under the same address bar in the PDF.
    """
    if not address:
        return ""
    # Strip the unit portion before the first comma, leaving just the street.
    cleaned = re.sub(
        r",?\s*(?:apto?\.?\s*#?\s*|#\s*)?\d+\w*\s*(?=,)",
        ",",
        address,
        flags=re.IGNORECASE,
    )
    parts = [p.strip() for p in cleaned.split(",")]
    return parts[0].lower() if parts else address.lower()


def _is_visitor_for_period(created_at_str: str, starts_at_str: str) -> bool:
    """Return True if a person was added to PCO within 7 days before a given period.

    Both arguments are ISO-8601 strings (UTC).  Returns False when either is
    missing or unparseable — no data means we cannot call them a visitor.
    """
    if not created_at_str or not starts_at_str:
        return False
    try:
        created_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        period_dt  = datetime.fromisoformat(starts_at_str.replace("Z", "+00:00"))
        delta = (period_dt - created_dt).days
        return 0 <= delta < 7
    except Exception:
        return False


def _extract_route_number(route: str) -> str:
    """Return just the numeric part of a route name.

    "Ruta 1 - Bus" → "1", "Ruta 12" → "12", "" → ""
    """
    if not route:
        return ""
    m = re.search(r"\d+", route)
    return m.group(0) if m else route


def _street_only(address: str) -> str:
    """Strip the apartment/unit portion from an address for display in the address bar.

    "430 Cypress Creek Pkwy, APT 46, Houston, TX" →
    "430 Cypress Creek Pkwy, Houston, TX"
    """
    if not address:
        return ""
    cleaned = re.sub(
        r",\s*(?:apto?\.?\s*#?\s*|#\s*)?\d+\w*(?=\s*,)",
        "",
        address,
        flags=re.IGNORECASE,
    )
    return cleaned.strip().strip(",").strip()
