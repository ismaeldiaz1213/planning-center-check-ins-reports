# backend/api.py
#
# FastAPI server providing:
#   - REST API under /api/*
#   - Static PDF serving under /previews/*
#   - IBL logo served at /ibl_logo.png
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

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Paths ──────────────────────────────────────────────────────────────────────
BACKEND_DIR  = Path(__file__).parent.resolve()   # .../backend/
PREVIEWS_DIR = BACKEND_DIR / "previews"
STATIC_DIR   = BACKEND_DIR / "static"
LOGO_PATH    = BACKEND_DIR / "ibl_logo.png"

# ── In-memory job store ────────────────────────────────────────────────────────
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="IBL Roster API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# PDF static files — /previews/{filename} → backend/previews/*.pdf
# Must be mounted BEFORE the SPA catch-all route.
PREVIEWS_DIR.mkdir(exist_ok=True)
app.mount("/previews", StaticFiles(directory=str(PREVIEWS_DIR)), name="previews")


@app.get("/ibl_logo.png", include_in_schema=False)
def serve_logo():
    if not LOGO_PATH.exists():
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(str(LOGO_PATH), media_type="image/png")


# ── Pydantic models ───────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    theme: Optional[str] = None
    type: Optional[str] = None


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


@app.get("/api/previews")
def list_previews():
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
def generate_preview(req: GenerateRequest):
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
def get_job(job_id: str, since: int = Query(default=0, ge=0)):
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


@app.post("/api/jobs/rutas/run", status_code=202)
def run_rutas():
    """Trigger python main.py Rutas in the background."""
    job_id = _create_job("rutas")
    _run_subprocess(job_id, [sys.executable, "main.py", "Rutas"])
    return {"job_id": job_id}


@app.post("/api/jobs/escuela/run", status_code=202)
def run_escuela():
    """Trigger python main.py 'Escuela Dominical' in the background."""
    job_id = _create_job("escuela")
    _run_subprocess(job_id, [sys.executable, "main.py", "Escuela Dominical"])
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
