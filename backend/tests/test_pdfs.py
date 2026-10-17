# tests/test_pdfs.py
#
# Render every PDF from mock data and check what a reader would see: the
# sections, labels and parent lines are present, empty states are handled,
# and the instructions bundle contains the cover plus both guides.

import pytest
from pypdf import PdfReader

import planning_center_reports.config as config
from planning_center_reports.mock_data import mock_roster, mock_volunteers
from planning_center_reports.pdf.instructions import (
    GUIDES,
    build_instructions_pdf,
    instructions_fingerprint,
)
from planning_center_reports.pdf.layout import fit
from planning_center_reports.pdf.rosters import _guardian_line, generate_roster_pdf, short_route
from planning_center_reports.pdf.volunteers import generate_volunteer_pdf
from planning_center_reports.roster_data import LocationRoster, VolunteerReport


def text_of(path) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(path).pages)


@pytest.fixture(autouse=True)
def default_theme():
    config._theme = config.THEMES[None]
    yield
    config._theme = config.THEMES[None]


class TestRosterPdf:
    def test_has_every_section(self, tmp_path):
        path = generate_roster_pdf(mock_roster("Clase Primaria"), "Escuela Dominical",
                                   str(tmp_path / "r.pdf"), show_route=True, attendance_summary=True)
        text = text_of(path)
        for expected in ("Clase Primaria", "Lista", "Maestros y ayudantes", "Resumen",
                         "Niños en la lista", "Promedio por domingo", "Hace tiempo que no viene",
                         "Padre/Tutor:", "Agregado", "Ruta"):
            assert expected in text

    def test_route_column_only_when_asked(self, tmp_path):
        path = generate_roster_pdf(mock_roster("Ruta 1 - Bus", show_route=False), "Rutas",
                                   str(tmp_path / "r.pdf"))
        header = text_of(path).split("Nombre", 1)[1].split("\n", 1)[0]
        assert "Ruta" not in header

    @pytest.mark.parametrize("theme", ["primavera", "verano", "otono", "invierno"])
    def test_renders_in_every_theme(self, tmp_path, theme):
        config._theme = config.THEMES[theme]
        path = generate_roster_pdf(mock_roster("Clase"), "Escuela", str(tmp_path / f"{theme}.pdf"))
        assert config.THEMES[theme]["campaign"] in text_of(path)

    def test_empty_roster_still_renders(self, tmp_path):
        path = generate_roster_pdf(LocationRoster(location="Vacía"), "Escuela", str(tmp_path / "e.pdf"))
        assert "Nadie ha venido" in text_of(path)

    def test_long_rosters_paginate(self, tmp_path):
        roster = mock_roster("Grande")
        roster.active = roster.active * 12
        path = generate_roster_pdf(roster, "Escuela", str(tmp_path / "big.pdf"))
        reader = PdfReader(path)
        assert len(reader.pages) > 2
        assert "continuación" in reader.pages[1].extract_text()


class TestRosterHelpers:
    def test_short_route(self):
        assert short_route("Ruta 1 - Bus") == "1 Bus"
        assert short_route("Ruta 12") == "12"
        assert short_route("") == ""

    def test_guardian_address_hidden_when_it_matches_the_kid(self):
        roster = mock_roster("x")
        m = roster.active[0]
        m.address = "12411 Antoine Dr, 803, Houston, TX, 77086"
        m.guardian = {"name": "Mamá", "phone": "1", "address": "12411 Antoine Dr, #803, Houston, TX, 77086"}
        assert [label for label, _ in _guardian_line(m)] == ["Padre/Tutor:", ""]

    def test_guardian_address_shown_when_different(self):
        m = mock_roster("x").active[0]
        m.address = "1 A St, Houston"
        m.guardian = {"name": "Mamá", "phone": "1", "address": "2 B St, Houston, TX, 77001"}
        assert _guardian_line(m)[-1] == ("", "2 B St, Houston")

    def test_no_guardian_no_line(self):
        m = mock_roster("x").active[0]
        m.guardian = None
        assert _guardian_line(m) is None


class TestVolunteerPdf:
    def test_lists_groups_times_and_summary(self, tmp_path):
        text = text_of(generate_volunteer_pdf(mock_volunteers(), "Escuela", str(tmp_path / "v.pdf")))
        for expected in ("Asistencia de voluntarios", "Clase Primaria", "Ingrid Rivero", "9:35",
                         "Resumen", "Primer check-in"):
            assert expected in text

    def test_never_labels_anyone_early_or_late(self, tmp_path):
        text = text_of(generate_volunteer_pdf(mock_volunteers(), "Escuela", str(tmp_path / "v.pdf")))
        assert "tarde" not in text and "antes de" not in text

    def test_empty_state_explains_how_to_tag_volunteers(self, tmp_path):
        report = VolunteerReport("Asistencia de voluntarios", [], [])
        text = text_of(generate_volunteer_pdf(report, "C", str(tmp_path / "v.pdf")))
        assert "Volunteer" in text


class TestInstructionsPdf:
    def test_cover_then_both_guides(self, tmp_path):
        path = build_instructions_pdf(str(tmp_path / "i.pdf"))
        reader = PdfReader(path)
        guide_pages = sum(len(PdfReader(p).pages) for _, p in GUIDES)
        assert len(reader.pages) == 1 + guide_pages
        cover = reader.pages[0].extract_text()
        assert "Cómo registrar asistencia" in cover
        assert "Mira el video" in cover

    def test_fingerprint_is_stable(self):
        assert instructions_fingerprint() == instructions_fingerprint()


class TestFit:
    def test_fit_truncates_with_ellipsis(self, tmp_path):
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(tmp_path / "f.pdf"))
        assert fit(c, "short", 100) == "short"
        assert fit(c, "a very long piece of text indeed", 40).endswith("…")
        assert fit(c, "", -5) == ""
