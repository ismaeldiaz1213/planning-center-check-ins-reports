# tests/golden/test_golden_pipeline.py
#
# Golden snapshots of whole runs: run_all() for IBL's church against the fake
# Planning Center (fake_pco.py), once uploading to a recorded fake Drive (the
# service-account delivery IBL uses) and once as a dry run (local delivery).
#
# What is pinned, per report config:
#   manifest.json   every delivered file, in order, with its Drive folder path,
#                   how it was uploaded, its page count, the dry-run file tree,
#                   and the number of Planning Center requests by endpoint
#   files/**.txt    the text and links of every PDF
#
# This is the safety net for the engine refactor: client, pagination, roster
# building, parent lookups, rendering, filenames and folders in one comparison.

import shutil
from pathlib import Path

import pytest
import yaml

from planning_center_reports import delivery, services
from planning_center_reports.pco_client import PcoClient, PersonalAccessToken
from planning_center_reports.reports import parse_reports

from . import harness

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIGS = {
    # '"B" Escuela Dominical' is not in the fake Planning Center, so this run
    # also covers "configured before the event exists".
    "example": PROJECT_ROOT / "reports.yaml.example",
    # IBL's three reports; the "C" session has no Volunteer check-ins yet.
    "ibl": harness.FIXTURE_DIR / "ibl_reports.yaml",
}


class FakeDrive:
    """Records what the engine would do in Google Drive. Folder ids are paths."""

    def __init__(self, keep_dir: Path):
        self.keep_dir = keep_dir
        self.uploads: list[dict] = []

    def folder(self, _service, parent_id: str, name: str) -> str:
        return f"{parent_id} / {name}"

    def _record(self, folder_id: str, local_path: str, name: str, mode: str) -> None:
        kept = self.keep_dir / f"{len(self.uploads):03d}.pdf"
        shutil.copy(local_path, kept)
        self.uploads.append({"folder": folder_id, "name": name, "upload": mode, "kept": kept})

    def replace(self, _service, folder_id, local_path, name=None):
        self._record(folder_id, local_path, name, "always replace")

    def if_changed(self, _service, folder_id, local_path, name, fingerprint):
        self._record(folder_id, local_path, name, f"only if fingerprint changes ({fingerprint})")
        return True


def _safe(text: str) -> str:
    return text.replace(" / ", "/").replace('"', "'")


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_full_run(name, tmp_path, monkeypatch, update_golden, fake_pco):
    path = CONFIGS[name]
    church = harness.ibl_church(parse_reports(yaml.safe_load(path.read_text(encoding="utf-8")), path.name))
    kept = tmp_path / "kept"
    kept.mkdir()
    drive = FakeDrive(kept)
    monkeypatch.setattr(delivery, "get_drive_service", lambda _key_path: object())
    monkeypatch.setattr(delivery, "get_or_create_folder", drive.folder)
    monkeypatch.setattr(delivery, "upload_and_replace", drive.replace)
    monkeypatch.setattr(delivery, "upload_if_changed", drive.if_changed)

    def run(destination) -> tuple[bool, dict]:
        pco = PcoClient(PersonalAccessToken("golden-app-id", "golden-secret"))
        fake_pco.requests.clear()
        with services.RunContext(church, pco, destination) as ctx:
            ok = services.run_all(ctx)
        counts = fake_pco.request_counts()
        assert pco.stats.requests == counts["total"], "the client's counter disagrees with the server"
        return ok, counts

    # ── Run 1: the weekly job, uploading to Drive ──
    ok, requests = run(delivery.DriveServiceAccountDelivery(church.drive_parent_folder_id, "credentials.json"))

    # Each distinct PDF text is stored once; the manifest says which snapshot
    # holds each delivered file (the same Instrucciones.pdf goes to every folder).
    delivered, snapshot_of, texts = [], {}, {}
    for item in drive.uploads:
        text = harness.pdf_snapshot(item["kept"])
        key = snapshot_of.setdefault(text, f"{_safe(item['folder'])}/{item['name']}.txt")
        texts[key] = text
        delivered.append({
            "drive_folder": item["folder"],
            "filename": item["name"],
            "upload": item["upload"],
            "pages": int(text.split("\n", 1)[0].removeprefix("pages: ")),
            "snapshot": f"files/{key}",
        })

    # ── Run 2: the same job as --dry-run, to pin the local file tree ──
    out = tmp_path / "out"
    ok_dry, requests_dry = run(delivery.LocalDelivery(str(out)))
    tree = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())

    manifest = {
        "all_reports_succeeded": ok,
        "dry_run_succeeded": ok_dry,
        "pco_requests_per_run": requests,
        "delivered": delivered,
        "dry_run_files": tree,
    }
    harness.check(f"pipeline/{name}/manifest.json", harness.to_json(manifest), update_golden)
    for key, text in texts.items():
        harness.check(f"pipeline/{name}/files/{key}", text, update_golden)
    assert len(tree) == len(delivered), "dry run and Drive run produced a different number of files"
    assert requests == requests_dry, "dry run made different Planning Center requests"
