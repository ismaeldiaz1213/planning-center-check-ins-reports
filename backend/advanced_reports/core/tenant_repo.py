# advanced_reports/core/tenant_repo.py
#
# TenantRepo(org_id): everything stored for ONE church. It is the only code that
# touches the document store or the files folder, and every path it builds
# starts with churches/{org_id} (plan §3.7 rule 2). Route handlers and the
# runner get a TenantRepo for the signed-in church and can reach nothing else.

from __future__ import annotations

import re
import secrets
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from advanced_reports.core import crypto
from advanced_reports.core.store import Store

_ORG_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

# A run that has not finished after this long is treated as dead, so one crashed
# runner cannot block a church's runs forever.
STALE_RUN = timedelta(minutes=30)


def all_org_ids(store: Store) -> list[str]:
    """Every church id. The one place that looks across churches: the scheduler
    uses it to find whose weekly run is due, then works through a TenantRepo."""
    return [path.split("/", 1)[1] for path, _doc in store.list("churches")]


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class TenantRepo:
    def __init__(self, store: Store, vault: crypto.Vault, files_root: str | Path, org_id: str):
        if not _ORG_ID.match(str(org_id)):
            raise ValueError(f"not a church id: {org_id!r}")
        self.org_id = str(org_id)
        self._store = store
        self._vault = vault
        self._root = f"churches/{self.org_id}"
        self._files = Path(files_root) / "churches" / self.org_id

    # ── The church ────────────────────────────────────────────────────────────
    def church(self) -> dict | None:
        return self._store.get(self._root)

    def exists(self) -> bool:
        return self.church() is not None

    def create_church(self, *, name: str, timezone: str, language: str, **extra) -> dict:
        if self.exists():
            raise ValueError(f"church {self.org_id} already exists")
        doc = {
            "name": name, "timezone": timezone, "language": language, "theme": None,
            "branding": {}, "status": "active", "plan": "founding", "created_at": now_iso(),
            "wrapped_data_key": self._vault.new_wrapped_key(self.org_id),
            **extra,
        }
        self._store.set(self._root, doc)
        return doc

    def update_church(self, changes: dict) -> dict:
        doc = self._require()
        doc.update({k: v for k, v in changes.items() if k != "wrapped_data_key"})
        self._store.set(self._root, doc)
        return doc

    def _require(self) -> dict:
        doc = self.church()
        if doc is None:
            raise LookupError(f"church {self.org_id} does not exist")
        return doc

    def _key(self) -> bytes:
        return self._vault.unwrap(self._require()["wrapped_data_key"], self.org_id)

    # ── Encrypted secrets (Planning Center and Google connections) ────────────
    def save_secret(self, name: str, value: dict, **public) -> None:
        """Store `value` encrypted; `public` fields (status, who connected) stay readable."""
        path = f"{self._root}/connections/{name}"
        self._store.set(path, {**public, "updated_at": now_iso(),
                               "sealed": crypto.seal(self._key(), value, path)})

    def secret(self, name: str) -> dict | None:
        path = f"{self._root}/connections/{name}"
        doc = self._store.get(path)
        return crypto.unseal(self._key(), doc["sealed"], path) if doc else None

    def connection(self, name: str) -> dict | None:
        """The readable part of a connection (never the secret itself)."""
        doc = self._store.get(f"{self._root}/connections/{name}")
        return {k: v for k, v in doc.items() if k != "sealed"} if doc else None

    # ── Module settings ───────────────────────────────────────────────────────
    def module(self, module_id: str) -> dict | None:
        return self._store.get(f"{self._root}/modules/{module_id}")

    def save_module(self, module_id: str, settings: dict) -> None:
        self._store.set(f"{self._root}/modules/{module_id}", settings)

    # ── Members ───────────────────────────────────────────────────────────────
    def touch_member(self, person_id: str, name: str) -> None:
        self._store.set(f"{self._root}/members/{person_id}",
                        {"name": name, "role": "admin", "last_login": now_iso()})

    # ── Runs ──────────────────────────────────────────────────────────────────
    def create_run(self, trigger: str, started_by: str = "") -> dict:
        run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)
        run = {"id": run_id, "trigger": trigger, "started_by": started_by, "status": "queued",
               "created_at": now_iso(), "started_at": None, "finished_at": None,
               "log": [], "outputs": [], "summary": [], "totals": {}, "usage": {}, "timings": {},
               "progress": None, "error": None}
        self._store.set(f"{self._root}/runs/{run_id}", run)
        return run

    def run(self, run_id: str) -> dict | None:
        if not _RUN_ID.match(run_id):
            return None
        return self._store.get(f"{self._root}/runs/{run_id}")

    def save_run(self, run: dict) -> None:
        self._store.set(f"{self._root}/runs/{run['id']}", run)

    def runs(self, limit: int = 20) -> list[dict]:
        found = [doc for _path, doc in self._store.list(f"{self._root}/runs")]
        return sorted(found, key=lambda r: r["id"], reverse=True)[:limit]

    def request_cancel(self, run_id: str) -> None:
        """Ask a run to stop. Kept apart from the run document, which only the runner writes."""
        self._store.set(f"{self._root}/runs/{run_id}/signals/cancel", {"at": now_iso()})

    def cancel_requested(self, run_id: str) -> bool:
        return self._store.get(f"{self._root}/runs/{run_id}/signals/cancel") is not None

    def discard_run_files(self, run_id: str) -> None:
        if _RUN_ID.match(run_id):
            shutil.rmtree(self._files / "runs" / run_id, ignore_errors=True)

    def active_run(self) -> dict | None:
        """The church's queued or running run, if any (one at a time)."""
        cutoff = (datetime.now(UTC) - STALE_RUN).strftime("%Y-%m-%dT%H:%M:%SZ")
        for run in self.runs(limit=5):
            if run["status"] in ("queued", "running") and run["created_at"] > cutoff:
                return run
        return None

    # ── Files a run produced ──────────────────────────────────────────────────
    def run_dir(self, run_id: str) -> Path:
        if not _RUN_ID.match(run_id):
            raise ValueError(f"not a run id: {run_id!r}")
        folder = self._files / "runs" / run_id
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def run_file(self, run_id: str, relative: str) -> Path | None:
        """A file inside this church's run folder, or None. Never outside it."""
        if not _RUN_ID.match(run_id):
            return None
        base = (self._files / "runs" / run_id).resolve()
        target = (base / relative).resolve()
        if base not in target.parents or not target.is_file():
            return None
        return target

    # ── Logo ──────────────────────────────────────────────────────────────────
    def logo_path(self) -> str | None:
        path = self._files / "logo.png"
        return str(path) if path.is_file() else None

    def save_logo(self, png: bytes) -> None:
        self._files.mkdir(parents=True, exist_ok=True)
        (self._files / "logo.png").write_bytes(png)

    # ── Disconnect ────────────────────────────────────────────────────────────
    def delete_everything(self) -> None:
        """Remove the church, every document under it, and its files (plan §3.5)."""
        self._store.delete_tree(self._root)
        shutil.rmtree(self._files, ignore_errors=True)
