# tests/golden/harness.py
#
# Shared machinery for the golden tests: the frozen clock, IBL's pinned
# settings, PDF → text snapshots, and the compare-or-update step.
#
# A snapshot is plain text so a diff reads like the PDF: one block per page with
# the text pypdf extracts, the link targets, and a fingerprint of the page's
# drawing instructions. Raw PDF bytes are never compared — they carry
# timestamps and object ids.
#
# Why the drawing fingerprint: attendance dots, the "new" star, yellow
# missing-data cells and theme colours are shapes, not text. Without it a
# refactor could break them and every text comparison would still pass. When
# only a [drawing] line differs, the words are unchanged but something on the
# page looks different — open the PDF and compare by eye.

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pypdf
import reportlab
from pypdf import PdfReader

from planning_center_reports.church import Branding, ChurchConfig
from planning_center_reports.config import LOGO_PATH
from planning_center_reports.pdf.context import RenderContext

GOLDEN_DIR   = Path(__file__).resolve().parent
SNAPSHOT_DIR = GOLDEN_DIR / "snapshots"
FIXTURE_DIR  = GOLDEN_DIR / "fixtures"

# The weekly job fires Monday 08:00 UTC and Cloud Run's clock is UTC, so the
# frozen instant is the Monday after the last mock Sunday (2026-10-11), in UTC.
FROZEN_NOW = datetime(2026, 10, 12, 8, 0, tzinfo=ZoneInfo("UTC"))

# IBL's settings, written out here on purpose. The golden tests build this
# church explicitly instead of going through legacy.py, so a developer's local
# .env cannot change a snapshot. test_golden_config.py separately checks that
# legacy.py's defaults still equal these values.
IBL_VERSE_TEXT   = '"Id por todo el mundo y predicad el evangelio a toda criatura"'
IBL_VERSE_REF    = "Marcos 16:15 — RV1960"
IBL_FEEDBACK_URL = (
    "https://docs.google.com/forms/d/e/1FAIpQLSfSflUQmzCsL1TekFt_lQVCddGIInJw0QRoBjE8f6VrX0Hz6g/viewform"
)
IBL_VIDEO_URL    = "https://drive.google.com/file/d/1yTSZM-FTPZHbKlRrMizAm06eUM-E6Mc4/view"
IBL_HELP_CONTACT = "Hna. Lira — cuarto de impresoras"
IBL_TIMEZONE     = "America/Chicago"
IBL_RUTAS_SUBTITLE = "Ministerio de Autobuses"
FAKE_DRIVE_PARENT  = "PARENT"


def ibl_church(reports=()) -> ChurchConfig:
    """IBL as the legacy adapter builds it, with nothing read from the environment."""
    return ChurchConfig(
        org_id="legacy",
        name="Iglesia Bautista Libertad",
        timezone=IBL_TIMEZONE,
        language="es",
        branding=Branding(
            logo_path=LOGO_PATH,
            verse_text=IBL_VERSE_TEXT,
            verse_ref=IBL_VERSE_REF,
            help_contact=IBL_HELP_CONTACT,
            video_url=IBL_VIDEO_URL,
            feedback_url=IBL_FEEDBACK_URL,
        ),
        drive_parent_folder_id=FAKE_DRIVE_PARENT,
        reports=tuple(reports),
    )


def ibl_render(theme: str | None = None) -> RenderContext:
    return RenderContext.for_church(ibl_church(), theme)


def update_requested(config) -> bool:
    """True when snapshots should be rewritten instead of compared."""
    return bool(config.getoption("--update-golden")) or os.environ.get("UPDATE_GOLDEN", "") == "1"


# ── PDF → text ────────────────────────────────────────────────────────────────

def _page_links(page) -> list[str]:
    links = []
    for ref in page.get("/Annots") or []:
        annot = ref.get_object()
        uri = (annot.get("/A") or {}).get("/URI")
        if uri:
            links.append(str(uri))
    return sorted(set(links))


def _drawing_fingerprint(page) -> str:
    contents = page.get_contents()
    data = contents.get_data() if contents is not None else b""
    # reportlab names an embedded image after a digest that can include its
    # file path; strip it so the fingerprint is the same on every machine.
    data = re.sub(rb"/FormXob\.[0-9a-f]+", b"/FormXob", data)
    return hashlib.sha256(data).hexdigest()[:16]


def pdf_snapshot(path: str | os.PathLike) -> str:
    """Everything a reader can see or tap in a PDF, as text."""
    reader = PdfReader(str(path))
    total = len(reader.pages)
    out = [f"pages: {total}"]
    for number, page in enumerate(reader.pages, start=1):
        out.append(f"==== page {number} of {total} ====")
        text = page.extract_text() or ""
        out.extend(line.rstrip() for line in text.splitlines())
        for link in _page_links(page):
            out.append(f"[link] {link}")
        out.append(f"[drawing] {_drawing_fingerprint(page)}")
    return "\n".join(out) + "\n"


def to_json(value) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False, default=str) + "\n"


# ── Compare or update ─────────────────────────────────────────────────────────

def library_versions() -> str:
    return f"pypdf {pypdf.__version__}, reportlab {reportlab.Version}"


def check(name: str, actual: str, update: bool) -> None:
    """Compare `actual` with snapshots/<name>, or rewrite it when updating."""
    path = SNAPSHOT_DIR / name
    if update:
        path.parent.mkdir(parents=True, exist_ok=True)
        versions = SNAPSHOT_DIR / "VERSIONS.txt"
        stamp = f"Snapshots last recorded with: {library_versions()}\n"
        if not versions.exists() or versions.read_text(encoding="utf-8") != stamp:
            versions.write_text(stamp, encoding="utf-8")
        if not path.exists() or path.read_text(encoding="utf-8") != actual:
            path.write_text(actual, encoding="utf-8")
        return
    if not path.exists():
        raise AssertionError(
            f"No golden snapshot at {path.relative_to(GOLDEN_DIR)}. "
            "If this output is new and intended, run: pytest --update-golden"
        )
    expected = path.read_text(encoding="utf-8")
    if expected == actual:
        return
    diff = "\n".join(difflib.unified_diff(
        expected.splitlines(), actual.splitlines(),
        fromfile=f"golden/{name}", tofile="this run", lineterm="", n=2,
    ))
    raise AssertionError(
        f"Output differs from golden snapshot {name}.\n"
        "This is IBL-visible output. Only if the change is deliberate, run: pytest --update-golden\n"
        f"(Snapshots were recorded with the versions in snapshots/VERSIONS.txt; this run has "
        f"{library_versions()}. A pypdf or reportlab upgrade alone can change extracted text or [drawing] fingerprints.)\n\n{diff}"
    )
