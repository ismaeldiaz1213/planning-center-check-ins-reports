# backend/api.py
#
# FastAPI server providing:
#   - REST API under /api/*
#   - Static PDF serving under /previews/*
#   - Church logo served at /logo.png
#   - Built React SPA served from backend/static/ when present
#
# Run from the project root or backend/ directory:
#   uvicorn backend.api:app --reload          (from project root)
#   uvicorn api:app --reload                  (from backend/)

from __future__ import annotations

import os
import sys
import threading
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.auth.transport import requests as _google_requests
from google.oauth2 import id_token as _google_id_token
from pydantic import BaseModel, Field

from planning_center_reports.reports import (
    VALID_THEMES,
    ReportConfigError,
    enabled_reports,
    get_report,
)

# ── Demo mode ─────────────────────────────────────────────────────────────────
# Set DEMO_MODE=true to serve a public demo: auth is bypassed, job runs use
# mock data via demo_run.py, and settings writes are accepted but not persisted.
DEMO_MODE = os.environ.get("DEMO_MODE", "").lower() in ("1", "true")

# ── Paths ──────────────────────────────────────────────────────────────────────
BACKEND_DIR  = Path(__file__).parent.resolve()   # .../backend/
PROJECT_DIR  = BACKEND_DIR.parent                # project root
ENV_PATH     = PROJECT_DIR / ".env"
PREVIEWS_DIR = BACKEND_DIR / "previews"
STATIC_DIR   = BACKEND_DIR / "static"
LOGO_PATH    = BACKEND_DIR / "logo.png"

# ── .env helpers ───────────────────────────────────────────────────────────────

def _read_dotenv() -> dict[str, str]:
    result: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            result[key.strip()] = val.strip()
    return result


def _write_dotenv(updates: dict[str, str]):
    existing_lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    written: set[str] = set()
    new_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.partition("=")[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                written.add(key)
                continue
        new_lines.append(line)
    for key, val in updates.items():
        if key not in written:
            new_lines.append(f"{key}={val}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n")
    for key, val in updates.items():
        os.environ[key] = val

# ── In-memory job store ────────────────────────────────────────────────────────
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

# ── CORS ──────────────────────────────────────────────────────────────────────
# In production (Cloud Run) the API and frontend share the same origin, so
# CORS is only needed for local development.
# Set ALLOWED_ORIGINS to a comma-separated list to override the defaults.
_DEV_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]


def _get_allowed_origins() -> list[str]:
    raw = os.environ.get("ALLOWED_ORIGINS", "").strip()
    if not raw:
        return list(_DEV_ORIGINS)
    return [o.strip() for o in raw.split(",") if o.strip()]


# ── Authentication ────────────────────────────────────────────────────────────
# Set GOOGLE_CLIENT_ID (OAuth 2.0 Web Client ID) to enable auth.
# When GOOGLE_CLIENT_ID is not set (local dev), all API routes are open.
# Set ALLOWED_GOOGLE_DOMAINS to a comma-separated list of domains to restrict
# access (e.g. "mychurch.org"). Leave unset to allow any Google account.


def _get_allowed_domains() -> set[str]:
    raw = os.environ.get("ALLOWED_GOOGLE_DOMAINS", "").strip()
    if not raw:
        return set()
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def _verify_google_token(authorization: Optional[str] = Header(default=None)) -> dict:
    if DEMO_MODE:
        return {"email": "demo@example.com", "name": "Demo User"}
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    if not client_id:
        return {}  # auth disabled — local dev without OAuth configured
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization[7:]
    try:
        idinfo = _google_id_token.verify_oauth2_token(
            token, _google_requests.Request(), client_id
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    email = idinfo.get("email", "")
    domain = email.split("@")[-1].lower() if "@" in email else ""
    allowed = _get_allowed_domains()
    if allowed and domain not in allowed:
        raise HTTPException(status_code=403, detail="Access restricted to authorised accounts")
    return idinfo

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Planning Center Roster API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

# PDF static files — /previews/{filename} → backend/previews/*.pdf
# Must be mounted BEFORE the SPA catch-all route.
PREVIEWS_DIR.mkdir(exist_ok=True)
app.mount("/previews", StaticFiles(directory=str(PREVIEWS_DIR)), name="previews")


@app.get("/logo.png", include_in_schema=False)
def serve_logo():
    if not LOGO_PATH.exists():
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(str(LOGO_PATH), media_type="image/png")


# ── Pydantic models ───────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    theme: Optional[str] = None
    type: Optional[str] = None


class RunJobRequest(BaseModel):
    weeks: Optional[int] = Field(default=None, ge=1, le=52)
    theme: Optional[str] = None


class ReportSettingsWrite(BaseModel):
    weeks: Optional[int] = Field(default=None, ge=1, le=52)
    theme: Optional[str] = None


class SettingsWrite(BaseModel):
    pco_app_id: Optional[str] = None
    pco_secret: Optional[str] = None
    google_drive_parent_folder_id: Optional[str] = None
    # Per-report overrides keyed by report id, e.g. {"escuela-b": {"weeks": 6}}.
    reports: Optional[dict[str, ReportSettingsWrite]] = None


# ── Internal helpers ──────────────────────────────────────────────────────────
def _create_job(job_type: str) -> str:
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "id": job_id,
            "type": job_type,
            "status": "running",
            "output": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
        }
    return job_id


def _run_subprocess(job_id: str, cmd: list[str]):
    """Spawn cmd in a background thread; capture merged stdout+stderr line by line."""
    def _worker():
        try:
            env = {**os.environ, "PYTHONPATH": str(BACKEND_DIR)}
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(BACKEND_DIR),
                env=env,
            )
            for raw_line in proc.stdout:
                line = raw_line.rstrip("\n")
                with _jobs_lock:
                    _jobs[job_id]["output"].append(line)
            proc.wait()
            status = "success" if proc.returncode == 0 else "failed"
        except Exception as exc:
            with _jobs_lock:
                _jobs[job_id]["output"].append(f"[API ERROR] {exc}")
            status = "failed"

        with _jobs_lock:
            _jobs[job_id]["status"] = status
            _jobs[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()

    threading.Thread(target=_worker, daemon=True).start()


# ── API routes ────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/auth/config")
def auth_config():
    """Return the Google OAuth client ID and demo mode flag for the frontend."""
    return {
        "google_client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
        "demo_mode": DEMO_MODE,
    }


@app.get("/api/previews")
def list_previews(_: dict = Depends(_verify_google_token)):
    """Return metadata for all PDFs in backend/previews/."""
    PREVIEWS_DIR.mkdir(exist_ok=True)
    files = []
    type_map = {
        "Roster":             "roster",
        "Escuela-Roster":     "escuela",
        "Direcciones-Roster": "direcciones",
    }
    for pdf in sorted(PREVIEWS_DIR.glob("*.pdf")):
        parts = pdf.stem.split("_", 1)
        theme    = parts[0] if len(parts) == 2 else "default"
        raw_type = parts[1] if len(parts) == 2 else pdf.stem
        files.append({
            "filename":   pdf.name,
            "theme":      theme,
            "type":       type_map.get(raw_type, raw_type.lower()),
            "size_bytes": pdf.stat().st_size,
            "url":        f"/previews/{pdf.name}",
        })
    return {"previews": files}


@app.post("/api/previews/generate", status_code=202)
def generate_preview(req: GenerateRequest, _: dict = Depends(_verify_google_token)):
    """Run preview.py in the background; return job_id immediately."""
    cmd = [sys.executable, "preview.py"]
    if req.type:
        cmd += ["--type", req.type]
    else:
        cmd += ["--type", "all"]
    if req.theme and req.theme != "default":
        cmd += ["--theme", req.theme]

    job_id = _create_job("preview")
    _run_subprocess(job_id, cmd)
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, since: int = Query(default=0, ge=0), _: dict = Depends(_verify_google_token)):
    """Return job status + output lines from index `since` onward."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    all_lines = job["output"]
    return {
        "id":          job["id"],
        "type":        job["type"],
        "status":      job["status"],
        "output":      all_lines[since:],
        "total_lines": len(all_lines),
        "started_at":  job["started_at"],
        "finished_at": job["finished_at"],
    }


@app.get("/api/reports")
def list_reports(_: dict = Depends(_verify_google_token)):
    """Return the reports configured in reports.yaml, for the dashboard tiles."""
    try:
        return {"reports": [spec.public_dict() for spec in enabled_reports()]}
    except ReportConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/settings")
def get_settings(_: dict = Depends(_verify_google_token)):
    """Return current editable settings (reads live env + .env file)."""
    env = _read_dotenv()
    def _get(key: str, default: str = "") -> str:
        return os.environ.get(key) or env.get(key, default)

    reports: dict[str, dict] = {}
    for spec in enabled_reports():
        raw_weeks = _get(f"{spec.env_prefix}_DEFAULT_WEEKS", "")
        raw_theme = _get(f"{spec.env_prefix}_DEFAULT_THEME", "")
        reports[spec.id] = {
            "label": spec.label,
            "weeks": int(raw_weeks) if raw_weeks.isdigit() else spec.default_weeks,
            "theme": raw_theme if raw_theme in VALID_THEMES else (spec.default_theme or ""),
        }

    return {
        "pco_app_id":                  _get("PCO_APP_ID"),
        "pco_secret":                  _get("PCO_SECRET"),
        "google_drive_parent_folder_id": _get("GOOGLE_DRIVE_PARENT_FOLDER_ID"),
        "reports":                     reports,
    }


@app.put("/api/settings")
def update_settings(body: SettingsWrite, _: dict = Depends(_verify_google_token)):
    """Persist settings changes to the .env file."""
    if DEMO_MODE:
        return {"ok": True}
    updates: dict[str, str] = {}
    if body.pco_app_id is not None:
        updates["PCO_APP_ID"] = body.pco_app_id
    if body.pco_secret is not None:
        updates["PCO_SECRET"] = body.pco_secret
    if body.google_drive_parent_folder_id is not None:
        updates["GOOGLE_DRIVE_PARENT_FOLDER_ID"] = body.google_drive_parent_folder_id

    for report_id, values in (body.reports or {}).items():
        try:
            spec = get_report(report_id)
        except ReportConfigError:
            raise HTTPException(status_code=404, detail=f"Unknown report '{report_id}'")
        if values.weeks is not None:
            updates[f"{spec.env_prefix}_DEFAULT_WEEKS"] = str(values.weeks)
        if values.theme is not None:
            updates[f"{spec.env_prefix}_DEFAULT_THEME"] = (
                values.theme if values.theme in VALID_THEMES else ""
            )

    if updates:
        _write_dotenv(updates)
    return {"ok": True}


@app.get("/api/jobs")
def list_jobs(_: dict = Depends(_verify_google_token)):
    """Return all jobs sorted newest-first."""
    with _jobs_lock:
        jobs = list(_jobs.values())
    jobs.sort(key=lambda j: j["started_at"], reverse=True)
    return {"jobs": jobs}


@app.post("/api/jobs/{report_id}/run", status_code=202)
def run_report_job(
    report_id: str,
    req: RunJobRequest = RunJobRequest(),
    _: dict = Depends(_verify_google_token),
):
    """Trigger a background roster run for one configured report.

    The report id doubles as the path segment, so the original
    /api/jobs/rutas/run and /api/jobs/escuela/run URLs keep working.
    """
    try:
        spec = get_report(report_id)
    except ReportConfigError:
        raise HTTPException(status_code=404, detail=f"Unknown report '{report_id}'")
    if not spec.enabled:
        raise HTTPException(status_code=404, detail=f"Report '{spec.id}' is disabled")

    weeks = req.weeks or spec.resolved_weeks()
    theme = req.theme or spec.resolved_theme() or ""
    if DEMO_MODE:
        cmd = [sys.executable, "demo_run.py", spec.id,
               theme if theme in VALID_THEMES else ""]
    else:
        cmd = [sys.executable, "main.py", spec.id, "--weeks", str(weeks)]
        if theme in VALID_THEMES:
            cmd += ["--theme", theme]

    job_id = _create_job(spec.id)
    _run_subprocess(job_id, cmd)
    return {"job_id": job_id}


# ── SPA catch-all (must be last) ──────────────────────────────────────────────
# Only wired up when the built React app exists in backend/static/.
# In local dev the Vite dev server on port 5173 handles the SPA.
if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    _assets = STATIC_DIR / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="spa-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        return FileResponse(str(STATIC_DIR / "index.html"))
