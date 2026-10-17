# tests/test_run_report.py
#
# services.run_report / run_all with the PCO and Drive surface mocked.
#
# The flexibility guarantee still holds: a report that does not declare an
# optional feature must not make the PCO calls that feature needs. And the
# whole point of run_all: shared events are fetched once, not once per report.

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from planning_center_reports.reports import ReportSpec
from planning_center_reports.services import RunContext, run_all, run_report

NOW = datetime.now(UTC)
PERIODS = [{"id": f"ep{i}", "starts_at": NOW - timedelta(weeks=3 - i, hours=2)} for i in range(4)]


def _checkin(person_id, location_id, ep_id="ep3", kind="Regular"):
    return {
        "attributes": {"first_name": "", "last_name": "", "kind": kind, "created_at": ""},
        "relationships": {
            "locations":    {"data": [{"id": location_id}]},
            "person":       {"data": {"id": person_id}},
            "event_period": {"data": {"id": ep_id}},
            "event_times":  {"data": []},
        },
    }


INCLUDED = [
    {"type": "Location", "id": "loc1", "attributes": {"name": "Clase Primaria"}},
    {"type": "Person", "id": "p1", "attributes": {"first_name": "Ana", "last_name": "Lopez", "child": True}},
    {"type": "Person", "id": "p2", "attributes": {"first_name": "Luis", "last_name": "Diaz", "child": True}},
]


def fake_checkins(_event_id, period_ids):
    (pid,) = period_ids
    return [_checkin("p1", "loc1", pid), _checkin("p2", "loc1", pid)], INCLUDED


MINIMAL_SPEC = ReportSpec(id="ninos", label="Clases de Niños", pco_event="Clases de Niños")

FULL_SPEC = ReportSpec(
    id="escuela-b",
    label='"B" Escuela Dominical',
    pco_event='"B" Escuela Dominical',
    route_source_event="Rutas",
    show_route=True,
    attendance_summary=True,
    instructions=True,
    volunteer_report=True,
    drive_folder_prefix='"B" Escuela Dominical',
)


@pytest.fixture
def pco(monkeypatch, tmp_path):
    """Patch the PCO surface and the PDF writers; yields the mocks.

    `copies` records where a dry run would save each file.
    """
    copies: list[str] = []
    monkeypatch.setattr("planning_center_reports.services.shutil.copy",
                        lambda src, dest: copies.append(dest))
    with patch("planning_center_reports.services.get_event_id", side_effect=lambda n: f"id:{n}") as ev, \
         patch("planning_center_reports.services.get_event_periods_since", return_value=PERIODS) as per, \
         patch("planning_center_reports.services.get_checkins_for_event_periods",
               side_effect=fake_checkins) as cks, \
         patch("planning_center_reports.services.get_guardians", return_value={}) as guardians, \
         patch("planning_center_reports.services.generate_roster_pdf",
               side_effect=lambda roster, *a, **k: a[1]) as roster_pdf, \
         patch("planning_center_reports.services.generate_volunteer_pdf",
               side_effect=lambda report, label, path: path) as vol_pdf, \
         patch("planning_center_reports.services.build_instructions_pdf",
               side_effect=lambda path: path) as instr:
        yield {"event_id": ev, "periods": per, "checkins": cks, "guardians": guardians,
               "roster": roster_pdf, "volunteers": vol_pdf, "instructions": instr,
               "copies": copies, "out": str(tmp_path)}


def _dry(spec, pco, **kw):
    run_report(spec, dry_run=True, output_dir=pco["out"], **kw)


# ── Optional features are genuinely optional ──────────────────────────────────

class TestMinimalReportSkipsOptionalWork:
    def test_only_looks_up_its_own_event(self, pco):
        _dry(MINIMAL_SPEC, pco)
        assert [c.args[0] for c in pco["event_id"].call_args_list] == ["Clases de Niños"]

    def test_renders_no_route_column_and_no_summary(self, pco):
        _dry(MINIMAL_SPEC, pco)
        kwargs = pco["roster"].call_args.kwargs
        assert kwargs["show_route"] is False
        assert kwargs["attendance_summary"] is False

    def test_emits_only_the_roster(self, pco):
        _dry(MINIMAL_SPEC, pco)
        assert [p.rsplit("/", 1)[1] for p in pco["copies"]] == ["Roster.pdf"]
        pco["volunteers"].assert_not_called()
        pco["instructions"].assert_not_called()

    def test_never_calls_the_people_api_per_person(self, pco):
        """Details come from check-in sideloads; parents are one batched lookup."""
        _dry(MINIMAL_SPEC, pco)
        pco["guardians"].assert_called_once()
        assert sorted(pco["guardians"].call_args.args[0]) == ["p1", "p2"]


class TestFullReportUsesOptionalWork:
    def test_builds_a_route_map_from_the_configured_event(self, pco):
        _dry(FULL_SPEC, pco)
        assert "Rutas" in [c.args[0] for c in pco["event_id"].call_args_list]

    def test_renders_route_column_and_summary(self, pco):
        _dry(FULL_SPEC, pco)
        kwargs = pco["roster"].call_args.kwargs
        assert kwargs["show_route"] is True
        assert kwargs["attendance_summary"] is True

    def test_writes_instructions_next_to_each_roster_built_once(self, pco):
        _dry(FULL_SPEC, pco)
        names = sorted(p.rsplit("/", 1)[1] for p in pco["copies"])
        assert names == ["Instrucciones.pdf", "Roster.pdf", "Voluntarios.pdf"]
        pco["instructions"].assert_called_once()

    def test_volunteer_report_lands_in_its_own_folder(self, pco):
        _dry(FULL_SPEC, pco)
        vol = next(p for p in pco["copies"] if p.endswith("Voluntarios.pdf"))
        assert "/Voluntarios/B_Escuela_Dominical/" in vol

    def test_location_filter_skips_the_volunteer_report(self, pco):
        _dry(FULL_SPEC, pco, location_filter="Primaria")
        pco["volunteers"].assert_not_called()

    def test_volunteer_event_is_fetched_when_configured(self, pco):
        spec = ReportSpec(id="rutas", label="Rutas", pco_event="Rutas", volunteer_report=True,
                          volunteer_event="Junta de Rutas Attendance")
        _dry(spec, pco)
        assert "Junta de Rutas Attendance" in [c.args[0] for c in pco["event_id"].call_args_list]


class TestSharedRunContext:
    def test_each_period_is_fetched_once_across_reports(self, pco):
        """Both Sunday schools read the Rutas event — it must be fetched once."""
        ctx = RunContext(dry_run=True, output_dir=pco["out"])
        try:
            run_report(FULL_SPEC, ctx=ctx)
            run_report(FULL_SPEC, ctx=ctx)
        finally:
            ctx.close()
        fetched = [(c.args[0], tuple(c.args[1])) for c in pco["checkins"].call_args_list]
        assert len(fetched) == len(set(fetched))

    def test_run_all_keeps_going_after_a_failure(self, pco, monkeypatch):
        specs = (ReportSpec(id="a", label="A", pco_event="A"), ReportSpec(id="b", label="B", pco_event="B"))
        monkeypatch.setattr("planning_center_reports.services.enabled_reports", lambda: specs)
        pco["roster"].side_effect = [RuntimeError("boom"), "/tmp/x.pdf"]
        assert run_all(dry_run=True, output_dir=pco["out"]) is False
        assert pco["roster"].call_count == 2


# ── Drive layout ──────────────────────────────────────────────────────────────

class TestDriveFolders:
    @patch("planning_center_reports.services.upload_if_changed", return_value=True)
    @patch("planning_center_reports.services.upload_and_replace")
    @patch("planning_center_reports.services.get_or_create_folder", side_effect=lambda s, p, n: f"{p}/{n}")
    @patch("planning_center_reports.services.get_drive_service")
    def test_prefix_nests_the_location_folder(self, _svc, _folder, upload, upload_if, pco):
        run_report(FULL_SPEC)
        roster_folder = upload.call_args_list[0].args[1]
        assert roster_folder.endswith('/"B" Escuela Dominical/Clase Primaria')
        vol_folder = upload.call_args_list[-1].args[1]
        assert vol_folder.endswith('/Voluntarios/"B" Escuela Dominical')
        assert upload_if.call_args.args[3] == "Instrucciones.pdf"

    @patch("planning_center_reports.services.upload_and_replace")
    @patch("planning_center_reports.services.get_or_create_folder", side_effect=lambda s, p, n: f"{p}/{n}")
    @patch("planning_center_reports.services.get_drive_service")
    def test_no_prefix_keeps_the_flat_layout(self, _svc, _folder, upload, pco):
        run_report(MINIMAL_SPEC)
        assert upload.call_args.args[1].endswith("/Clase Primaria")
        assert upload.call_args.args[1].count("/") == 1

    def test_dry_run_mirrors_the_prefix_on_disk(self, pco):
        _dry(FULL_SPEC, pco)
        assert any("/B_Escuela_Dominical/Clase_Primaria/Roster.pdf" in p for p in pco["copies"])


# ── Missing or empty events ───────────────────────────────────────────────────

class TestMissingOrEmptyEvent:
    def test_missing_event_is_not_a_crash(self, pco, capsys):
        pco["event_id"].side_effect = Exception("Event 'Clases de Niños' not found")
        _dry(MINIMAL_SPEC, pco)
        assert "Nothing to generate" in capsys.readouterr().out
        pco["roster"].assert_not_called()

    def test_event_with_no_checkins_generates_nothing(self, pco, capsys):
        pco["checkins"].side_effect = lambda *_a: ([], [])
        _dry(MINIMAL_SPEC, pco)
        assert "Nothing to generate" in capsys.readouterr().out

    def test_event_with_no_periods_generates_nothing(self, pco, capsys):
        pco["periods"].return_value = []
        _dry(MINIMAL_SPEC, pco)
        assert "Nothing to generate" in capsys.readouterr().out

    def test_guardian_lookup_failure_still_writes_rosters(self, pco, capsys):
        pco["guardians"].side_effect = Exception("People API down")
        _dry(MINIMAL_SPEC, pco)
        assert "Could not look up parents" in capsys.readouterr().out
        pco["roster"].assert_called_once()
