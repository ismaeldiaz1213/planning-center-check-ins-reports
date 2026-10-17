# planning_center_reports/pdf/layout.py
#
# Drawing primitives shared by every report: page chrome (header, footer, page
# breaks), section headings, count chips and tables.
#
# Report modules (rosters.py, volunteers.py) only describe *what* to draw —
# rows and cells — and this module decides how it looks. The style is plain on
# purpose: flat header bars, zebra rows, one accent colour from the theme.
# Colours come from config.T(), so a campaign theme restyles everything.
#
# ReportLab's built-in Helvetica only covers Latin-1, so symbols such as the
# "new" star and the attendance dots are drawn as shapes, never as glyphs.

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from datetime import datetime

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas as rl_canvas

import planning_center_reports.config as cfg
from planning_center_reports.config import (
    ASSETS_DIR,
    COL_HDR_H,
    FEEDBACK_FORM_URL,
    GOLD_STAR,
    GREY_LINE,
    INK,
    LOGO_PATH,
    MARGIN,
    MESES_ES,
    MUTED,
    ROW_H,
    VERSE_REF,
    VERSE_TEXT,
    WHITE,
    YELLOW_WARN,
    T,
)

FONT      = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITAL = "Helvetica-Oblique"

SUB_ROW_H      = 27   # data row with a second line (parent details)
GROUP_ROW_H    = 16
CONTENT_BOTTOM = MARGIN + 6
DOT_EMPTY      = colors.HexColor("#D9DEE5")


# ── Text helpers ──────────────────────────────────────────────────────────────

def fecha_es(dt: datetime | None = None) -> str:
    """"Generado el 15 de marzo de 2026 a las 10:32" """
    dt = dt or datetime.now()
    return (
        f"Generado el {dt.day} de {MESES_ES[dt.month]} de {dt.year} "
        f"a las {dt.strftime('%H:%M')}"
    )


def fit(c, text: str, width: float, font: str = FONT, size: float = 8) -> str:
    """Truncate `text` with an ellipsis so it fits `width` points."""
    text = str(text or "")
    if not text or c.stringWidth(text, font, size) <= width:
        return text
    while text and c.stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text.rstrip(" ,·") + "…"


def tint(color, amount: float):
    """Blend `color` toward white; amount 0 → white, 1 → color."""
    return colors.Color(
        1 - (1 - color.red) * amount,
        1 - (1 - color.green) * amount,
        1 - (1 - color.blue) * amount,
    )


def draw_star(c, cx: float, cy: float, r: float, color=GOLD_STAR) -> None:
    """Filled five-point star (the "new this week" marker)."""
    path = c.beginPath()
    for i in range(10):
        radius = r if i % 2 == 0 else r * 0.45
        angle  = math.pi / 2 + i * math.pi / 5
        x, y = cx + radius * math.cos(angle), cy + radius * math.sin(angle)
        (path.moveTo if i == 0 else path.lineTo)(x, y)
    path.close()
    c.setFillColor(color)
    c.drawPath(path, fill=1, stroke=0)


def draw_new_marker(c, cx: float, cy: float) -> None:
    """Theme's visitor icon if it has one, otherwise a gold star."""
    icon = cfg._theme.get("visitor_icon")
    path = os.path.join(ASSETS_DIR, icon) if icon else None
    if path and os.path.exists(path):
        c.drawImage(path, cx - 4.5, cy - 4.5, width=9, height=9, mask="auto")
    else:
        draw_star(c, cx, cy, 4.2)


def draw_qr(c, x: float, y: float, size: float, url: str) -> None:
    """QR code with its bottom-left corner at (x, y)."""
    widget = QrCodeWidget(url, barLevel="M")
    x1, y1, x2, y2 = widget.getBounds()
    drawing = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
    drawing.add(widget)
    renderPDF.draw(drawing, c, x, y)


def chip(c, x: float, y_mid: float, text: str, color, size: float = 7,
         solid: bool = False, max_w: float | None = None) -> float:
    """Small rounded label (counts, dates). Returns its width."""
    text = fit(c, text, (max_w or 999) - 10, FONT_BOLD, size)
    w = c.stringWidth(text, FONT_BOLD, size) + 10
    h = size + 5
    c.setFillColor(color if solid else tint(color, 0.16))
    c.roundRect(x, y_mid - h / 2, w, h, h / 2, fill=1, stroke=0)
    c.setFillColor(WHITE if solid else color)
    c.setFont(FONT_BOLD, size)
    c.drawString(x + 5, y_mid - size / 2 + 1.2, text)
    return w


def caps(c, x: float, y: float, text: str, size: float = 6.6, color=MUTED,
         font: str = FONT_BOLD) -> None:
    """Small letter-spaced uppercase caption (used on the instructions cover)."""
    t = c.beginText(x, y)
    t.setFont(font, size)
    t.setCharSpace(0.6)
    t.setFillColor(color)
    t.textOut(text.upper())
    t.setCharSpace(0)   # Tc persists in the PDF text state — reset it for later text
    c.drawText(t)


FEEDBACK_LABEL = "¿Dudas o ideas? Cuéntanos ›"


def feedback_link(c, x_right: float, y: float) -> None:
    """Right-aligned text link to the feedback form."""
    c.setFont(FONT_BOLD, 7)
    c.setFillColor(T("col_header"))
    c.drawRightString(x_right, y, FEEDBACK_LABEL)
    w = c.stringWidth(FEEDBACK_LABEL, FONT_BOLD, 7)
    c.linkURL(FEEDBACK_FORM_URL, (x_right - w, y - 2, x_right, y + 8), relative=0)


# ── Page chrome ───────────────────────────────────────────────────────────────

class Page:
    """One PDF document: running cursor, automatic page breaks, header/footer.

    Usage:
        page = Page(path, "Ruta 7", "Ministerio de Autobuses", ["Historial: …"])
        page.ensure(40); ...draw at page.y...; page.y -= 40
        page.save()
    """

    def __init__(self, path: str, title: str, subtitle: str, meta: list[str],
                 legend: tuple[str, ...] = ("new", "warn"), pagesize=landscape(letter)):
        self.c = rl_canvas.Canvas(path, pagesize=pagesize)
        self.c.setTitle(f"{title} — {subtitle}")
        self.c.setAuthor("Planning Center Check-Ins Reports")
        self.width, self.height = pagesize
        self.usable_w = self.width - 2 * MARGIN
        self.title, self.subtitle = title, subtitle
        self.legend = legend
        self.page_num = 1
        self.gen_dt = datetime.now()
        self.y = self._first_header(meta)

    # ── header / footer ──
    def _first_header(self, meta: list[str]) -> float:
        c, top = self.c, self.height - MARGIN
        title_x = MARGIN
        if os.path.exists(LOGO_PATH):
            logo_h = 22
            logo_w = logo_h * (300 / 58)
            c.drawImage(LOGO_PATH, MARGIN, top - logo_h, width=logo_w, height=logo_h, mask="auto")
            title_x = MARGIN + logo_w + 12

        c.setFont(FONT_BOLD, 14)
        c.setFillColor(T("title"))
        c.drawString(title_x, top - 13, fit(c, self.title, self.usable_w * 0.5, FONT_BOLD, 14))
        c.setFont(FONT, 8)
        c.setFillColor(T("subtitle"))
        c.drawString(title_x, top - 25, self.subtitle)

        campaign = cfg._theme.get("campaign")
        if campaign:
            c.setFont(FONT_BOLD, 10)
            c.setFillColor(T("addr_bar"))
            c.drawCentredString(self.width / 2, top - 18, campaign)

        c.setFont(FONT, 7)
        c.setFillColor(MUTED)
        lines = [fecha_es(self.gen_dt), *meta]
        for i, line in enumerate(lines):
            c.drawRightString(self.width - MARGIN, top - 7 - i * 9, line)
        feedback_link(c, self.width - MARGIN, top - 7 - len(lines) * 9)

        rule_y = top - 36
        c.setStrokeColor(T("rule"))
        c.setLineWidth(1.2)
        c.line(MARGIN, rule_y, self.width - MARGIN, rule_y)
        return rule_y - 10

    def _continuation_header(self) -> float:
        c, top = self.c, self.height - MARGIN
        c.setFont(FONT_BOLD, 10)
        c.setFillColor(T("title"))
        c.drawString(MARGIN, top - 8, self.title)
        w = c.stringWidth(self.title, FONT_BOLD, 10)
        c.setFont(FONT, 7.5)
        c.setFillColor(MUTED)
        c.drawString(MARGIN + w + 8, top - 8, f"{self.subtitle} · continuación")
        feedback_link(c, self.width - MARGIN, top - 8)
        rule_y = top - 15
        c.setStrokeColor(T("rule"))
        c.setLineWidth(1.2)
        c.line(MARGIN, rule_y, self.width - MARGIN, rule_y)
        return rule_y - 10

    def _footer(self) -> None:
        c = self.c
        c.setStrokeColor(T("rule"))
        c.setLineWidth(0.8)
        c.line(MARGIN, MARGIN - 4, self.width - MARGIN, MARGIN - 4)
        c.setFont(FONT_ITAL, 7)
        c.setFillColor(T("footer_text"))
        c.drawString(MARGIN, MARGIN - 14, VERSE_TEXT)
        c.setFont(FONT_BOLD, 7)
        c.drawString(MARGIN, MARGIN - 23, VERSE_REF)

        x = self.width - MARGIN - 52
        c.setFont(FONT, 7)
        c.setFillColor(MUTED)
        c.drawRightString(self.width - MARGIN, MARGIN - 17, f"Página {self.page_num}")
        for item in reversed(self.legend):
            label = {"new": "Nuevo este domingo", "warn": "Falta información"}.get(item, item)
            x -= c.stringWidth(label, FONT, 6.8) + 22
            if item == "new":
                draw_new_marker(c, x + 4, MARGIN - 15)
            elif item == "warn":
                c.setFillColor(YELLOW_WARN)
                c.setStrokeColor(GREY_LINE)
                c.rect(x, MARGIN - 19, 9, 8, fill=1, stroke=1)
            c.setFont(FONT, 6.8)
            c.setFillColor(MUTED)
            c.drawString(x + 12, MARGIN - 17.5, label)

    # ── flow ──
    def ensure(self, height: float) -> bool:
        """Start a new page if `height` points no longer fit. True if it did."""
        if self.y - height < CONTENT_BOTTOM:
            self.break_page()
            return True
        return False

    def break_page(self) -> None:
        self._footer()
        self.c.showPage()
        self.page_num += 1
        self.y = self._continuation_header()

    def save(self) -> None:
        self._footer()
        self.c.save()


# ── Sections & tables ─────────────────────────────────────────────────────────

def draw_section(page: Page, title: str, count: int | None = None, accent=None,
                 note: str = "", keep_with: float = 0) -> None:
    """Section heading: title, count chip and a muted note."""
    c = page.c
    page.ensure(22 + keep_with)
    accent = accent or T("col_header")
    y = page.y
    c.setFont(FONT_BOLD, 11)
    c.setFillColor(T("title"))
    c.drawString(MARGIN, y - 10, title)
    x = MARGIN + c.stringWidth(title, FONT_BOLD, 11) + 7
    if count is not None:
        x += chip(c, x, y - 6.3, str(count), accent, size=7.5, solid=True) + 8
    if note:
        c.setFont(FONT, 7.2)
        c.setFillColor(MUTED)
        c.drawString(x, y - 9.3, fit(c, note, page.width - MARGIN - x, FONT, 7.2))
    page.y = y - 18


@dataclass
class Column:
    header: str
    width:  float
    align:  str = "left"           # left | center | right


@dataclass
class Cell:
    text:  str = ""
    warn:  bool = False            # missing info → yellow background
    style: str | None = None       # bold | muted | chip | meter | dash
    color: object = None
    meter: tuple[int, int] = (0, 0)


@dataclass
class Row:
    cells:  list[Cell] = field(default_factory=list)
    marker: bool = False           # draw the "new" star in the first column
    sub:    list[tuple[str, str]] | None = None   # second line: [(label, text), ...]
    group:  str | None = None      # a full-width group band instead of cells


def _draw_header_row(page: Page, columns: list[Column], color, x0: float) -> None:
    c, y = page.c, page.y
    c.setFillColor(color)
    c.rect(x0, y - COL_HDR_H, sum(col.width for col in columns), COL_HDR_H, fill=1, stroke=0)
    c.setFont(FONT_BOLD, 8)
    c.setFillColor(WHITE)
    x = x0
    for col in columns:
        if col.header:
            base = y - COL_HDR_H + 5.5
            if col.align == "center":
                c.drawCentredString(x + col.width / 2, base, col.header)
            elif col.align == "right":
                c.drawRightString(x + col.width - 5, base, col.header)
            else:
                c.drawString(x + 5, base, col.header)
        x += col.width
    page.y = y - COL_HDR_H


def _draw_meter(c, x: float, y_mid: float, filled: int, total: int) -> None:
    for i in range(total):
        c.setFillColor(T("col_header") if i < filled else DOT_EMPTY)
        c.circle(x + 3 + i * 6.4, y_mid, 2.2, fill=1, stroke=0)


def _draw_cell(c, cell: Cell, col: Column, x: float, y_mid: float) -> None:
    pad, avail = 5, col.width - 10
    if cell.style == "meter":
        filled, total = cell.meter
        width = total * 6.4
        start = x + (col.width - width) / 2 if col.align == "center" else x + pad
        _draw_meter(c, start, y_mid, filled, total)
        return
    if cell.style == "chip":
        w = c.stringWidth(cell.text, FONT_BOLD, 7) + 10
        px = {"center": x + (col.width - w) / 2, "right": x + col.width - w - pad}.get(col.align, x + pad)
        chip(c, px, y_mid, cell.text, cell.color or T("col_header"), max_w=avail + 6)
        return
    font = FONT_BOLD if cell.style == "bold" else FONT
    text = "—" if cell.style == "dash" else fit(c, cell.text, avail, font, 8)
    c.setFont(font, 8)
    c.setFillColor(cell.color or (MUTED if cell.style in ("muted", "dash") else INK))
    base = y_mid - 2.8
    if col.align == "center":
        c.drawCentredString(x + col.width / 2, base, text)
    elif col.align == "right":
        c.drawRightString(x + col.width - pad, base, text)
    else:
        c.drawString(x + pad, base, text)


def table_height(rows: list[Row]) -> float:
    return COL_HDR_H + sum(GROUP_ROW_H if r.group else (SUB_ROW_H if r.sub else ROW_H) for r in rows)


def draw_table(page: Page, columns: list[Column], rows: list[Row], header_color=None,
               empty_text: str = "", x0: float = MARGIN, gap_after: float = 14) -> None:
    """Draw a table at x0, repeating its header row after every page break."""
    c = page.c
    header_color = header_color or T("col_header")
    width = sum(col.width for col in columns)
    page.ensure(COL_HDR_H + ROW_H)
    _draw_header_row(page, columns, header_color, x0)

    if not rows and empty_text:
        c.setFont(FONT_ITAL, 8)
        c.setFillColor(MUTED)
        c.drawString(x0 + 8, page.y - 13, empty_text)
        page.y -= ROW_H + 4
        return

    stripe = 0
    for row in rows:
        h = GROUP_ROW_H if row.group else (SUB_ROW_H if row.sub else ROW_H)
        # A group band never sits alone at the bottom of a page.
        if page.ensure(h + (SUB_ROW_H if row.group else 0)):
            _draw_header_row(page, columns, header_color, x0)
        y = page.y

        if row.group:
            c.setFillColor(tint(header_color, 0.14))
            c.rect(x0, y - h, width, h, fill=1, stroke=0)
            c.setFont(FONT_BOLD, 7.6)
            c.setFillColor(T("title"))
            c.drawString(x0 + 6, y - h + 5, row.group)
            page.y = y - h
            stripe = 0
            continue

        c.setFillColor(WHITE if stripe % 2 == 0 else T("row_alt"))
        c.rect(x0, y - h, width, h, fill=1, stroke=0)
        line_mid = y - ROW_H / 2 - (1 if row.sub else 0)
        x = x0
        for cell, col in zip(row.cells, columns, strict=False):
            if cell.warn:
                c.setFillColor(YELLOW_WARN)
                c.rect(x, y - ROW_H, col.width, ROW_H, fill=1, stroke=0)
            x += col.width
        if row.marker:
            draw_new_marker(c, x0 + columns[0].width / 2, line_mid)
        x = x0
        for cell, col in zip(row.cells, columns, strict=False):
            _draw_cell(c, cell, col, x, line_mid)
            x += col.width

        if row.sub:
            sx = x0 + columns[0].width + 5
            sy = y - SUB_ROW_H + 6.5
            limit = x0 + width - 6
            for i, (label, text) in enumerate(row.sub):
                if not text:
                    continue
                if label:
                    c.setFont(FONT_BOLD, 6.8)
                    c.setFillColor(T("subtitle"))
                    c.drawString(sx, sy, label)
                    sx += c.stringWidth(label, FONT_BOLD, 6.8) + 5
                c.setFont(FONT, 6.8)
                c.setFillColor(MUTED)
                shown = fit(c, text, limit - sx, FONT, 6.8)
                c.drawString(sx, sy, shown)
                sx += c.stringWidth(shown, FONT, 6.8)
                if i < len(row.sub) - 1:
                    c.drawString(sx + 4, sy, "·")
                    sx += 12
                if sx >= limit:
                    break

        c.setStrokeColor(GREY_LINE)
        c.setLineWidth(0.3)
        c.line(x0, y - h, x0 + width, y - h)
        page.y = y - h
        stripe += 1

    page.y -= gap_after


def draw_side_by_side(page: Page, tables: list[tuple[list[Column], list[Row]]], gap: float = 24) -> None:
    """Small tables next to each other (e.g. the Resumen block). They must fit
    on one page together, so the tallest decides whether to break first."""
    page.ensure(max(table_height(rows) for _, rows in tables) + 4)
    top, bottom, x = page.y, page.y, MARGIN
    for columns, rows in tables:
        page.y = top
        draw_table(page, columns, rows, x0=x, gap_after=0)
        bottom = min(bottom, page.y)
        x += sum(col.width for col in columns) + gap
    page.y = bottom - 14


def draw_resumen(page: Page, stats: list[tuple[str, str]],
                 tables: list[tuple[list[Column], list[Row]]]) -> None:
    """The "Resumen" block — heading, a line of numbers and small side-by-side
    tables — kept together on one page."""
    tallest = max((table_height(rows) for _, rows in tables), default=0)
    page.ensure(18 + 20 + tallest + 4)
    draw_section(page, "Resumen")
    draw_stats_line(page, stats)
    if tables:
        draw_side_by_side(page, tables)


def draw_stats_line(page: Page, stats: list[tuple[str, str]]) -> None:
    """One row of "Label  value" pairs, e.g. Promedio por domingo  23."""
    c = page.c
    page.ensure(16)
    x, y = MARGIN, page.y - 9
    for label, value in stats:
        c.setFont(FONT, 8)
        c.setFillColor(MUTED)
        c.drawString(x, y, label)
        x += c.stringWidth(label, FONT, 8) + 4
        c.setFont(FONT_BOLD, 9)
        c.setFillColor(INK)
        c.drawString(x, y, value)
        x += c.stringWidth(value, FONT_BOLD, 9) + 22
    page.y -= 20


def draw_feedback_card(page: Page) -> None:
    """End-of-document box: QR code + link to the feedback form."""
    c, h = page.c, 58
    page.ensure(h + 6)
    y = page.y - 4
    c.setStrokeColor(GREY_LINE)
    c.setLineWidth(0.6)
    c.rect(MARGIN, y - h, page.usable_w, h, fill=0, stroke=1)
    draw_qr(c, MARGIN + 6, y - h + 5, 48, FEEDBACK_FORM_URL)
    c.setFont(FONT_BOLD, 10)
    c.setFillColor(T("title"))
    c.drawString(MARGIN + 64, y - 19, "¿Algo confuso? ¿Una idea? ¿Algo que no funciona? Cuéntanos.")
    c.setFont(FONT, 8)
    c.setFillColor(MUTED)
    c.drawString(MARGIN + 64, y - 33, "Escanea el código o toca aquí para dejar tus comentarios, dudas o quejas.")
    c.drawString(MARGIN + 64, y - 45, "Entre más nos digas, mejor podemos hacer estas listas.  "
                                      "·  Scan or tap to share feedback.")
    c.linkURL(FEEDBACK_FORM_URL, (MARGIN, y - h, MARGIN + page.usable_w, y), relative=0)
    page.y = y - h - 8


def draw_note(page: Page, text: str) -> None:
    """A muted one-line explanation under a section."""
    page.ensure(14)
    page.c.setFont(FONT_ITAL, 7)
    page.c.setFillColor(MUTED)
    page.c.drawString(MARGIN, page.y - 8, fit(page.c, text, page.usable_w, FONT_ITAL, 7))
    page.y -= 16
