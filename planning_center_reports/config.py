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

from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter

load_dotenv()

# ── Credentials (loaded from .env locally; injected as secrets on Cloud Run) ──
PCO_APP_ID                    = os.getenv("PCO_APP_ID")
PCO_SECRET                    = os.getenv("PCO_SECRET")
GOOGLE_DRIVE_PARENT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID")

BASE_URL = "https://api.planningcenteronline.com"

# ── File paths ────────────────────────────────────────────────────────────────
# Resolved relative to this file so paths work both locally and inside Docker.
_HERE      = os.path.abspath(os.path.dirname(__file__))
_ROOT      = os.path.dirname(_HERE)            # project root (one level up)
LOGO_PATH  = os.path.join(_ROOT, "ibl_logo.png")
ASSETS_DIR = os.path.join(_ROOT, "assets")    # theme image assets

# ── Page layout (landscape Letter = 792 × 612 pts) ───────────────────────────
PAGE_W, PAGE_H = landscape(letter)
MARGIN         = 36
USABLE_W       = PAGE_W - 2 * MARGIN          # 720 pts

HEADER_H       = 46    # height of the logo + title area
ADDR_BAR_H     = 20    # height of the address-group bar
COL_HDR_H      = 18    # height of the column header row
ROW_H          = 18    # height of each data row
MIN_EMPTY_ROWS = 5     # blank write-in rows appended to each address group
FOOTER_H       = 24    # height of the footer area

# ── Column definitions ────────────────────────────────────────────────────────
# Address-grouped roster (Direcciones-Roster.pdf) — columns sum to 720 pts.
# Order: visitor-marker | Nombre | Apellido | Cumpleaños | Teléfono | Grado | Apto. | Asist. | Dirección
COL_WIDTHS = [16, 95, 95, 65, 90, 44, 44, 36, 235]
HEADERS_ES = ["", "Nombre", "Apellido", "Cumpleaños", "Teléfono", "Grado", "Apto.", "Asist.", "Dirección"]

# Simple alphabetical roster (Roster.pdf) — slightly wider name columns.
SR_COL_WIDTHS = [16, 100, 100, 65, 95, 44, 44, 36, 220]
SR_HEADERS    = ["", "Nombre", "Apellido", "Cumpleaños", "Teléfono", "Grado", "Apto.", "Asist.", "Dirección"]

# ── Fixed colours (never change with theme) ───────────────────────────────────
WHITE       = colors.white
GREY_LINE   = colors.HexColor("#CCCCCC")
YELLOW_WARN = colors.HexColor("#FFF176")   # missing-data highlight
GOLD_STAR   = colors.HexColor("#F5A623")   # default visitor dot

# ── Footer text ───────────────────────────────────────────────────────────────
VERSE_TEXT = '"Id por todo el mundo y predicad el evangelio a toda criatura"'
VERSE_REF  = "Marcos 16:15 — RV1960"

# ── Spanish month names (used when printing the generation date) ──────────────
MESES_ES = {
    1: "enero",     2: "febrero",   3: "marzo",     4: "abril",
    5: "mayo",      6: "junio",     7: "julio",      8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

# ── Colour palettes ───────────────────────────────────────────────────────────
# Each theme is a dict with the keys used by T() throughout the PDF code.
#
# visitor_icon  — filename within ASSETS_DIR to use instead of the gold dot.
#                 Set to None to keep the default gold dot.
# campaign_icon — filename within ASSETS_DIR to display beside the campaign
#                 label in the page header. Set to None for no image.
THEMES = {
    # Default IBL navy/blue — no campaign label
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
