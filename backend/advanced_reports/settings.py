# advanced_reports/settings.py
#
# Process-level settings for the platform (not church settings: those live in
# the store). Read from the environment once, at start-up.
#
#   AR_DATA_DIR            where the local document store and run files live
#   AR_MASTER_KEY          base64 32-byte key that wraps every church's data key
#   AR_SESSION_SECRET      signs session cookies
#   AR_DEV_LOGIN=1         local development only: sign in without Planning
#                          Center OAuth, as one of the built-in dev churches
#   AR_BASE_URL            public address, used for OAuth redirect URIs
#   PCO_OAUTH_CLIENT_ID / PCO_OAUTH_CLIENT_SECRET
#   GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET   "Connect Google Drive"
#   AR_DISPATCH_KEY        shared secret the scheduler sends to /internal/dispatch
#   AR_FIRESTORE_PROJECT   keep documents in this Google Cloud project's Firestore
#                          (unset: one JSON file per document under AR_DATA_DIR)
#   AR_FIRESTORE_DATABASE  Firestore database id (default "(default)")
#   AR_BUCKET              keep run PDFs and logos in this Cloud Storage bucket
#                          (unset: files under AR_DATA_DIR)
#   AR_RUNNER_JOB          start runs as executions of this Cloud Run job,
#                          projects/<p>/locations/<r>/jobs/<name> (unset: a subprocess)
#
# With AR_DEV_LOGIN=1 a missing master key or session secret is generated and
# kept in AR_DATA_DIR, so a local demo needs no setup. Without it both are
# required: production never invents its own keys.

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from advanced_reports.core.crypto import Vault

_BACKEND = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    master_key_b64: str
    session_secret: str
    dev_login: bool = False
    base_url: str = "http://localhost:8000"
    pco_client_id: str = ""
    pco_client_secret: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    dispatch_key: str = ""        # shared secret for POST /internal/dispatch; empty turns the route off
    demo_step_s: float = 0.0      # pause per Planning Center call for the sample church, so progress is visible
    firestore_project: str = ""   # empty: FileStore under data_dir
    firestore_database: str = "(default)"
    bucket: str = ""              # empty: LocalBlobs under data_dir/files
    runner_job: str = ""          # empty: SubprocessLauncher

    @property
    def vault(self) -> Vault:
        return Vault.from_b64(self.master_key_b64)

    @property
    def store_dir(self) -> Path:
        return self.data_dir / "store"

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    @property
    def secure_cookies(self) -> bool:
        return self.base_url.startswith("https://")


def _dev_value(data_dir: Path, name: str, make) -> str:
    path = data_dir / name
    if not path.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(make(), encoding="utf-8")
        path.chmod(0o600)
    return path.read_text(encoding="utf-8").strip()


def from_env(env: dict | None = None) -> Settings:
    env = os.environ if env is None else env
    dev = str(env.get("AR_DEV_LOGIN", "")).lower() in ("1", "true")
    data_dir = Path(env.get("AR_DATA_DIR") or _BACKEND.parent / "out" / "platform-data").resolve()
    master = env.get("AR_MASTER_KEY", "")
    session = env.get("AR_SESSION_SECRET", "")
    if dev:
        master = master or _dev_value(data_dir, "dev-master.key", Vault.generate_b64)
        session = session or _dev_value(data_dir, "dev-session.key", lambda: secrets.token_urlsafe(48))
    if not master or not session:
        raise RuntimeError("AR_MASTER_KEY and AR_SESSION_SECRET are required "
                           "(or set AR_DEV_LOGIN=1 for local development)")
    return Settings(
        data_dir=data_dir, master_key_b64=master, session_secret=session, dev_login=dev,
        base_url=(env.get("AR_BASE_URL") or "http://localhost:8000").rstrip("/"),
        pco_client_id=env.get("PCO_OAUTH_CLIENT_ID", ""),
        pco_client_secret=env.get("PCO_OAUTH_CLIENT_SECRET", ""),
        google_client_id=env.get("GOOGLE_OAUTH_CLIENT_ID", ""),
        google_client_secret=env.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
        dispatch_key=env.get("AR_DISPATCH_KEY", ""),
        demo_step_s=float(env.get("AR_DEMO_STEP_SECONDS") or (0.2 if dev else 0)),
        firestore_project=env.get("AR_FIRESTORE_PROJECT", "").strip(),
        firestore_database=env.get("AR_FIRESTORE_DATABASE", "").strip() or "(default)",
        bucket=env.get("AR_BUCKET", "").strip(),
        runner_job=env.get("AR_RUNNER_JOB", "").strip(),
    )
