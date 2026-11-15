# advanced_reports/runner.py
#
# One execution = one church's run (plan §3.1). It loads only that church's
# settings, key and connection, runs the report engine with live Planning Center
# data, saves the PDFs into the church's run folder, and records status, log,
# outputs, timings and usage on the run.
#
#   python -m advanced_reports.runner <org_id> <run_id>
#
# Locally the web service starts this as a subprocess; on Google Cloud the same
# entry point is the Cloud Run job. Milestone 1 delivers to the run folder
# (downloadable from the dashboard). Google Drive delivery with the church's own
# Google account is not connected yet.

from __future__ import annotations

import contextlib
import shutil
import sys
import time
from pathlib import Path

from advanced_reports.core import connections
from advanced_reports.core.store import FileStore, Store
from advanced_reports.core.tenant_repo import TenantRepo, now_iso
from advanced_reports.modules import checkin_reports
from advanced_reports.settings import Settings, from_env
from planning_center_reports.delivery import slug
from planning_center_reports.services import RunContext, run_all

_LOG_LIMIT = 2000        # lines kept per run
_FLUSH_EVERY_S = 1.0


class RunFolderDelivery:
    """Save each PDF into the church's run folder, mirroring the folder nesting."""

    def __init__(self, folder: Path):
        self.folder = folder

    def deliver(self, path, folders, filename, fingerprint=None) -> None:
        dest = self.folder.joinpath(*[slug(f) for f in folders])
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy(path, dest / filename)
        print(f"  ✓ Saved {'/'.join(folders)}/{filename}", flush=True)


class _RunLog:
    """Collects printed lines into the run document, saving about once a second."""

    def __init__(self, repo: TenantRepo, run: dict):
        self.repo, self.run = repo, run
        self._partial = ""
        self._saved_at = 0.0

    def write(self, text: str) -> int:
        self._partial += text
        *lines, self._partial = self._partial.split("\n")
        if lines:
            self.run["log"] = (self.run["log"] + lines)[-_LOG_LIMIT:]
            if time.monotonic() - self._saved_at > _FLUSH_EVERY_S:
                self.save()
        return len(text)

    def flush(self) -> None:
        pass

    def save(self) -> None:
        self.repo.save_run(self.run)
        self._saved_at = time.monotonic()


def execute(settings: Settings, store: Store, org_id: str, run_id: str) -> bool:
    """Run every enabled report for one church. Returns True if all succeeded."""
    repo = TenantRepo(store, settings.vault, settings.files_dir, org_id)
    run = repo.run(run_id)
    if run is None:
        raise LookupError(f"run {run_id} not found for church {org_id}")
    run.update(status="running", started_at=now_iso())
    repo.save_run(run)
    log = _RunLog(repo, run)
    started = time.perf_counter()
    ok, pco = False, None
    try:
        church = checkin_reports.church_config(
            org_id, repo.church(), repo.module(checkin_reports.MODULE_ID), repo.logo_path())
        if not church.enabled_reports:
            raise RuntimeError("no reports are set up for this church yet")
        pco = connections.pco_client(repo, settings)
        folder = repo.run_dir(run_id)
        with contextlib.redirect_stdout(log), RunContext(church, pco, RunFolderDelivery(folder)) as ctx:
            ok = run_all(ctx)
        run["outputs"] = sorted(
            ({"path": str(f.relative_to(folder)), "bytes": f.stat().st_size} for f in folder.rglob("*.pdf")),
            key=lambda o: o["path"])
        if not ok:
            run["error"] = "One or more reports failed; see the log."
    except Exception as exc:  # the run record must always reach a final state
        run["error"] = str(exc) or type(exc).__name__
        run["log"].append(f"✗ {run['error']}")
    run["status"] = "succeeded" if ok else "failed"
    run["finished_at"] = now_iso()
    run["timings"] = {"total_s": round(time.perf_counter() - started, 2)}
    run["usage"] = {"pco": pco.stats.as_dict() if pco is not None else {},
                    "files": len(run["outputs"]),
                    "bytes": sum(o["bytes"] for o in run["outputs"])}
    log.save()
    return ok


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: python -m advanced_reports.runner <org_id> <run_id>", file=sys.stderr)
        return 2
    settings = from_env()
    return 0 if execute(settings, FileStore(settings.store_dir), args[0], args[1]) else 1


if __name__ == "__main__":
    sys.exit(main())
