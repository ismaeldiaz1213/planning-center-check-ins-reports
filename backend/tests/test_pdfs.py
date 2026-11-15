# tests/test_pdfs.py
#
# Render every PDF from mock data and check what a reader would see: the
# sections, labels and parent lines are present, empty states are handled,
# and the instructions bundle contains the cover plus both guides.

import pytest
from pypdf import PdfReader

from planning_center_reports.church import Branding, ChurchConfig
from planning_center_reports.i18n import catalog
from planning_center_reports.mock_data import mock_roster, mock_volunteers
from planning_center_reports.pdf.context import RenderContext
from planning_center_reports.pdf.instructions import (
    build_instructions_pdf,
    guides,
    instructions_fingerprint,
)
from planning_center_reports.pdf.layout import fit
from planning_center_reports.pdf.rosters import _guardian_line, generate_roster_pdf, short_route
from planning_center_reports.pdf.volunteers import generate_volunteer_pdf
from planning_center_reports.roster_data import LocationRoster, VolunteerReport


def text_of(path) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(path).pages)


ES = catalog("es")
BRANDING = Branding(verse_text="Un versículo", verse_ref="Libro 1:1", help_contact="la oficina",
                    video_url="https://example.org/video", feedback_url="https://example.org/feedback")
CTX = RenderContext(texts=ES, branding=BRANDING)


class TestRosterPdf:
    def test_has_every_section(self, tmp_path):
        path = generate_roster_pdf(mock_roster("Clase Primaria"), "Escuela Dominical",
                                   str(tmp_path / "r.pdf"), CTX, show_route=True, attendance_summary=True)
        text = text_of(path)
        for expected in ("Clase Primaria", "Lista", "Maestros y ayudantes", "Resumen",
                         "Niños en la lista", "Promedio por domingo", "Hace tiempo que no viene",
                         "Padre/Tutor:", "Agregado", "Ruta"):
            assert expected in text

    def test_route_column_only_when_asked(self, tmp_path):
        path = generate_roster_pdf(mock_roster("Ruta 1 - Bus", show_route=False), "Rutas",
                                   str(tmp_path / "r.pdf"), CTX)
        header = text_of(path).split("Nombre", 1)[1].split("\n", 1)[0]
        assert "Ruta" not in header

    @pytest.mark.parametrize("theme", ["primavera", "verano", "otono", "invierno"])
    def test_renders_in_every_theme(self, tmp_path, theme):
        path = generate_roster_pdf(mock_roster("Clase"), "Escuela", str(tmp_path / f"{theme}.pdf"),
                                   CTX.with_theme(theme))
        assert ES.t(f"campaign.{theme}") in text_of(path)

    def test_empty_roster_still_renders(self, tmp_path):
        path = generate_roster_pdf(LocationRoster(location="Vacía"), "Escuela", str(tmp_path / "e.pdf"), CTX)
        assert "Nadie ha venido" in text_of(path)

    def test_long_rosters_paginate(self, tmp_path):
        roster = mock_roster("Grande")
        roster.active = roster.active * 12
        path = generate_roster_pdf(roster, "Escuela", str(tmp_path / "big.pdf"), CTX)
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
        assert [label for label, _ in _guardian_line(m, ES)] == ["Padre/Tutor:", ""]

    def test_guardian_address_shown_when_different(self):
        m = mock_roster("x").active[0]
        m.address = "1 A St, Houston"
        m.guardian = {"name": "Mamá", "phone": "1", "address": "2 B St, Houston, TX, 77001"}
        assert _guardian_line(m, ES)[-1] == ("", "2 B St, Houston")

    def test_no_guardian_no_line(self):
        m = mock_roster("x").active[0]
        m.guardian = None
        assert _guardian_line(m, ES) is None


class TestVolunteerPdf:
    def test_lists_groups_times_and_summary(self, tmp_path):
        text = text_of(generate_volunteer_pdf(mock_volunteers(), "Escuela", str(tmp_path / "v.pdf"), CTX))
        for expected in ("Asistencia de voluntarios", "Clase Primaria", "Ingrid Rivero", "9:35",
                         "Resumen", "Primer check-in"):
            assert expected in text

    def test_never_labels_anyone_early_or_late(self, tmp_path):
        text = text_of(generate_volunteer_pdf(mock_volunteers(), "Escuela", str(tmp_path / "v.pdf"), CTX))
        assert "tarde" not in text and "antes de" not in text

    def test_empty_state_explains_how_to_tag_volunteers(self, tmp_path):
        report = VolunteerReport("Asistencia de voluntarios", [], [])
        text = text_of(generate_volunteer_pdf(report, "C", str(tmp_path / "v.pdf"), CTX))
        assert "Volunteer" in text


class TestInstructionsPdf:
    def test_cover_then_both_guides(self, tmp_path):
        path = build_instructions_pdf(str(tmp_path / "i.pdf"), CTX)
        reader = PdfReader(path)
        guide_pages = sum(len(PdfReader(p).pages) for _, p in guides(ES))
        assert len(reader.pages) == 1 + guide_pages
        cover = reader.pages[0].extract_text()
        assert "Cómo registrar asistencia" in cover
        assert "Mira el video" in cover

    def test_fingerprint_is_stable(self):
        assert instructions_fingerprint(CTX) == instructions_fingerprint(CTX)


class TestFit:
    def test_fit_truncates_with_ellipsis(self, tmp_path):
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(tmp_path / "f.pdf"))
        assert fit(c, "short", 100) == "short"
        assert fit(c, "a very long piece of text indeed", 40).endswith("…")
        assert fit(c, "", -5) == ""


# ── Two churches, one process ─────────────────────────────────────────────────
# Nothing a PDF prints may come from module state: a second church rendered
# right after the first must show only its own language, branding and colours.

EN = catalog("en")
OTHER = RenderContext(
    texts=EN,
    branding=Branding(verse_text="For God so loved the world", verse_ref="John 3:16",
                      help_contact="the front desk", video_url="https://liberty.example/video",
                      feedback_url="https://liberty.example/feedback"),
    theme_key="invierno",
)


def links_of(path) -> set[str]:
    found = set()
    for page in PdfReader(path).pages:
        for ref in page.get("/Annots") or []:
            uri = (ref.get_object().get("/A") or {}).get("/URI")
            if uri:
                found.add(str(uri))
    return found


class TestTwoChurches:
    def test_rosters_rendered_back_to_back_share_nothing(self, tmp_path):
        def spanish(name):
            return generate_roster_pdf(mock_roster("Clase Primaria"), "Escuela Dominical",
                                       str(tmp_path / name), CTX.with_theme("primavera"),
                                       show_route=True, attendance_summary=True)
        first = spanish("es.pdf")
        second = generate_roster_pdf(mock_roster("3rd Grade"), "Sunday School",
                                     str(tmp_path / "en.pdf"), OTHER,
                                     show_route=True, attendance_summary=True)
        again = spanish("es2.pdf")
        es, en = text_of(first), text_of(second)

        for only_spanish in ("Lista", "Hace tiempo que no viene", "Padre/Tutor:", "Un versículo",
                             "Campaña de Primavera", "Página 1", "Generado el"):
            assert only_spanish in es and only_spanish not in en
        for only_english in ("Haven't been back recently", "Parent/Guardian:", "John 3:16",
                             "Winter Campaign", "Page 1", "Generated "):
            assert only_english in en and only_english not in es

        assert links_of(first) == {"https://example.org/feedback"}
        assert links_of(second) == {"https://liberty.example/feedback"}
        # Rendering another church in between changes nothing about the first one.
        assert text_of(again) == es

    def test_english_volunteer_sheet_and_instructions(self, tmp_path):
        sheet = text_of(generate_volunteer_pdf(mock_volunteers("Volunteer attendance"), "Sunday School",
                                               str(tmp_path / "v.pdf"), OTHER))
        assert "Usual time" in sheet and "Hora usual" not in sheet
        reader = PdfReader(build_instructions_pdf(str(tmp_path / "i.pdf"), OTHER))
        cover = reader.pages[0].extract_text()
        assert "How to check people in" in cover and "Cómo registrar asistencia" not in cover
        assert "the front desk" in cover
        # English churches get the English guide only.
        assert len(reader.pages) == 1 + sum(len(PdfReader(p).pages) for _, p in guides(EN))
        assert instructions_fingerprint(OTHER) != instructions_fingerprint(CTX)

    def test_church_without_links_or_logo_still_renders(self, tmp_path):
        bare = RenderContext(texts=EN, branding=Branding())
        path = generate_roster_pdf(mock_roster("Class"), "Sunday School", str(tmp_path / "bare.pdf"), bare)
        assert links_of(path) == set()
        assert "Tell us" not in text_of(path)
        build_instructions_pdf(str(tmp_path / "i.pdf"), bare)


class TestChurchConfig:
    def test_rejects_unknown_language_theme_and_timezone(self):
        ok = dict(org_id="1", name="X", timezone="America/Chicago")
        assert ChurchConfig(**ok).texts.code == "en"
        for bad in ({"language": "fr"}, {"theme": "otoño"}, {"timezone": "Mars/Olympus"}, {"org_id": " "}):
            with pytest.raises(Exception):  # noqa: B017 — ValueError or ZoneInfoNotFoundError
                ChurchConfig(**{**ok, **bad})
