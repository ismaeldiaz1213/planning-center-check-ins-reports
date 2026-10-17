# tests/test_reports_config.py
#
# Tests for the declarative report registry (planning_center_reports/reports.py):
# schema validation, the no-config fallback, and report lookup.

import os
import textwrap

import pytest
import yaml

from planning_center_reports.reports import (
    DEFAULT_REPORTS,
    OUTPUT_FILENAMES,
    ReportConfigError,
    ReportSpec,
    get_report,
    load_reports,
    parse_reports,
)


@pytest.fixture(autouse=True)
def restore_registry():
    """Tests here refresh the module-level registry cache; put it back afterwards
    so the config pinned in conftest.py is what every other test sees.

    REPORTS_CONFIG is restored by hand rather than relying on monkeypatch, whose
    undo runs after this fixture's teardown.
    """
    pinned = os.environ.get("REPORTS_CONFIG", "")
    yield
    if pinned:
        os.environ["REPORTS_CONFIG"] = pinned
    else:
        os.environ.pop("REPORTS_CONFIG", None)
    load_reports(refresh=True)


def _parse(yaml_text: str):
    return parse_reports(yaml.safe_load(textwrap.dedent(yaml_text)), source="test.yaml")


MINIMAL = textwrap.dedent("""
    reports:
      - id: ninos
        label: Clases de Niños
        pco_event: Clases de Niños
""").lstrip("\n")


def _with(*extra_fields: str) -> str:
    """MINIMAL plus extra field lines on the single report."""
    return MINIMAL + "".join(f"    {line}\n" for line in extra_fields)


# ── Minimal spec: every optional feature off ──────────────────────────────────

class TestMinimalSpec:
    def test_only_three_required_fields(self):
        (spec,) = _parse(MINIMAL)
        assert spec.id == "ninos"
        assert spec.label == "Clases de Niños"
        assert spec.pco_event == "Clases de Niños"

    def test_optional_features_default_off(self):
        """A church with no bus ministry must not be forced into route logic."""
        (spec,) = _parse(MINIMAL)
        assert spec.route_source_event is None
        assert spec.helpers_event is None
        assert spec.show_route is False
        assert spec.attendance_summary is False
        assert spec.drive_folder_prefix is None

    def test_defaults_to_a_single_alphabetical_roster(self):
        (spec,) = _parse(MINIMAL)
        assert spec.outputs == ("simple",)
        assert spec.default_weeks == 5
        assert spec.default_theme is None

    def test_subtitle_falls_back_to_label(self):
        (spec,) = _parse(MINIMAL)
        assert spec.pdf_subtitle == "Clases de Niños"

    def test_explicit_subtitle_wins(self):
        (spec,) = _parse(_with("subtitle: Ministerio Infantil"))
        assert spec.pdf_subtitle == "Ministerio Infantil"


# ── Validation ────────────────────────────────────────────────────────────────

class TestValidation:
    def test_missing_required_field_is_an_error(self):
        with pytest.raises(ReportConfigError):
            _parse("reports:\n  - id: x\n    label: X\n")

    def test_unknown_key_is_rejected(self):
        with pytest.raises(ReportConfigError, match="unknown key"):
            _parse(_with("show_rutas: true"))

    def test_duplicate_id_is_rejected(self):
        with pytest.raises(ReportConfigError, match="duplicate report id"):
            _parse(MINIMAL + MINIMAL.split("reports:\n", 1)[1])

    def test_unknown_output_is_rejected(self):
        with pytest.raises(ReportConfigError, match="unknown output"):
            _parse(_with("outputs: [excel]"))

    def test_empty_outputs_is_rejected(self):
        with pytest.raises(ReportConfigError, match="at least one"):
            _parse(_with("outputs: []"))

    def test_unknown_theme_is_rejected(self):
        with pytest.raises(ReportConfigError, match="unknown theme"):
            _parse(_with("default_theme: otoño"))

    def test_show_route_without_a_source_is_rejected(self):
        """Otherwise the Ruta column would silently render blank for every row."""
        with pytest.raises(ReportConfigError, match="route_source_event"):
            _parse(_with("show_route: true"))

    def test_out_of_range_weeks_is_rejected(self):
        with pytest.raises(ReportConfigError, match="default_weeks"):
            _parse(_with("default_weeks: 0"))

    def test_empty_report_list_is_rejected(self):
        with pytest.raises(ReportConfigError, match="empty"):
            _parse("reports: []\n")

    def test_missing_reports_key_is_rejected(self):
        with pytest.raises(ReportConfigError, match="no 'reports' list"):
            _parse("something_else: 1\n")

    def test_a_bare_list_is_accepted(self):
        specs = parse_reports([{"id": "a", "label": "A", "pco_event": "A"}])
        assert specs[0].id == "a"

    def test_a_single_output_string_is_accepted(self):
        (spec,) = _parse(_with("outputs: address"))
        assert spec.outputs == ("address",)


# ── Fallback when no config file exists ───────────────────────────────────────

class TestNoConfigFallback:
    def test_falls_back_to_builtin_defaults(self, monkeypatch, tmp_path):
        """An install that never adds a reports.yaml keeps the original behaviour."""
        monkeypatch.delenv("REPORTS_CONFIG", raising=False)
        monkeypatch.setattr("planning_center_reports.reports.config_path", lambda: None)
        specs = load_reports(refresh=True)
        assert specs == DEFAULT_REPORTS
        assert [s.id for s in specs] == ["rutas", "escuela"]

    def test_builtin_rutas_matches_the_original_pipeline(self):
        rutas = next(s for s in DEFAULT_REPORTS if s.id == "rutas")
        assert rutas.pco_event == "Rutas"
        assert rutas.outputs == ("address", "simple")
        assert rutas.helpers_event == "Junta de Rutas Attendance"
        assert rutas.show_route is False
        assert rutas.attendance_summary is False

    def test_builtin_escuela_matches_the_original_pipeline(self):
        esc = next(s for s in DEFAULT_REPORTS if s.id == "escuela")
        assert esc.pco_event == "Escuela Dominical"
        assert esc.outputs == ("simple",)
        assert esc.route_source_event == "Rutas"
        assert esc.show_route is True
        assert esc.attendance_summary is True

    def test_missing_reports_config_path_is_an_error(self, monkeypatch):
        monkeypatch.setenv("REPORTS_CONFIG", "/nonexistent/reports.yaml")
        with pytest.raises(ReportConfigError, match="missing file"):
            load_reports(refresh=True)


# ── Lookup ────────────────────────────────────────────────────────────────────

class TestGetReport:
    def test_resolves_by_id(self):
        assert get_report("escuela-b").id == "escuela-b"

    def test_resolves_by_pco_event_name(self):
        """Keeps `python main.py "Escuela Dominical"` and the Cloud Run job args working."""
        assert get_report("Escuela Dominical").id == "escuela"

    def test_resolves_case_insensitively_as_a_last_resort(self):
        assert get_report("RUTAS").id == "rutas"

    def test_unknown_key_raises_with_the_configured_list(self):
        with pytest.raises(ReportConfigError, match="Configured reports"):
            get_report("does-not-exist")


# ── Derived values ────────────────────────────────────────────────────────────

class TestDerivedValues:
    def test_env_prefix_underscores_hyphens(self):
        assert get_report("escuela-b").env_prefix == "ESCUELA_B"

    def test_resolved_weeks_prefers_the_env_override(self, monkeypatch):
        monkeypatch.setenv("ESCUELA_B_DEFAULT_WEEKS", "9")
        assert get_report("escuela-b").resolved_weeks() == 9

    def test_resolved_weeks_ignores_an_out_of_range_override(self, monkeypatch):
        monkeypatch.setenv("ESCUELA_B_DEFAULT_WEEKS", "99")
        assert get_report("escuela-b").resolved_weeks() == 5

    def test_resolved_theme_ignores_an_unknown_override(self, monkeypatch):
        monkeypatch.setenv("RUTAS_DEFAULT_THEME", "bogus")
        assert get_report("rutas").resolved_theme() is None

    def test_public_dict_hides_pco_event_names(self):
        data = get_report("escuela-b").public_dict()
        assert set(data) == {
            "id", "label", "icon", "outputs", "show_route", "default_weeks", "default_theme"
        }

    def test_spec_is_immutable(self):
        with pytest.raises(Exception):
            get_report("rutas").label = "changed"

    def test_every_output_kind_has_a_filename(self):
        for spec in load_reports():
            for kind in spec.outputs:
                assert kind in OUTPUT_FILENAMES


# ── The shipped example config ────────────────────────────────────────────────

class TestShippedConfig:
    def test_escuela_b_is_configured(self):
        spec = get_report("escuela-b")
        assert spec.pco_event == '"B" Escuela Dominical'
        assert spec.show_route is True
        assert spec.attendance_summary is True
        assert spec.helpers_event == "Junta de Rutas Attendance"

    def test_escuela_b_uploads_under_its_own_folder(self):
        """Its class names may collide with the A session's — the prefix keeps them apart."""
        assert get_report("escuela-b").drive_folder_prefix == '"B" Escuela Dominical'
        assert get_report("escuela").drive_folder_prefix is None

    def test_all_shipped_reports_construct(self):
        assert {s.id for s in load_reports()} == {"rutas", "escuela", "escuela-b"}


def test_report_spec_can_be_built_directly():
    spec = ReportSpec(id="x", label="X", pco_event="X Event")
    assert spec.outputs == ("simple",)
