# tests/test_cli.py
#
# cli.main() resolves a report from reports.yaml and forwards the run flags, or
# runs every report with --all.

import sys
from unittest.mock import patch

import pytest


class TestCLIFlags:
    """cli.main() resolves a report from reports.yaml and forwards the run flags.

    The positional argument accepts either a report id or the PCO event name, so
    the pre-registry invocations ("Rutas", "Escuela Dominical") still work.
    """

    @patch("planning_center_reports.cli.run_report")
    def test_dry_run_flag_passed_through(self, mock_run, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "--dry-run", "Rutas"])
        from planning_center_reports.cli import main
        main()
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["dry_run"] is True

    @patch("planning_center_reports.cli.run_report")
    def test_location_flag_passed_through(self, mock_run, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "--location", "Ruta 8", "Rutas"])
        from planning_center_reports.cli import main
        main()
        _, kwargs = mock_run.call_args
        assert kwargs["location_filter"] == "Ruta 8"

    @patch("planning_center_reports.cli.run_report")
    def test_output_dir_flag_passed_through(self, mock_run, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["main.py", "--dry-run", "--output-dir", "/tmp/test", "Rutas"]
        )
        from planning_center_reports.cli import main
        main()
        _, kwargs = mock_run.call_args
        assert kwargs["output_dir"] == "/tmp/test"

    @patch("planning_center_reports.cli.run_report")
    def test_no_dry_run_by_default(self, mock_run, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "Rutas"])
        from planning_center_reports.cli import main
        main()
        _, kwargs = mock_run.call_args
        assert kwargs["dry_run"] is False

    @patch("planning_center_reports.cli.run_report")
    def test_no_location_filter_by_default(self, mock_run, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "Rutas"])
        from planning_center_reports.cli import main
        main()
        _, kwargs = mock_run.call_args
        assert kwargs["location_filter"] is None

    @patch("planning_center_reports.cli.run_report")
    def test_resolves_report_by_pco_event_name(self, mock_run, monkeypatch):
        """The original 'Escuela Dominical' argument still resolves."""
        monkeypatch.setattr(sys, "argv", ["main.py", "--dry-run", "Escuela Dominical"])
        from planning_center_reports.cli import main
        main()
        spec = mock_run.call_args[0][0]
        assert spec.id == "escuela"

    @patch("planning_center_reports.cli.run_report")
    def test_resolves_report_by_id(self, mock_run, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "escuela-b"])
        from planning_center_reports.cli import main
        main()
        spec = mock_run.call_args[0][0]
        assert spec.id == "escuela-b"
        assert spec.pco_event == '"B" Escuela Dominical'

    @patch("planning_center_reports.cli.run_report")
    def test_unknown_report_exits_with_error(self, mock_run, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "Nope"])
        from planning_center_reports.cli import main
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        mock_run.assert_not_called()


class TestAllFlag:
    @patch("planning_center_reports.cli.run_all", return_value=True)
    def test_all_runs_every_report(self, mock_all, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "--all", "--dry-run"])
        from planning_center_reports.cli import main
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        assert mock_all.call_args.kwargs["dry_run"] is True

    @patch("planning_center_reports.cli.run_all", return_value=False)
    def test_a_failed_report_fails_the_job(self, _mock, monkeypatch):
        """Cloud Run should mark the weekly run failed so someone notices."""
        monkeypatch.setattr(sys, "argv", ["main.py", "--all"])
        from planning_center_reports.cli import main
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    @patch("planning_center_reports.cli.run_all")
    def test_all_rejects_a_report_name(self, mock_all, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "--all", "rutas"])
        from planning_center_reports.cli import main
        with pytest.raises(SystemExit):
            main()
        mock_all.assert_not_called()
