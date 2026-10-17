# planning_center_reports/config.py
#
# Central configuration: environment variables, layout constants, colour palettes,
# and the active-theme system. Every other module that needs a constant or colour
# should import it from here rather than defining its own copy.
#
# The _theme global and T() helper are defined here so that cli.py can switch the
# theme once (config._theme = config.THEMES["primavera"]) and every PDF function
# picks up the change automatically — because T() reads _theme from this module's
# namespace at call time, not at import time.

import os
from pathlib import Path

from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter

# Search for .env starting from the package → backend/ → project root.
# This handles: local dev (root .env), Docker (env vars injected, no .env needed).
load_dotenv(Path(__file__).parent.parent.parent / ".env")  # project root
load_dotenv(Path(__file__).parent.parent / ".env")         # backend/ (overrides if present)

# ── Credentials (loaded from .env locally; injected as secrets on Cloud Run) ──
PCO_APP_ID                    = os.getenv("PCO_APP_ID")
PCO_SECRET                    = os.getenv("PCO_SECRET")
GOOGLE_DRIVE_PARENT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID")

BASE_URL = "https://api.planningcenteronline.com"

# ── File paths ────────────────────────────────────────────────────────────────
# Resolved relative to this file so paths work both locally and inside Docker.
_HERE      = os.path.abspath(os.path.dirname(__file__))
_ROOT      = os.path.dirname(_HERE)            # project root (one level up)
LOGO_PATH  = os.path.join(_ROOT, "logo.png")
ASSETS_DIR = os.path.join(_ROOT, "assets")    # theme image assets

# ── Church locale ─────────────────────────────────────────────────────────────
# Check-in timestamps arrive in UTC; arrival times and Sunday dates are shown in
# the church's local time.
CHURCH_TIMEZONE = os.getenv("CHURCH_TIMEZONE", "America/Chicago")

# Video walkthrough linked (and QR-coded) on the Instrucciones.pdf cover page.
CHECKIN_VIDEO_URL = os.getenv(
    "CHECKIN_VIDEO_URL",
    "https://drive.google.com/file/d/1yTSZM-FTPZHbKlRrMizAm06eUM-E6Mc4/view",
)
# Feedback form linked from every PDF — questions, confusion, ideas, venting.
FEEDBACK_FORM_URL = os.getenv(
    "FEEDBACK_FORM_URL",
    "https://docs.google.com/forms/d/e/1FAIpQLSfSflUQmzCsL1TekFt_lQVCddGIInJw0QRoBjE8f6VrX0Hz6g/viewform",
)
# Who volunteers should find when the app can't sort something out.
CHECKIN_HELP_CONTACT = os.getenv("CHECKIN_HELP_CONTACT", "Hna. Lira — cuarto de impresoras")

# ── Page layout (landscape Letter = 792 × 612 pts) ───────────────────────────
PAGE_W, PAGE_H = landscape(letter)
MARGIN         = 36
USABLE_W       = PAGE_W - 2 * MARGIN          # 720 pts

HEADER_H       = 46    # height of the logo + title area
COL_HDR_H      = 18    # height of a table's column header row
ROW_H          = 17    # height of each data row
FOOTER_H       = 24    # height of the footer area

# ── Fixed colours (never change with theme) ───────────────────────────────────
WHITE       = colors.white
GREY_LINE   = colors.HexColor("#CCCCCC")
YELLOW_WARN = colors.HexColor("#FFF3B0")   # missing-data highlight
GOLD_STAR   = colors.HexColor("#F5A623")   # default visitor dot
INK         = colors.HexColor("#1F2937")   # body text
MUTED       = colors.HexColor("#6B7280")   # captions, secondary text
TILE_BG     = colors.HexColor("#F5F7FA")   # stat-tile background

# Status accents shared by every theme, so "good / watch / late" reads the same
# whatever campaign is running.
ACCENT_OK    = colors.HexColor("#2E7D32")  # early / new / healthy
ACCENT_SOFT  = colors.HexColor("#3F9A45")  # a little early
ACCENT_WARN  = colors.HexColor("#E08A00")  # slightly late / follow up
ACCENT_LATE  = colors.HexColor("#C62828")  # late

# ── Footer text ───────────────────────────────────────────────────────────────
VERSE_TEXT     = os.getenv(
    "CHURCH_VERSE_TEXT",
    '"Id por todo el mundo y predicad el evangelio a toda criatura"',
)
VERSE_REF      = os.getenv("CHURCH_VERSE_REF", "Marcos 16:15 — RV1960")
RUTAS_SUBTITLE = os.getenv("RUTAS_SUBTITLE", "Ministerio de Autobuses")

# ── Spanish month names (used when printing the generation date) ──────────────
MESES_ES = {
    1: "enero",     2: "febrero",   3: "marzo",     4: "abril",
    5: "mayo",      6: "junio",     7: "julio",      8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

MESES_ABREV = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}

# ── Colour palettes ───────────────────────────────────────────────────────────
# Each theme is a dict with the keys used by T() throughout the PDF code.
#
# visitor_icon  — filename within ASSETS_DIR to use instead of the gold dot.
#                 Set to None to keep the default gold dot.
# campaign_icon — filename within ASSETS_DIR to display beside the campaign
#                 label in the page header. Set to None for no image.
THEMES = {
    # Default navy/blue — no campaign label
    None: {
        "title":         colors.HexColor("#0D1F5C"),
        "subtitle":      colors.HexColor("#1a4b9c"),
        "col_header":    colors.HexColor("#4A90D9"),
        "row_alt":       colors.HexColor("#EEF4FB"),
        "addr_bar":      colors.HexColor("#2255aa"),
        "rule":          colors.HexColor("#4A90D9"),
        "footer_text":   colors.HexColor("#0D1F5C"),
        "campaign":      None,
        "emoji":         "",
        "visitor_icon":  None,
        "campaign_icon": None,
    },
    "primavera": {
        "title":         colors.HexColor("#1B5E20"),
        "subtitle":      colors.HexColor("#388E3C"),
        "col_header":    colors.HexColor("#43A047"),
        "row_alt":       colors.HexColor("#E8F5E9"),
        "addr_bar":      colors.HexColor("#2E7D32"),
        "rule":          colors.HexColor("#81C784"),
        "footer_text":   colors.HexColor("#1B5E20"),
        "campaign":      "Campaña de Primavera",
        "emoji":         "⚽",
        "visitor_icon":  "SoccerBall.png",   # replaces gold dot for visitors
        "campaign_icon": "gold_medal.png",   # shown beside campaign label
    },
    "verano": {
        "title":         colors.HexColor("#BF360C"),
        "subtitle":      colors.HexColor("#E64A19"),
        "col_header":    colors.HexColor("#FF7043"),
        "row_alt":       colors.HexColor("#FBE9E7"),
        "addr_bar":      colors.HexColor("#D84315"),
        "rule":          colors.HexColor("#FFAB91"),
        "footer_text":   colors.HexColor("#BF360C"),
        "campaign":      "Campaña de Verano",
        "emoji":         "☀️",
        "visitor_icon":  None,
        "campaign_icon": None,
    },
    "otono": {
        "title":         colors.HexColor("#4E342E"),
        "subtitle":      colors.HexColor("#6D4C41"),
        "col_header":    colors.HexColor("#8D6E63"),
        "row_alt":       colors.HexColor("#EFEBE9"),
        "addr_bar":      colors.HexColor("#5D4037"),
        "rule":          colors.HexColor("#BCAAA4"),
        "footer_text":   colors.HexColor("#4E342E"),
        "campaign":      "Campaña de Otoño",
        "emoji":         "🍂",
        "visitor_icon":  None,
        "campaign_icon": None,
    },
    "invierno": {
        "title":         colors.HexColor("#1A237E"),
        "subtitle":      colors.HexColor("#3949AB"),
        "col_header":    colors.HexColor("#5C6BC0"),
        "row_alt":       colors.HexColor("#E8EAF6"),
        "addr_bar":      colors.HexColor("#283593"),
        "rule":          colors.HexColor("#9FA8DA"),
        "footer_text":   colors.HexColor("#1A237E"),
        "campaign":      "Campaña de Invierno",
        "emoji":         "❄️",
        "visitor_icon":  None,
        "campaign_icon": None,
    },
}

# ── Active theme ──────────────────────────────────────────────────────────────
# Set once in cli.py before any PDF functions are called.
# All modules import T() from here; reassigning _theme here updates them all.
_theme = THEMES[None]


def T(key):
    """Return the value for `key` from the currently active theme."""
    return _theme[key]
