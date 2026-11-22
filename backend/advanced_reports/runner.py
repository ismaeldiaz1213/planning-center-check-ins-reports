# advanced_reports/runner.py
#
# One execution = one church's run (plan §3.1). It loads only that church's
# settings, key and connection, runs the report engine with live Planning Center
# data, saves the PDFs into the church's run folder, and records status,
# progress, outputs, timings and usage on the run.
#
#   python -m advanced_reports.runner <org_id> <run_id>
#
# Locally the web service starts this as a subprocess; on Google Cloud the same
# entry point is the Cloud Run job. Milestone 1 delivers to the run folder
# (downloadable from the dashboard). Google Drive delivery with the church's own
# Google account is not connected yet.
#
# Progress and cancelling: every Planning Center call and every saved PDF is one
# "step". The dashboard shows the current step, and how far along the run is
# compared with the church's last finished run. Between steps the runner checks
# whether someone pressed Cancel.

from __future__ import annotations

import contextlib
import shutil
import sys
import time
from pathlib import Path

from advanced_reports.core import connections
from advanced_reports.core.store import Store, open_store
from advanced_reports.core.tenant_repo import TenantRepo, now_iso
from advanced_reports.modules import checkin_reports
from advanced_reports.settings import Settings, from_env
from planning_center_reports.delivery import slug
from planning_center_reports.services import RunContext, run_report

_LOG_LIMIT = 2000        # lines kept per run
_SAVE_EVERY_S = 0.7


class RunCancelled(BaseException):
    """Someone pressed Cancel. Not an Exception, so the engine's own
    "log it and carry on" handlers do not swallow it."""


class _Recorder:
    """Keeps the run document up to date while the engine works."""

    def __init__(self, repo: TenantRepo, run: dict, expected_steps: int | None, expected_s: float | None):
        self.repo, self.run = repo, run
        self.expected_steps, self.expected_s = expected_steps, expected_s
        self.steps = 0
        self.started = time.monotonic()
        self._partial = ""
        self._saved_at = 0.0
        self._checked_at = 0.0
        self.report = {"id": "", "label": "", "index": 0, "count": 0}

    # stdout of the engine → the run's log (kept for troubleshooting)
    def write(self, text: str) -> int:
        self._partial += text
        *lines, self._partial = self._partial.split("\n")
        if lines:
            self.run["log"] = (self.run["log"] + lines)[-_LOG_LIMIT:]
        return len(text)

    def flush(self) -> None:
        pass

    def step(self, phase: str, **detail) -> None:
        """One unit of work is about to happen: record it, and stop here if cancelled."""
        now = time.monotonic()
        if now - self._checked_at > 0.4:
            self._checked_at = now
            if self.repo.cancel_requested(self.run["id"]):
                raise RunCancelled()
        self.steps += 1
        elapsed = now - self.started
        fraction = eta = None
        if self.expected_steps:
            fraction = min(0.97, self.steps / self.expected_steps)
            if self.steps >= 5:
                eta = elapsed * (1 - fraction) / fraction
            elif self.expected_s:
                eta = self.expected_s * (1 - fraction)
        self.run["progress"] = {
            "phase": phase, "detail": detail, "report": dict(self.report), "steps": self.steps,
            "fraction": round(fraction, 3) if fraction is not None else None,
            "eta_s": round(eta) if eta is not None else None, "elapsed_s": round(elapsed),
        }
        if now - self._saved_at > _SAVE_EVERY_S:
            self.save()

    def save(self) -> None:
        self.repo.save_run(self.run)
        self._saved_at = time.monotonic()


class _WatchedPco:
    """The church's Planning Center client, reporting each call as a step."""

    def __init__(self, pco, recorder: _Recorder):
        self._pco, self._rec = pco, recorder
        self._sunday = 0
        self._sundays = 0

    def __getattr__(self, name):
        return getattr(self._pco, name)

    def get_event_id(self, event_name):
        self._rec.step("event", event=event_name)
        return self._pco.get_event_id(event_name)

    def get_event_periods_since(self, event_id, since, **kw):
        self._rec.step("sundays")
        periods = self._pco.get_event_periods_since(event_id, since, **kw)
        self._sunday, self._sundays = 0, len(periods)
        return periods

    def get_checkins_for_event_periods(self, event_id, event_period_ids):
        self._sunday += 1
        self._rec.step("checkins", sunday=self._sunday, of=max(self._sundays, self._sunday))
        return self._pco.get_checkins_for_event_periods(event_id, event_period_ids)

    def get_guardians(self, child_ids):
        self._rec.step("parents", kids=len(child_ids))
        return self._pco.get_guardians(child_ids)


class RunFolderDelivery:
    """Save each PDF into the church's run folder, mirroring the folder nesting,
    and remember which report and class each file belongs to."""

    def __init__(self, folder: Path, recorder: _Recorder, texts):
        self.folder, self._rec = folder, recorder
        self._kinds = {texts.t("file.roster"): "roster", texts.t("file.volunteers"): "volunteers",
                       texts.t("file.instructions"): "instructions"}
        self.outputs: list[dict] = []

    def deliver(self, path, folders, filename, fingerprint=None) -> None:
        kind = self._kinds.get(filename, "other")
        if kind != "instructions":
            self._rec.step("saving", kind=kind, location=folders[-1] if kind == "roster" else "")
        dest = self.folder.joinpath(*[slug(f) for f in folders])
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy(path, dest / filename)
        relative = (dest / filename).relative_to(self.folder)
        self.outputs.append({"path": str(relative), "bytes": (dest / filename).stat().st_size,
                             "kind": kind, "report": self._rec.report["id"],
                             "location": folders[-1] if kind != "volunteers" else ""})
        print(f"  ✓ Saved {'/'.join(folders)}/{filename}", flush=True)


def _last_finished(repo: TenantRepo) -> tuple[int | None, float | None]:
    for run in repo.runs(limit=10):
        steps = (run.get("usage") or {}).get("steps")
        if run["status"] == "succeeded" and steps:
            return steps, (run.get("timings") or {}).get("total_s")
    return None, None


def execute(settings: Settings, store: Store, org_id: str, run_id: str) -> bool:
    """Run every enabled report for one church. Returns True if all succeeded."""
    repo = TenantRepo(store, settings.vault, settings.files_dir, org_id)
    run = repo.run(run_id)
    if run is None:
        raise LookupError(f"run {run_id} not found for church {org_id}")
    run.update(status="running", started_at=now_iso())
    recorder = _Recorder(repo, run, *_last_finished(repo))
    recorder.save()
    started = time.perf_counter()
    ok, cancelled, pco, summary, delivery = False, False, None, [], None
    try:
        church = checkin_reports.church_config(
            org_id, repo.church(), repo.module(checkin_reports.MODULE_ID), repo.logo_path())
        reports = church.enabled_reports
        if not reports:
            raise RuntimeError("no reports are set up for this church yet")
        pco = connections.pco_client(repo, settings)
        delivery = RunFolderDelivery(repo.run_dir(run_id), recorder, church.texts)
        failed: list[str] = []
        with contextlib.redirect_stdout(recorder), \
                RunContext(church, _WatchedPco(pco, recorder), delivery) as ctx:
            for index, spec in enumerate(reports):
                recorder.report = {"id": spec.id, "label": spec.label, "index": index + 1, "count": len(reports)}
                print(f"\n{'═' * 60}\n{spec.label}\n{'═' * 60}", flush=True)
                try:
                    run_report(ctx, spec)
                except Exception as exc:
                    failed.append(spec.label)
                    print(f"\n  ✗ Report '{spec.id}' failed: {exc}", flush=True)
            summary = ctx.summary
        ok = not failed
        if failed:
            run["error"] = "Could not finish: " + ", ".join(failed)
    except RunCancelled:
        cancelled = True
        repo.discard_run_files(run_id)
        run["log"].append("Cancelled.")
    except Exception as exc:  # the run record must always reach a final state
        run["error"] = str(exc) or type(exc).__name__
        run["log"].append(f"✗ {run['error']}")
    outputs = [] if cancelled or delivery is None else sorted(delivery.outputs, key=lambda o: o["path"])
    run["status"] = "cancelled" if cancelled else "succeeded" if ok else "failed"
    run["finished_at"] = now_iso()
    run["progress"] = None
    run["outputs"] = outputs
    run["summary"] = [] if cancelled else summary
    run["totals"] = {} if cancelled else {
        "rosters": len(summary), **{k: sum(row[k] for row in summary) for k in ("active", "new", "inactive", "workers")}}
    run["timings"] = {"total_s": round(time.perf_counter() - started, 2)}
    run["usage"] = {"pco": pco.stats.as_dict() if pco is not None else {}, "steps": recorder.steps,
                    "files": len(outputs), "bytes": sum(o["bytes"] for o in outputs)}
    recorder.save()
    return ok


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: python -m advanced_reports.runner <org_id> <run_id>", file=sys.stderr)
        return 2
    settings = from_env()
    return 0 if execute(settings, open_store(settings), args[0], args[1]) else 1


if __name__ == "__main__":
    sys.exit(main())
