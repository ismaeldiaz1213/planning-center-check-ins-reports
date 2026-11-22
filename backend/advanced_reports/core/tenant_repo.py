# advanced_reports/core/tenant_repo.py
#
# TenantRepo(org_id): everything stored for ONE church. It is the only code that
# touches the document store or the file store (core/blobs.py), and every path
# it builds starts with churches/{org_id} (plan §3.7 rule 2). Files are
# encrypted with the church's data key before they leave this class. Route handlers and the
# runner get a TenantRepo for the signed-in church and can reach nothing else.

from __future__ import annotations

import hashlib
import re
import secrets
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from advanced_reports.core import crypto
from advanced_reports.core.blobs import BlobStore, LocalBlobs, check_key
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
    def __init__(self, store: Store, vault: crypto.Vault, files: BlobStore | str | Path, org_id: str):
        if not _ORG_ID.match(str(org_id)):
            raise ValueError(f"not a church id: {org_id!r}")
        self.org_id = str(org_id)
        self._store = store
        self._vault = vault
        self._root = f"churches/{self.org_id}"
        self._blobs = LocalBlobs(files) if isinstance(files, (str, Path)) else files

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


    def start_run(self, trigger: str, started_by: str = "") -> dict | None:
        """Create a run unless one is already queued or running. None means "busy".

        Race-free: the newest run is read, then a claim document named after it
        is created atomically. Two requests that read the same newest run race
        for the same claim, and only one wins. A request that reads after the
        winner's run exists sees it as active and backs off.
        """
        if self.active_run():
            return None
        newest = self.runs(limit=1)
        after = newest[0]["id"] if newest else "none"
        if not self._store.create(f"{self._root}/run_claims/after-{after}", {"at": now_iso()}):
            return None
        return self.create_run(trigger, started_by)

    def fail_to_start(self, run: dict, reason: str) -> None:
        """The run was recorded but could not be started: close it so it does not block."""
        run.update(status="failed", finished_at=now_iso(), error=reason)
        run["log"] = [*run.get("log", []), f"✗ {reason}"]
        self.save_run(run)

    def active_run(self) -> dict | None:
        """The church's queued or running run, if any (one at a time)."""
        cutoff = (datetime.now(UTC) - STALE_RUN).strftime("%Y-%m-%dT%H:%M:%SZ")
        for run in self.runs(limit=5):
            if run["status"] in ("queued", "running") and run["created_at"] > cutoff:
                return run
        return None

    # ── Files a run produced (encrypted in the file store) ────────────────────
    def _run_key(self, run_id: str, relative: str) -> str:
        if not _RUN_ID.match(run_id):
            raise ValueError(f"not a run id: {run_id!r}")
        key = f"{self._root}/runs/{run_id}/{relative}"
        check_key(key)
        return key

    def save_run_file(self, run_id: str, relative: str, data: bytes) -> None:
        key = self._run_key(run_id, relative)
        self._blobs.put(key, crypto.seal_bytes(self._key(), data, key))

    def run_file(self, run_id: str, relative: str) -> bytes | None:
        """A file of this church's run, decrypted, or None. Never another church's."""
        try:
            key = self._run_key(run_id, relative)
        except ValueError:
            return None
        blob = self._blobs.get(key)
        if blob is None:
            return None
        try:
            return crypto.unseal_bytes(self._key(), blob, key)
        except crypto.DecryptError:  # damaged, moved, or left from before files were encrypted
            return None

    def discard_run_files(self, run_id: str) -> None:
        if _RUN_ID.match(run_id):
            self._blobs.delete_prefix(f"{self._root}/runs/{run_id}")

    def keep_only_files_of(self, run_id: str) -> None:
        """Decision D2: once a run succeeds, delete every older run's PDFs."""
        for run in self.runs(limit=1000):
            if run["id"] != run_id and run.get("outputs") and not run.get("files_deleted"):
                self.discard_run_files(run["id"])
                run["files_deleted"] = True
                self.save_run(run)

    # ── Logo ──────────────────────────────────────────────────────────────────
    def has_logo(self) -> bool:
        return self._blobs.exists(f"{self._root}/logo.png")

    def save_logo(self, png: bytes) -> None:
        key = f"{self._root}/logo.png"
        self._blobs.put(key, crypto.seal_bytes(self._key(), png, key))

    def logo_path(self) -> str | None:
        """The logo as a local file, for the PDF renderer. Written to a private
        temporary file named after its content, so it is written once per version."""
        key = f"{self._root}/logo.png"
        blob = self._blobs.get(key)
        if blob is None:
            return None
        try:
            png = crypto.unseal_bytes(self._key(), blob, key)
        except crypto.DecryptError:
            return None
        folder = Path(tempfile.gettempdir()) / "advanced-reports-logos"
        folder.mkdir(mode=0o700, exist_ok=True)
        path = folder / f"{self.org_id}-{hashlib.sha256(png).hexdigest()[:16]}.png"
        if not path.is_file():
            fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
            with open(fd, "wb") as fh:
                fh.write(png)
            Path(tmp).replace(path)
        return str(path)

    # ── Disconnect ────────────────────────────────────────────────────────────
    def delete_everything(self) -> None:
        """Remove the church, every document under it, and its files (plan §3.5)."""
        self._blobs.delete_prefix(self._root)
        self._store.delete_tree(self._root)
