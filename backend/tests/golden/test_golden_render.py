# tests/golden/test_golden_render.py
#
# Golden snapshots of every PDF type, rendered straight from mock_data.
# This is the parity spec for the renderer: the engine refactor, the English
# catalog and a future Rust/Typst renderer must all reproduce these texts.

import pytest

from planning_center_reports.mock_data import mock_roster, mock_volunteers
from planning_center_reports.pdf.instructions import build_instructions_pdf, instructions_fingerprint
from planning_center_reports.pdf.rosters import generate_roster_pdf
from planning_center_reports.pdf.volunteers import generate_volunteer_pdf
from planning_center_reports.roster_data import LocationRoster, VolunteerReport

from . import harness

THEMES = [None, "primavera", "verano", "otono", "invierno"]


def _snap(name, path, update):
    harness.check(f"render/{name}.txt", harness.pdf_snapshot(path), update)


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t or "default")
def test_roster_with_route_and_summary_in_every_theme(tmp_path, update_golden, theme):
    """Sunday school roster: Ruta column, per-route summary, workers, inactive list."""
    path = generate_roster_pdf(mock_roster("Clase Primaria"), "Escuela Dominical", str(tmp_path / "r.pdf"),
                               harness.ibl_render(theme), show_route=True, attendance_summary=True)
    _snap(f"roster_route_summary__{theme or 'default'}", path, update_golden)


def test_roster_without_route(tmp_path, update_golden):
    """Bus route roster: no Ruta column, no per-route summary."""
    path = generate_roster_pdf(mock_roster("Ruta 1 - Bus", show_route=False),
                               harness.IBL_RUTAS_SUBTITLE, str(tmp_path / "r.pdf"), harness.ibl_render())
    _snap("roster_plain", path, update_golden)


def test_roster_with_route_but_no_summary(tmp_path, update_golden):
    path = generate_roster_pdf(mock_roster("Clase Primaria"), "Escuela Dominical",
                               str(tmp_path / "r.pdf"), harness.ibl_render(),
                               show_route=True, attendance_summary=False)
    _snap("roster_route_no_summary", path, update_golden)


def test_roster_active_people_only(tmp_path, update_golden):
    """No workers and nobody inactive: those two sections are left out."""
    roster = mock_roster("Clase Secundaria")
    roster.workers, roster.inactive = [], []
    path = generate_roster_pdf(roster, "Escuela Dominical", str(tmp_path / "r.pdf"), harness.ibl_render(),
                               show_route=True, attendance_summary=True)
    _snap("roster_active_only", path, update_golden)


def test_roster_empty(tmp_path, update_golden):
    path = generate_roster_pdf(LocationRoster(location="Vacía"), "Escuela Dominical",
                               str(tmp_path / "r.pdf"), harness.ibl_render())
    _snap("roster_empty", path, update_golden)


def test_roster_long_enough_to_paginate(tmp_path, update_golden):
    roster = mock_roster("Grande")
    roster.active = roster.active * 12
    roster.inactive = roster.inactive * 12
    path = generate_roster_pdf(roster, "Escuela Dominical", str(tmp_path / "r.pdf"), harness.ibl_render(),
                               show_route=True, attendance_summary=True)
    _snap("roster_paginated", path, update_golden)


def test_volunteer_report(tmp_path, update_golden):
    path = generate_volunteer_pdf(mock_volunteers(), "Escuela Dominical", str(tmp_path / "v.pdf"),
                                  harness.ibl_render())
    _snap("volunteers", path, update_golden)


def test_volunteer_report_empty(tmp_path, update_golden):
    report = VolunteerReport("Asistencia de voluntarios", [], [])
    path = generate_volunteer_pdf(report, '"C" Escuela Dominical', str(tmp_path / "v.pdf"),
                                  harness.ibl_render())
    _snap("volunteers_empty", path, update_golden)


def test_instructions_bundle(tmp_path, update_golden):
    """Cover page plus both bundled guides, and the fingerprint that decides re-uploads."""
    path = build_instructions_pdf(str(tmp_path / "i.pdf"), harness.ibl_render())
    _snap("instructions", path, update_golden)
    harness.check("render/instructions_fingerprint.txt",
                  instructions_fingerprint(harness.ibl_render()) + "\n", update_golden)
