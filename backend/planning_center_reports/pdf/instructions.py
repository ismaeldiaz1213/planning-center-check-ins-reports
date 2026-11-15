# planning_center_reports/pdf/instructions.py
#
# Instrucciones.pdf — dropped into every class/route folder next to the roster.
#
#   page 1     a bilingual cover: the three steps, a QR code to the video
#              walkthrough, a quick-reference table and who to ask for help
#   pages 2+   the full Spanish guide, then the full English guide, unchanged
#              (assets/guides/*.pdf)
#
# The file only changes when the guides, the video link or this layout change,
# so instructions_fingerprint() lets services.py skip re-uploading it.

from __future__ import annotations

import hashlib
import os

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as rl_canvas

from planning_center_reports.config import (
    ACCENT_OK,
    ACCENT_WARN,
    ASSETS_DIR,
    GREY_LINE,
    INK,
    MUTED,
    THEMES,
    TILE_BG,
    WHITE,
)
from planning_center_reports.i18n import Catalog
from planning_center_reports.pdf.context import RenderContext
from planning_center_reports.pdf.layout import FONT, FONT_BOLD, FONT_ITAL, caps, draw_qr, fit

# Bump when the cover's design or wording changes, so every folder gets the new copy.
COVER_VERSION = "2026-10-cover-2"

NAVY  = THEMES[None]["title"]
BLUE  = THEMES[None]["col_header"]


GUIDE_FILES = {"es": "guia-check-in-es.pdf", "en": "check-in-guide-en.pdf"}


def guides(texts: Catalog, languages: tuple[str, ...] | None = None) -> list[tuple[str, str]]:
    """(table-of-contents label, file path) for each guide bundled after the cover.

    `languages` is the church's own choice (Branding.guide_languages); None means
    the default set for the PDF language.
    """
    if languages is None:
        chosen = texts.cover["guides"]
    else:
        chosen = [(texts.cover["guide_labels"][lang], GUIDE_FILES[lang]) for lang in languages]
    return [(label, os.path.join(ASSETS_DIR, "guides", name)) for label, name in chosen]


def instructions_fingerprint(ctx: RenderContext) -> str:
    """Hash of everything that goes into the PDF — changes only when its content does."""
    b = ctx.branding
    seed = f"{COVER_VERSION}|{b.video_url}|{b.feedback_url}|{b.help_contact}"
    if ctx.texts.code != "es":
        # Spanish keeps the original formula, so IBL's existing copies in Drive
        # still match and are not re-uploaded.
        seed += f"|{ctx.texts.code}"
    if b.guide_languages is not None:
        seed += f"|guides:{','.join(b.guide_languages)}"
    h = hashlib.sha256(seed.encode())
    for _, path in guides(ctx.texts, b.guide_languages):
        if os.path.exists(path):
            with open(path, "rb") as f:
                h.update(f.read())
    return h.hexdigest()[:32]


def _cover(path: str, guide_pages: list[tuple[str, int]], ctx: RenderContext) -> None:
    cover, branding = ctx.texts.cover, ctx.branding
    c = rl_canvas.Canvas(path, pagesize=letter)
    c.setTitle(cover["doc_title"])
    W, H = letter
    M = 44

    # ── Top: logo on white, then a navy title band ──
    if branding.logo_path and os.path.exists(branding.logo_path):
        c.drawImage(branding.logo_path, M, H - 62, width=150, height=150 * 58 / 300, mask="auto")
    caps(c, W - M - 150, H - 50, cover["brand"], size=7.5)

    band_top, band_h = H - 80, 118
    c.setFillColor(NAVY)
    c.rect(0, band_top - band_h, W, band_h, fill=1, stroke=0)
    c.setFillColor(BLUE)
    c.rect(0, band_top - band_h, W * 0.3, 5, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 30)
    c.drawString(M, band_top - 46, cover["title"])
    c.setFont(FONT, 16)
    c.setFillColor(colors.HexColor("#C9D6F2"))
    c.drawString(M, band_top - 70, cover["title_alt"])
    caps(c, M, band_top - 96, cover["audience"],
         size=7.4, color=colors.HexColor("#AFC3EA"), font=FONT_BOLD)

    # ── Steps (left) and video card (right) ──
    top = band_top - band_h - 30
    caps(c, M, top, cover["steps_heading"], size=8, color=BLUE)
    y = top - 20
    for i, (es, en, hint) in enumerate(cover["steps"], 1):
        c.setFillColor(BLUE)
        c.circle(M + 13, y - 11, 13, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(FONT_BOLD, 13)
        c.drawCentredString(M + 13, y - 15.5, str(i))
        c.setFillColor(INK)
        c.setFont(FONT_BOLD, 11.5)
        c.drawString(M + 36, y - 7, es)
        c.setFont(FONT_ITAL, 9)
        c.setFillColor(MUTED)
        c.drawString(M + 36, y - 19, en)
        c.setFont(FONT, 8.3)
        c.setFillColor(INK)
        c.drawString(M + 36, y - 31, fit(c, hint, 300, FONT, 8.3))
        y -= 52

    card_w, card_h = 176, 216
    cx, cy = W - M - card_w, top + 6 - card_h
    if branding.video_url:      # a church with no walkthrough video gets no video card
        c.setFillColor(TILE_BG)
        c.roundRect(cx, cy, card_w, card_h, 10, fill=1, stroke=0)
        qr_size = 136
        c.setFillColor(WHITE)
        c.roundRect(cx + (card_w - qr_size) / 2 - 6, cy + card_h - qr_size - 22, qr_size + 12, qr_size + 12,
                    6, fill=1, stroke=0)
        draw_qr(c, cx + (card_w - qr_size) / 2, cy + card_h - qr_size - 16, qr_size, branding.video_url)
        c.setFillColor(INK)
        c.setFont(FONT_BOLD, 12)
        c.drawCentredString(cx + card_w / 2, cy + 48, cover["video_title"])
        c.setFont(FONT_ITAL, 9)
        c.setFillColor(MUTED)
        c.drawCentredString(cx + card_w / 2, cy + 35, cover["video_alt"])
        c.setFont(FONT, 7)
        c.setFillColor(BLUE)
        c.drawCentredString(cx + card_w / 2, cy + 18, cover["video_hint"])
        c.linkURL(branding.video_url, (cx, cy, cx + card_w, cy + card_h), relative=0)

    # ── Quick reference ──
    y = min(y, cy) - 20
    caps(c, M, y, cover["quick_heading"], size=8, color=BLUE)
    y -= 10
    col1 = 196
    row_h = 32
    c.setFillColor(NAVY)
    c.roundRect(M, y - 18, W - 2 * M, 18, 3, fill=1, stroke=0)
    caps(c, M + 10, y - 12, cover["quick_situation"], size=6.8, color=WHITE)
    caps(c, M + col1 + 10, y - 12, cover["quick_action"], size=6.8, color=WHITE)
    y -= 18
    for i, (es, en, todo) in enumerate(cover["quick"]):
        c.setFillColor(WHITE if i % 2 == 0 else TILE_BG)
        c.rect(M, y - row_h, W - 2 * M, row_h, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont(FONT_BOLD, 8.6)
        c.drawString(M + 10, y - 13, fit(c, es, col1 - 16, FONT_BOLD, 8.6))
        c.setFont(FONT_ITAL, 7.6)
        c.setFillColor(MUTED)
        c.drawString(M + 10, y - 24, en)
        c.setFont(FONT, 8.6)
        c.setFillColor(INK)
        c.drawString(M + col1 + 10, y - 19, fit(c, todo, W - 2 * M - col1 - 20, FONT, 8.6))
        c.setStrokeColor(GREY_LINE)
        c.setLineWidth(0.4)
        c.line(M, y - row_h, W - M, y - row_h)
        y -= row_h

    # ── Help + feedback ──
    y -= 22
    box_h = 74
    c.setFillColor(colors.HexColor("#FFF7E6"))
    c.roundRect(M, y - box_h, W - 2 * M, box_h, 8, fill=1, stroke=0)
    c.setFillColor(ACCENT_WARN)
    c.roundRect(M, y - box_h, 4, box_h, 2, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 10)
    c.drawString(M + 16, y - 18, cover["help_title"] if branding.help_contact else "")
    c.setFont(FONT, 9)
    c.drawString(M + 16, y - 32,
                 cover["help_line"].format(contact=branding.help_contact) if branding.help_contact else "")
    if branding.feedback_url:
        c.setFont(FONT_BOLD, 10)
        c.drawString(M + 16, y - 51, cover["feedback_title"])
        c.setFont(FONT, 9)
        c.drawString(M + 16, y - 64, cover["feedback_line"])
        c.setFillColor(WHITE)
        c.roundRect(W - M - 68, y - box_h + 6, 62, 62, 5, fill=1, stroke=0)
        draw_qr(c, W - M - 66, y - box_h + 8, 58, branding.feedback_url)
        c.linkURL(branding.feedback_url, (M, y - box_h, W - M, y - 40), relative=0)

    y -= box_h + 20
    caps(c, M, y, cover["contents_heading"], size=8, color=BLUE)
    y -= 16
    for label, page_no in guide_pages:
        c.setFillColor(ACCENT_OK)
        c.circle(M + 4, y + 3, 2.5, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont(FONT, 9.5)
        c.drawString(M + 14, y, label)
        c.setFont(FONT_BOLD, 9.5)
        c.drawRightString(W - M, y, cover["page_abbr"].format(n=page_no))
        c.setStrokeColor(GREY_LINE)
        c.setDash(1, 2)
        c.line(M + 18 + c.stringWidth(label, FONT, 9.5), y + 2, W - M - 40, y + 2)
        c.setDash()
        y -= 18

    c.setFont(FONT, 6.8)
    c.setFillColor(MUTED)
    c.drawString(M, 24, cover["footer_video"].format(url=branding.video_url) if branding.video_url else "")
    c.drawString(M, 14,
                 cover["footer_feedback"].format(url=branding.feedback_url) if branding.feedback_url else "")
    c.showPage()
    c.save()


def build_instructions_pdf(filename: str, ctx: RenderContext) -> str:
    """Write Instrucciones.pdf (cover + guides) and return `filename`."""
    readers = [(label, PdfReader(path)) for label, path in guides(ctx.texts, ctx.branding.guide_languages)
               if os.path.exists(path)]
    page_no, toc = 2, []
    for label, reader in readers:
        toc.append((label, page_no))
        page_no += len(reader.pages)

    cover_path = filename + ".cover.pdf"
    _cover(cover_path, toc, ctx)
    try:
        writer = PdfWriter()
        writer.append(cover_path)
        for _, reader in readers:
            writer.append(reader)
        writer.add_metadata({"/Title": ctx.texts.cover["doc_title"]})
        with open(filename, "wb") as f:
            writer.write(f)
    finally:
        os.remove(cover_path)
    return filename
