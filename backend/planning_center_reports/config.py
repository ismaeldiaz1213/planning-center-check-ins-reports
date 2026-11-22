# planning_center_reports/config.py
#
# Constants shared by the whole engine: page layout, fixed colours, the theme
# palettes and where bundled assets live. Nothing here belongs to a particular
# church — a church's settings arrive as a ChurchConfig (church.py), and the
# only module that reads the environment is the single-church adapter, legacy.py.

import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter

BASE_URL = "https://api.planningcenteronline.com"

# ── File paths ────────────────────────────────────────────────────────────────
# Resolved relative to this file so paths work both locally and inside Docker.
_HERE      = os.path.abspath(os.path.dirname(__file__))
_ROOT      = os.path.dirname(_HERE)            # project root (one level up)
LOGO_PATH  = os.path.join(_ROOT, "logo.png")     # the bundled logo (legacy single-church install)
ASSETS_DIR = os.path.join(_ROOT, "assets")    # theme image assets

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

# ── Colour palettes ───────────────────────────────────────────────────────────
# Each theme is a dict with the keys the PDF code reads through RenderContext.T().
# The campaign label printed in the header comes from the church's text catalog
# (i18n "campaign.<theme>"), not from here.
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
        "emoji":         "❄️",
        "visitor_icon":  None,
        "campaign_icon": None,
    },
}
