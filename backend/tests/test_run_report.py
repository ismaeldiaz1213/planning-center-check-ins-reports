# tests/test_run_report.py
#
# services.run_report / run_all with a stub Planning Center client and the PDF
# writers mocked.
#
# The flexibility guarantee still holds: a report that does not declare an
# optional feature must not make the PCO calls that feature needs. And the
# whole point of run_all: shared events are fetched once, not once per report.
# The last class runs two churches for real (PDFs included) to prove that one
# church's run leaves nothing behind for the next.

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pypdf import PdfReader

from planning_center_reports.church import Branding, ChurchConfig
from planning_center_reports.delivery import DriveServiceAccountDelivery, LocalDelivery
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


def church(*reports: ReportSpec, **kw) -> ChurchConfig:
    kw.setdefault("org_id", "test")
    kw.setdefault("name", "Iglesia de Prueba")
    kw.setdefault("timezone", "America/Chicago")
    kw.setdefault("language", "es")
    return ChurchConfig(reports=reports, **kw)


class StubPco:
    """The four PcoClient methods a run uses, as mocks."""

    def __init__(self, checkins=fake_checkins):
        self.get_event_id = Mock(side_effect=lambda n: f"id:{n}")
        self.get_event_periods_since = Mock(return_value=PERIODS)
        self.get_checkins_for_event_periods = Mock(side_effect=checkins)
        self.get_guardians = Mock(return_value={})


@pytest.fixture
def pco(monkeypatch, tmp_path):
    """A stub Planning Center client and mocked PDF writers; yields the mocks.

    `copies` records where a dry run (LocalDelivery) would save each file.
    """
    copies: list[str] = []
    monkeypatch.setattr("planning_center_reports.delivery.shutil.copy",
                        lambda src, dest: copies.append(dest))
    client = StubPco()
    with patch("planning_center_reports.services.generate_roster_pdf",
               side_effect=lambda roster, subtitle, path, ctx, **k: path) as roster_pdf, \
         patch("planning_center_reports.services.generate_volunteer_pdf",
               side_effect=lambda report, label, path, ctx: path) as vol_pdf, \
         patch("planning_center_reports.services.build_instructions_pdf",
               side_effect=lambda path, ctx: path) as instr:
        yield {"client": client, "event_id": client.get_event_id,
               "periods": client.get_event_periods_since,
               "checkins": client.get_checkins_for_event_periods,
               "guardians": client.get_guardians,
               "roster": roster_pdf, "volunteers": vol_pdf, "instructions": instr,
               "copies": copies, "out": str(tmp_path)}


def _ctx(pco, *reports, delivery=None) -> RunContext:
    return RunContext(church(*reports), pco["client"], delivery or LocalDelivery(pco["out"]))


def _dry(spec, pco, **kw):
    with _ctx(pco, spec) as ctx:
        run_report(ctx, spec, **kw)


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
        with _ctx(pco, FULL_SPEC) as ctx:
            run_report(ctx, FULL_SPEC)
            run_report(ctx, FULL_SPEC)
        fetched = [(c.args[0], tuple(c.args[1])) for c in pco["checkins"].call_args_list]
        assert len(fetched) == len(set(fetched))

    def test_run_all_keeps_going_after_a_failure(self, pco):
        specs = (ReportSpec(id="a", label="A", pco_event="A"), ReportSpec(id="b", label="B", pco_event="B"))
        pco["roster"].side_effect = [RuntimeError("boom"), "/tmp/x.pdf"]
        with _ctx(pco, *specs) as ctx:
            assert run_all(ctx) is False
        assert pco["roster"].call_count == 2

    def test_run_all_skips_disabled_reports(self, pco):
        specs = (ReportSpec(id="a", label="A", pco_event="A"),
                 ReportSpec(id="b", label="B", pco_event="B", enabled=False))
        with _ctx(pco, *specs) as ctx:
            assert run_all(ctx) is True
        assert [c.args[0] for c in pco["event_id"].call_args_list] == ["A"]

    def test_theme_precedence_is_call_then_report_then_church(self, pco):
        themed = ReportSpec(id="a", label="A", pco_event="A", default_theme="verano")
        plain = ReportSpec(id="b", label="B", pco_event="B")
        ch = church(themed, plain, theme="invierno")
        with RunContext(ch, pco["client"], LocalDelivery(pco["out"])) as ctx:
            run_report(ctx, themed)
            run_report(ctx, plain)
            run_report(ctx, themed, theme="otono")
        assert [c.args[3].theme_key for c in pco["roster"].call_args_list] == ["verano", "invierno", "otono"]


# ── Drive layout ──────────────────────────────────────────────────────────────

class TestDriveFolders:
    @patch("planning_center_reports.delivery.upload_if_changed", return_value=True)
    @patch("planning_center_reports.delivery.upload_and_replace")
    @patch("planning_center_reports.delivery.get_or_create_folder", side_effect=lambda s, p, n: f"{p}/{n}")
    @patch("planning_center_reports.delivery.get_drive_service")
    def test_prefix_nests_the_location_folder(self, _svc, _folder, upload, upload_if, pco):
        with _ctx(pco, FULL_SPEC, delivery=DriveServiceAccountDelivery("PARENT", "key.json")) as ctx:
            run_report(ctx, FULL_SPEC)
        roster_folder = upload.call_args_list[0].args[1]
        assert roster_folder == 'PARENT/"B" Escuela Dominical/Clase Primaria'
        vol_folder = upload.call_args_list[-1].args[1]
        assert vol_folder == 'PARENT/Voluntarios/"B" Escuela Dominical'
        assert upload_if.call_args.args[3] == "Instrucciones.pdf"

    @patch("planning_center_reports.delivery.upload_and_replace")
    @patch("planning_center_reports.delivery.get_or_create_folder", side_effect=lambda s, p, n: f"{p}/{n}")
    @patch("planning_center_reports.delivery.get_drive_service")
    def test_no_prefix_keeps_the_flat_layout(self, connect, _folder, upload, pco):
        with _ctx(pco, MINIMAL_SPEC, delivery=DriveServiceAccountDelivery("PARENT", "key.json")) as ctx:
            run_report(ctx, MINIMAL_SPEC)
        assert upload.call_args.args[1] == "PARENT/Clase Primaria"
        connect.assert_called_once_with("key.json")

    @patch("planning_center_reports.delivery.get_drive_service")
    def test_drive_is_not_contacted_when_nothing_is_generated(self, connect, pco):
        pco["periods"].return_value = []
        with _ctx(pco, MINIMAL_SPEC, delivery=DriveServiceAccountDelivery("PARENT", "key.json")) as ctx:
            run_report(ctx, MINIMAL_SPEC)
        connect.assert_not_called()

    def test_drive_delivery_needs_a_parent_folder(self):
        with pytest.raises(ValueError):
            DriveServiceAccountDelivery("", "key.json")

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


# ── Two churches, one process ─────────────────────────────────────────────────

def _people_checkins(location: str, people: list[tuple[str, str, str]]):
    included = [{"type": "Location", "id": "loc", "attributes": {"name": location}}] + [
        {"type": "Person", "id": pid, "attributes": {"first_name": first, "last_name": last, "child": True}}
        for pid, first, last in people
    ]

    def fetch(_event_id, period_ids):
        (ep,) = period_ids
        return [_checkin(pid, "loc", ep) for pid, _f, _l in people], included
    return fetch


def _text(path: Path) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(str(path)).pages)


class TestTwoChurchesRunBackToBack:
    """Real PDFs, two churches, same process: nothing crosses over.

    Both churches use the same Planning Center ids on purpose (event "Sunday",
    periods ep0–ep3, location "loc", person ids p1/p2), so anything cached by id
    outside the RunContext would show up as one church's people on the other's roster.
    """

    SPEC = ReportSpec(id="sunday", label="Sunday", pco_event="Sunday")

    def _run(self, ch: ChurchConfig, client: StubPco, out: Path) -> None:
        with RunContext(ch, client, LocalDelivery(str(out))) as ctx:
            assert run_all(ctx) is True

    def test_no_people_language_theme_or_cache_crossover(self, tmp_path):
        libertad = church(
            self.SPEC, org_id="100", name="Iglesia Uno", language="es", theme="primavera",
            branding=Branding(feedback_url="https://uno.example/feedback"),
        )
        liberty = church(
            ReportSpec(id="sunday", label="Sunday", pco_event="Sunday", volunteer_report=True),
            org_id="200", name="Church Two", language="en", timezone="America/New_York",
        )
        pco_a = StubPco(_people_checkins("Clase Uno", [("p1", "Abril", "Alcaraz"), ("p2", "Benito", "Benavides")]))
        pco_b = StubPco(_people_checkins("Class Two", [("p1", "Zoe", "Young"), ("p2", "Walt", "Xavier")]))

        self._run(libertad, pco_a, tmp_path / "a1")
        self._run(liberty, pco_b, tmp_path / "b")
        self._run(libertad, pco_a, tmp_path / "a2")

        files = lambda d: sorted(str(p.relative_to(tmp_path / d)) for p in (tmp_path / d).rglob("*.pdf"))  # noqa: E731
        assert files("a1") == files("a2") == ["Clase_Uno/Roster.pdf"]
        assert files("b") == ["Class_Two/Roster.pdf", "Volunteers/Sunday/Volunteers.pdf"]

        es = _text(tmp_path / "a1" / "Clase_Uno" / "Roster.pdf")
        en = _text(tmp_path / "b" / "Class_Two" / "Roster.pdf")
        for own in ("Alcaraz", "Benavides", "Campaña de Primavera", "Página 1"):
            assert own in es and own not in en
        for own in ("Young", "Xavier", "Page 1"):
            assert own in en and own not in es
        assert "Campaign" not in en and "Campaña" not in en
        # The second church's run in between changed nothing for the first.
        assert _text(tmp_path / "a2" / "Clase_Uno" / "Roster.pdf") == es

        # Each client was asked only for its own church's work.
        assert pco_a.get_checkins_for_event_periods.call_count == 2 * len(PERIODS)
        assert pco_b.get_checkins_for_event_periods.call_count == len(PERIODS)

    def test_each_run_reads_its_own_churchs_calendar(self, tmp_path):
        """History start is computed in the church's timezone, per run."""
        seen = {}
        for name, tz in (("a", "Pacific/Kiritimati"), ("b", "Pacific/Pago_Pago")):
            client = StubPco()
            client.get_event_periods_since = Mock(return_value=[])
            with RunContext(church(self.SPEC, org_id=name, timezone=tz), client,
                            LocalDelivery(str(tmp_path / name))) as ctx:
                run_report(ctx, self.SPEC)
                seen[name] = (ctx.today, client.get_event_periods_since.call_args.kwargs["tz"].key)
        assert seen["a"][1] == "Pacific/Kiritimati" and seen["b"][1] == "Pacific/Pago_Pago"
        assert (seen["a"][0] - seen["b"][0]).days in (1, 2)   # UTC+14 vs UTC-11
