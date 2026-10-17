# tests/test_run_report.py
#
# Tests for services.run_report — the single pipeline that replaced the separate
# run_rutas / run_escuela_dominical functions.
#
# The point of these tests is the flexibility guarantee: a report that does not
# declare an optional feature must not make the PCO calls that feature needs.

from unittest.mock import patch

import pytest

from planning_center_reports.reports import ReportSpec
from planning_center_reports.services import run_report

EMPTY_PERSON = {"phone": "", "address": "", "birthday": "", "grade": "", "created_at": ""}


def _checkin(person_id, first, last, location_id, ep_id="ep1"):
    return {
        "attributes": {"first_name": first, "last_name": last},
        "relationships": {
            "locations":    {"data": [{"id": location_id}]},
            "person":       {"data": {"id": person_id}},
            "event_period": {"data": {"id": ep_id}},
        },
    }


CHECKINS = [
    _checkin("p1", "Ana", "Lopez", "loc1"),
    _checkin("p2", "Luis", "Diaz", "loc1"),
]
INCLUDED = [{"type": "Location", "id": "loc1", "attributes": {"name": "Clase Primaria"}}]

MINIMAL_SPEC = ReportSpec(id="ninos", label="Clases de Niños", pco_event="Clases de Niños")

FULL_SPEC = ReportSpec(
    id="escuela-b",
    label='"B" Escuela Dominical',
    pco_event='"B" Escuela Dominical',
    helpers_event="Junta de Rutas Attendance",
    route_source_event="Rutas",
    show_route=True,
    attendance_summary=True,
    drive_folder_prefix='"B" Escuela Dominical',
)


@pytest.fixture
def pco(monkeypatch):
    """Patch the whole PCO surface run_report touches; yields the mock namespace.

    `copies` records the destinations _save_pdf_locally would write, since the
    generator mocks return paths that do not exist on disk.
    """
    copies: list[str] = []
    monkeypatch.setattr("planning_center_reports.services.shutil.copy",
                        lambda src, dest: copies.append(dest))
    monkeypatch.setattr("planning_center_reports.services.time.sleep", lambda _s: None)
    with patch("planning_center_reports.services.get_event_id", return_value="ev1") as ev, \
         patch("planning_center_reports.services.get_recent_event_periods",
               return_value=(["ep1"], {"ep1": "Abr 6"}, {"ep1": "2025-04-06T00:00:00Z"})), \
         patch("planning_center_reports.services.get_checkins_for_event_periods",
               return_value=(CHECKINS, INCLUDED)), \
         patch("planning_center_reports.services.get_person_details", return_value=EMPTY_PERSON), \
         patch("planning_center_reports.services.get_helpers_set", return_value=set()) as helpers, \
         patch("planning_center_reports.services._get_route_mapping", return_value={}) as routes, \
         patch("planning_center_reports.services.generate_simple_roster_pdf",
               return_value="/tmp/does-not-exist-simple.pdf") as simple, \
         patch("planning_center_reports.services.generate_address_pdf",
               return_value="/tmp/does-not-exist-address.pdf") as address:
        yield {
            "event_id": ev, "helpers": helpers, "routes": routes,
            "simple": simple, "address": address, "copies": copies,
        }


# ── Optional features are genuinely optional ──────────────────────────────────

class TestMinimalReportSkipsOptionalWork:
    def test_never_fetches_helpers(self, pco, tmp_path):
        run_report(MINIMAL_SPEC, dry_run=True, output_dir=str(tmp_path))
        pco["helpers"].assert_not_called()

    def test_never_builds_a_route_map(self, pco, tmp_path):
        run_report(MINIMAL_SPEC, dry_run=True, output_dir=str(tmp_path))
        pco["routes"].assert_not_called()

    def test_only_looks_up_its_own_event(self, pco, tmp_path):
        run_report(MINIMAL_SPEC, dry_run=True, output_dir=str(tmp_path))
        assert [c[0][0] for c in pco["event_id"].call_args_list] == ["Clases de Niños"]

    def test_renders_no_route_column_and_no_summary(self, pco, tmp_path):
        run_report(MINIMAL_SPEC, dry_run=True, output_dir=str(tmp_path))
        _, kwargs = pco["simple"].call_args
        assert kwargs["show_route"] is False
        assert kwargs["sunday_data"] is None

    def test_emits_only_the_simple_roster(self, pco, tmp_path):
        run_report(MINIMAL_SPEC, dry_run=True, output_dir=str(tmp_path))
        pco["address"].assert_not_called()
        assert pco["simple"].call_count == 1


class TestFullReportUsesOptionalWork:
    def test_fetches_helpers_from_the_configured_event(self, pco, tmp_path):
        run_report(FULL_SPEC, dry_run=True, output_dir=str(tmp_path))
        args, kwargs = pco["helpers"].call_args
        assert args[0] == "Junta de Rutas Attendance"
        assert kwargs["min_age"] == 16

    def test_builds_a_route_map_from_the_configured_event(self, pco, tmp_path):
        run_report(FULL_SPEC, dry_run=True, output_dir=str(tmp_path))
        assert pco["routes"].call_args[0][0] == "Rutas"

    def test_renders_route_column_and_summary(self, pco, tmp_path):
        run_report(FULL_SPEC, dry_run=True, output_dir=str(tmp_path))
        _, kwargs = pco["simple"].call_args
        assert kwargs["show_route"] is True
        assert kwargs["sunday_data"] is not None

    def test_uses_the_spec_subtitle(self, pco, tmp_path):
        run_report(FULL_SPEC, dry_run=True, output_dir=str(tmp_path))
        assert pco["simple"].call_args[0][1] == '"B" Escuela Dominical'


class TestOutputs:
    def test_address_output_generates_the_direcciones_pdf(self, pco, tmp_path):
        spec = ReportSpec(id="r", label="R", pco_event="R", outputs=("address", "simple"))
        run_report(spec, dry_run=True, output_dir=str(tmp_path))
        assert pco["address"].call_args[0][2] == "Direcciones-Roster.pdf"
        assert pco["simple"].call_args[0][3] == "Roster.pdf"


# ── Drive destination ─────────────────────────────────────────────────────────

class TestDriveFolderPrefix:
    @patch("planning_center_reports.services.upload_and_replace")
    @patch("planning_center_reports.services.get_or_create_folder")
    @patch("planning_center_reports.services.get_drive_service")
    def test_prefix_nests_the_location_folder(self, _svc, mock_folder, _upload, pco):
        mock_folder.side_effect = ["prefix-folder-id", "location-folder-id"]
        run_report(FULL_SPEC)
        # First call creates the report's prefix folder under the configured parent,
        # second creates the class folder inside it.
        assert mock_folder.call_args_list[0][0][2] == '"B" Escuela Dominical'
        assert mock_folder.call_args_list[1][0][1] == "prefix-folder-id"
        assert mock_folder.call_args_list[1][0][2] == "Clase Primaria"

    @patch("planning_center_reports.services.upload_and_replace")
    @patch("planning_center_reports.services.get_or_create_folder")
    @patch("planning_center_reports.services.get_drive_service")
    def test_no_prefix_keeps_the_original_flat_layout(self, _svc, mock_folder, _upload, pco):
        mock_folder.return_value = "location-folder-id"
        run_report(MINIMAL_SPEC)
        assert mock_folder.call_count == 1
        assert mock_folder.call_args[0][2] == "Clase Primaria"

    def test_dry_run_mirrors_the_prefix_on_disk(self, pco, tmp_path):
        run_report(FULL_SPEC, dry_run=True, output_dir=str(tmp_path))
        assert pco["copies"]
        assert "B_Escuela_Dominical" in pco["copies"][0]

    def test_dry_run_without_a_prefix_stays_flat(self, pco, tmp_path):
        run_report(MINIMAL_SPEC, dry_run=True, output_dir=str(tmp_path))
        assert pco["copies"] == [str(tmp_path / "Clase_Primaria_Roster.pdf")]


# ── Graceful degradation ──────────────────────────────────────────────────────

class TestMissingOrEmptyEvent:
    def test_missing_event_is_not_a_crash(self, pco, tmp_path, capsys):
        """A report can be configured before its PCO event exists — e.g. a class
        that has not started meeting yet."""
        pco["event_id"].side_effect = Exception("Event not found")
        run_report(MINIMAL_SPEC, dry_run=True, output_dir=str(tmp_path))
        out = capsys.readouterr().out
        assert "exists in Planning Center yet" in out
        assert "this is not an error" in out
        pco["simple"].assert_not_called()

    def test_event_with_no_checkins_generates_nothing(self, pco, tmp_path, capsys):
        with patch("planning_center_reports.services.get_checkins_for_event_periods",
                   return_value=([], [])):
            run_report(MINIMAL_SPEC, dry_run=True, output_dir=str(tmp_path))
        out = capsys.readouterr().out
        assert "No one has checked into" in out
        assert "this is not an error" in out
        pco["simple"].assert_not_called()

    def test_event_with_no_periods_generates_nothing(self, pco, tmp_path, capsys):
        with patch("planning_center_reports.services.get_recent_event_periods",
                   return_value=([], {}, {})):
            run_report(MINIMAL_SPEC, dry_run=True, output_dir=str(tmp_path))
        out = capsys.readouterr().out
        assert "no event periods" in out
        assert "this is not an error" in out
        pco["simple"].assert_not_called()

    @pytest.mark.parametrize("failure_mode", ["missing_event", "no_periods", "no_checkins"])
    def test_empty_runs_exit_zero_through_the_cli(self, pco, tmp_path, monkeypatch, failure_mode):
        """The Cloud Run job must report success, not failure, when a configured
        report simply has nothing to generate yet."""
        import sys
        from planning_center_reports.cli import main

        if failure_mode == "missing_event":
            pco["event_id"].side_effect = Exception("404 Not Found")
            ctx = patch("planning_center_reports.services.get_event_id",
                        side_effect=Exception("404 Not Found"))
        elif failure_mode == "no_periods":
            ctx = patch("planning_center_reports.services.get_recent_event_periods",
                        return_value=([], {}, {}))
        else:
            ctx = patch("planning_center_reports.services.get_checkins_for_event_periods",
                        return_value=([], []))

        monkeypatch.setattr(sys, "argv",
                            ["main.py", "escuela-b", "--dry-run", "--output-dir", str(tmp_path)])
        with ctx:
            main()   # must not raise SystemExit — argparse/CLI errors would
