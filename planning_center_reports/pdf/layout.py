# planning_center_reports/pdf/layout.py
#
# Low-level PDF drawing primitives. Every function here takes a ReportLab
# Canvas as its first argument and draws a single visual element onto it.
#
# None of these functions save or show pages — that is left to rosters.py so
# the page-break logic stays in one place. Functions that advance the vertical
# cursor return the new Y position.
#
# Colours and layout constants are read from config.py through the T() helper
# so themes are applied automatically without passing theme state around.

import os

from reportlab.lib import colors

import planning_center_reports.config as cfg
from planning_center_reports.config import (
    ASSETS_DIR,
    ADDR_BAR_H,
    COL_HDR_H,
    FOOTER_H,
    GOLD_STAR,
    GREY_LINE,
    HEADER_H,
    LOGO_PATH,
    MARGIN,
    MESES_ES,
    PAGE_H,
    PAGE_W,
    ROW_H,
    USABLE_W,
    VERSE_REF,
    VERSE_TEXT,
    WHITE,
    YELLOW_WARN,
    T,
)


# ── Date helper ───────────────────────────────────────────────────────────────

def _fecha_es(dt=None) -> str:
    """Return a Spanish-language generation timestamp string.

    Example: "Generado el 15 de marzo de 2026 a las 10:32"
    """
    from datetime import datetime
    dt = dt or datetime.now()
    return (
        f"Generado el {dt.day} de {MESES_ES[dt.month]} de {dt.year} "
        f"a las {dt.strftime('%H:%M')}"
    )


# ── Layout helper ─────────────────────────────────────────────────────────────

def _rows_available(is_first_page: bool) -> int:
    """Return the number of data rows that fit in the content area of a page.

    The first page is shorter because the full header (logo + title) is drawn
    there; subsequent pages omit the header.
    """
    if is_first_page:
        content_h = PAGE_H - 2 * MARGIN - HEADER_H - ADDR_BAR_H - COL_HDR_H - FOOTER_H
    else:
        content_h = PAGE_H - 2 * MARGIN - ADDR_BAR_H - COL_HDR_H - FOOTER_H
    return int(content_h / ROW_H)


# ── Draw primitives ───────────────────────────────────────────────────────────

def _draw_page_header(c, title: str, subtitle: str, gen_dt, visitor_count: int = 0) -> float:
    """Draw the page header: logo, title, subtitle, campaign label, visitor count,
    and generation date. Returns the Y coordinate of the bottom of the header rule."""
    top    = PAGE_H - MARGIN
    logo_h = 22
    logo_w = logo_h * (300 / 58)   # maintain the logo's original aspect ratio

    if os.path.exists(LOGO_PATH):
        c.drawImage(LOGO_PATH, MARGIN, top - logo_h, width=logo_w, height=logo_h, mask="auto")
        title_x = MARGIN + logo_w + 12
    else:
        title_x = MARGIN

    # Tinted background strip for campaign pages
    campaign = cfg._theme["campaign"]
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

    # Campaign label — centered, with optional image icons flanking the text.
    # ReportLab's built-in fonts cannot render emoji glyphs (they appear as
    # coloured boxes), so when a campaign_icon image is configured we omit the
    # emoji from the string and draw the icon on both sides instead.
    if campaign:
        campaign_icon = cfg._theme["campaign_icon"]
        icon_path     = os.path.join(ASSETS_DIR, campaign_icon) if campaign_icon else None
        icon_exists   = icon_path is not None and os.path.exists(icon_path)

        label = campaign if icon_exists else f"{cfg._theme['emoji']}  {campaign}  {cfg._theme['emoji']}".strip()
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(T("addr_bar"))
        c.drawCentredString(PAGE_W / 2, top - 20, label)

        if icon_exists:
            icon_size = 13
            label_w   = c.stringWidth(label, "Helvetica-Bold", 11)
            icon_y    = top - 20 - icon_size + 3
            c.drawImage(icon_path, PAGE_W / 2 - label_w / 2 - icon_size - 5, icon_y,
                        width=icon_size, height=icon_size, mask="auto")
            c.drawImage(icon_path, PAGE_W / 2 + label_w / 2 + 5, icon_y,
                        width=icon_size, height=icon_size, mask="auto")

    # Visitor count — top-right corner
    if visitor_count:
        vlabel = (
            f"★  {visitor_count} "
            f"visitante{'s' if visitor_count != 1 else ''} "
            f"nuevo{'s' if visitor_count != 1 else ''} esta semana"
        )
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

    # Horizontal rule below the header area
    rule_y = top - HEADER_H + 4
    c.setStrokeColor(T("rule"))
    c.setLineWidth(1.5)
    c.line(MARGIN, rule_y, PAGE_W - MARGIN, rule_y)
    return rule_y - 4


def _draw_page_footer(c, page_num: int):
    """Draw the footer: Bible verse, visitor legend, and page number."""
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(T("footer_text"))
    c.drawString(MARGIN, MARGIN - 14, VERSE_TEXT)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(MARGIN, MARGIN - 23, VERSE_REF)

    # Visitor legend icon — use theme image if available, otherwise gold dot.
    visitor_icon = cfg._theme["visitor_icon"]
    if visitor_icon:
        icon_path = os.path.join(ASSETS_DIR, visitor_icon)
        if os.path.exists(icon_path):
            icon_size = 8
            cx = PAGE_W - MARGIN - 120
            cy = MARGIN - 15
            c.drawImage(icon_path, cx - icon_size / 2, cy - icon_size / 2,
                        width=icon_size, height=icon_size, mask="auto")
        else:
            c.setFillColor(GOLD_STAR)
            c.circle(PAGE_W - MARGIN - 120, MARGIN - 15, 3, fill=1, stroke=0)
    else:
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


def _draw_address_bar(c, display_addr: str, y: float) -> float:
    """Draw the coloured address-group bar and return the new Y position."""
    c.setFillColor(T("addr_bar"))
    c.roundRect(MARGIN, y - ADDR_BAR_H, USABLE_W, ADDR_BAR_H, 3, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(WHITE)
    label = (
        f"Grupo de Dirección: {display_addr}"
        if display_addr
        else "Grupo de Dirección: (sin dirección registrada)"
    )
    c.drawString(MARGIN + 8, y - ADDR_BAR_H + 6, label)
    return y - ADDR_BAR_H


def _draw_column_headers(c, y: float, col_widths=None, headers=None) -> float:
    """Draw the column header row and return the new Y position."""
    from planning_center_reports.config import COL_WIDTHS, HEADERS_ES
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


def _draw_data_row(c, y: float, row_data: list, row_index: int, warn_flags: list,
                   is_visitor: bool = False, col_widths=None) -> float:
    """Draw one data row (background, borders, visitor icon, text).

    Returns the Y position below the row (i.e. y - ROW_H).

    Parameters
    ----------
    y           : top Y of the row
    row_data    : list of cell values; first element is always empty (icon column)
    row_index   : 0-based row index used for alternating background colours
    warn_flags  : bool list parallel to col_widths; True → yellow highlight
    is_visitor  : if True, draw the visitor marker in the first column
    col_widths  : column widths; defaults to the address-grouped layout
    """
    from planning_center_reports.config import COL_WIDTHS
    col_widths = col_widths or COL_WIDTHS
    base_bg    = WHITE if row_index % 2 == 0 else T("row_alt")
    x = MARGIN

    # Draw cell backgrounds (yellow for warned cells, theme alternating otherwise)
    for i, (col_w, warn) in enumerate(zip(col_widths, warn_flags)):
        c.setFillColor(base_bg if i == 0 else (YELLOW_WARN if warn else base_bg))
        c.rect(x, y - ROW_H, col_w, ROW_H, fill=1, stroke=0)
        x += col_w

    # Row outline and vertical column dividers
    c.setStrokeColor(GREY_LINE)
    c.setLineWidth(0.3)
    c.rect(MARGIN, y - ROW_H, USABLE_W, ROW_H, fill=0, stroke=1)
    x = MARGIN
    for col_w in col_widths[:-1]:
        x += col_w
        c.line(x, y, x, y - ROW_H)

    # Visitor marker in the first (narrow) column
    if is_visitor:
        visitor_icon = cfg._theme["visitor_icon"]
        if visitor_icon:
            icon_path = os.path.join(ASSETS_DIR, visitor_icon)
            if os.path.exists(icon_path):
                icon_size = 9
                cx = MARGIN + col_widths[0] / 2
                cy = y - ROW_H / 2
                c.drawImage(icon_path, cx - icon_size / 2, cy - icon_size / 2,
                            width=icon_size, height=icon_size, mask="auto")
            else:
                c.setFillColor(GOLD_STAR)
                c.circle(MARGIN + col_widths[0] / 2, y - ROW_H / 2, 4, fill=1, stroke=0)
        else:
            c.setFillColor(GOLD_STAR)
            c.circle(MARGIN + col_widths[0] / 2, y - ROW_H / 2, 4, fill=1, stroke=0)

    # Cell text (skip the first column — it's icon-only)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)
    x = MARGIN + col_widths[0]
    for val, col_w in zip(row_data[1:], col_widths[1:]):
        text = str(val) if val else ""
        c.drawString(x + 4, y - ROW_H + 5, text[: int(col_w / 5.2)])
        x += col_w

    return y - ROW_H
