# advanced_reports/make_samples.py
#
# Regenerate the sample roster pictures on the home page from the engine's mock
# data (invented people; addresses are public Chick-fil-A restaurants around
# Houston). Needs `pdftoppm` (poppler).
#
#   cd backend && python -m advanced_reports.make_samples

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from planning_center_reports import legacy
from planning_center_reports.church import Branding
from planning_center_reports.i18n import catalog
from planning_center_reports.mock_data import mock_roster, mock_volunteers
from planning_center_reports.pdf.context import RenderContext
from planning_center_reports.pdf.rosters import generate_roster_pdf
from planning_center_reports.pdf.volunteers import generate_volunteer_pdf

OUT = Path(__file__).resolve().parent / "static" / "img"


def _png(pdf: str, name: str, page: int = 1) -> None:
    subprocess.run(["pdftoppm", "-png", "-r", "110", "-f", str(page), "-l", str(page), "-singlefile",
                    pdf, str(OUT / name)], check=True)
    print(f"  ✓ {name}.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    es = legacy.render_context()
    en = RenderContext(texts=catalog("en"), branding=Branding(
        verse_text='"Let the little children come to me"', verse_ref="Matthew 19:14"))
    with tempfile.TemporaryDirectory() as tmp:
        _png(generate_roster_pdf(mock_roster("Clase Primaria"), "Escuela Dominical", f"{tmp}/es.pdf", es,
                                 show_route=True, attendance_summary=True), "sample-roster-es")
        _png(generate_roster_pdf(mock_roster("3rd Grade"), "Sunday School", f"{tmp}/en.pdf", en,
                                 show_route=True, attendance_summary=True), "sample-roster-en")
        _png(generate_volunteer_pdf(mock_volunteers(en.texts.t("volunteers.title")), "Sunday School",
                                    f"{tmp}/vol.pdf", en), "sample-volunteers-en")


if __name__ == "__main__":
    main()
