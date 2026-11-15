# advanced_reports/app.py
#
# The platform's web service (plan §3.1, Milestone 1 steps 4–5).
#
#   AR_DEV_LOGIN=1 uvicorn advanced_reports.app:create_app --factory --port 8000
#
# Isolation rules this file follows (plan §3.7):
#   • the church id comes only from the signed session cookie, never from the
#     URL, the body or a header;
#   • handlers get a TenantRepo for that church and build no storage paths;
#   • no Planning Center or Google secret is ever sent to the browser.

from __future__ import annotations

import secrets
import subprocess
import sys
from pathlib import Path
from typing import Protocol
from zoneinfo import available_timezones

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from advanced_reports import demo
from advanced_reports.core import connections, pco_oauth, session
from advanced_reports.core.store import FileStore, Store
from advanced_reports.core.tenant_repo import TenantRepo
from advanced_reports.importers import ibl
from advanced_reports.modules import checkin_reports
from advanced_reports.settings import Settings, from_env
from planning_center_reports.i18n import LANGUAGES
from planning_center_reports.reports import VALID_THEMES, ReportConfigError

_STATIC = Path(__file__).resolve().parent / "static"
_BACKEND = Path(__file__).resolve().parent.parent
_STATE_COOKIE = "ar_oauth_state"
_BRANDING = ("verse_text", "verse_ref", "help_contact", "video_url", "feedback_url")


class Launcher(Protocol):
    def launch(self, org_id: str, run_id: str) -> None: ...


class SubprocessLauncher:
    """Start the runner as its own process: one execution, one church."""

    def launch(self, org_id: str, run_id: str) -> None:
        subprocess.Popen([sys.executable, "-m", "advanced_reports.runner", org_id, run_id],
                         cwd=_BACKEND, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class ChurchUpdate(BaseModel):
    name: str | None = None
    timezone: str | None = None
    language: str | None = None
    theme: str | None = None
    branding: dict[str, str] | None = None


class ReportsUpdate(BaseModel):
    reports: list[dict]


class DevLogin(BaseModel):
    church: str


def create_app(settings: Settings | None = None, store: Store | None = None,
               launcher: Launcher | None = None) -> FastAPI:
    settings = settings or from_env()
    store = store or FileStore(settings.store_dir)
    launcher = launcher or SubprocessLauncher()
    app = FastAPI(title="Advanced Reports for Planning Center", docs_url=None, redoc_url=None)

    def repo_for(org_id: str) -> TenantRepo:
        return TenantRepo(store, settings.vault, settings.files_dir, org_id)

    # ── Session ───────────────────────────────────────────────────────────────
    def current(request: Request) -> dict:
        who = session.read(settings.session_secret, request.cookies.get(session.COOKIE))
        if who is None:
            raise HTTPException(401, "Not signed in")
        return who

    def church_repo(who: dict = Depends(current)) -> TenantRepo:
        repo = repo_for(who["org"])
        if not repo.exists():          # disconnected in another tab, or a stale cookie
            raise HTTPException(401, "Not signed in")
        return repo

    def changing(request: Request) -> None:
        """Requests that change something must come from our own page (CSRF)."""
        if request.headers.get("x-ar-csrf") != "1":
            raise HTTPException(403, "Missing X-AR-CSRF header")

    def sign_in(response: Response, org_id: str, person_id: str, name: str) -> None:
        repo_for(org_id).touch_member(person_id, name)
        response.set_cookie(
            session.COOKIE, session.issue(settings.session_secret, org_id=org_id,
                                          person_id=person_id, name=name),
            max_age=session.MAX_AGE, httponly=True, samesite="lax", secure=settings.secure_cookies)

    # ── Sign-in ───────────────────────────────────────────────────────────────
    def dev_churches() -> list[dict]:
        if not settings.dev_login:
            return []
        found = [{"id": "demo", "name": demo.CHURCH["name"], "note": "made-up data"}]
        if ibl.available():
            found.append({"id": "ibl", "name": "Iglesia Bautista Libertad",
                          "note": "live Planning Center data, from .env"})
        return found

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/auth/config")
    def auth_config():
        return {"pco_oauth": bool(settings.pco_client_id and settings.pco_client_secret),
                "dev_churches": dev_churches()}

    @app.post("/auth/dev/login", dependencies=[Depends(changing)])
    def dev_login(body: DevLogin, response: Response):
        if body.church not in {c["id"] for c in dev_churches()}:
            raise HTTPException(404, "Not available")
        if body.church == "ibl":
            repo = repo_for(ibl.DEV_ORG_ID)
            ibl.import_church(repo)
        else:
            repo = repo_for(demo.ORG_ID)
            if not repo.exists():
                repo.create_church(**demo.CHURCH)
                repo.save_module(checkin_reports.MODULE_ID, {"reports": [
                    checkin_reports.spec_to_dict(s) for s in checkin_reports.parse(demo.REPORTS)]})
            repo.save_secret("pco", {"kind": "demo"}, kind="demo", status="connected")
        sign_in(response, repo.org_id, "dev-admin", "Local developer")
        return {"ok": True}

    @app.get("/auth/pco/login")
    def pco_login():
        if not settings.pco_client_id:
            raise HTTPException(404, "Planning Center sign-in is not configured")
        state = secrets.token_urlsafe(24)
        redirect = RedirectResponse(pco_oauth.authorize_url(settings.pco_client_id, settings.base_url, state))
        redirect.set_cookie(_STATE_COOKIE, state, max_age=600, httponly=True, samesite="lax",
                            secure=settings.secure_cookies)
        return redirect

    @app.get("/auth/pco/callback")
    def pco_callback(request: Request, code: str = "", state: str = ""):
        expected = request.cookies.get(_STATE_COOKIE, "")
        if not code or not state or not expected or not secrets.compare_digest(state, expected):
            raise HTTPException(400, "Sign-in could not be verified. Please try again.")
        try:
            token = pco_oauth.exchange_code(settings.pco_client_id, settings.pco_client_secret,
                                            settings.base_url, code)
            who = pco_oauth.who_am_i(token["access_token"])
        except pco_oauth.OAuthError as exc:
            raise HTTPException(502, str(exc)) from exc
        if not who["admin"]:
            raise HTTPException(403, "Only a Planning Center organization administrator can set this up.")
        repo = repo_for(who["org_id"])
        if not repo.exists():
            repo.create_church(name=who["org_name"] or "My church", timezone="America/Chicago", language="en")
        else:
            repo.update_church({"status": "active"})
        repo.save_secret("pco", token, kind="oauth", status="connected", connected_by=who["name"])
        redirect = RedirectResponse("/", status_code=303)
        redirect.delete_cookie(_STATE_COOKIE)
        sign_in(redirect, repo.org_id, who["person_id"], who["name"])
        return redirect

    @app.post("/auth/logout", dependencies=[Depends(changing)])
    def logout(response: Response):
        response.delete_cookie(session.COOKIE)
        return {"ok": True}

    # ── The signed-in church ──────────────────────────────────────────────────
    def public_church(repo: TenantRepo) -> dict:
        doc = repo.church()
        return {"name": doc["name"], "timezone": doc["timezone"], "language": doc["language"],
                "theme": doc.get("theme"), "status": doc.get("status", "active"),
                "branding": {k: (doc.get("branding") or {}).get(k, "") for k in _BRANDING},
                "has_logo": repo.logo_path() is not None}

    @app.get("/api/me")
    def me(who: dict = Depends(current), repo: TenantRepo = Depends(church_repo)):
        return {"person": {"name": who["name"]}, "church": public_church(repo),
                "connections": {"pco": repo.connection("pco"), "google": repo.connection("google")},
                "options": {"languages": list(LANGUAGES), "themes": sorted(VALID_THEMES)}}

    @app.get("/api/church")
    def get_church(repo: TenantRepo = Depends(church_repo)):
        return public_church(repo)

    @app.put("/api/church", dependencies=[Depends(changing)])
    def put_church(body: ChurchUpdate, repo: TenantRepo = Depends(church_repo)):
        doc, changes = repo.church(), {}
        if body.name is not None:
            if not body.name.strip():
                raise HTTPException(422, "The church name cannot be empty")
            changes["name"] = body.name.strip()[:120]
        if body.timezone is not None:
            if body.timezone not in available_timezones():
                raise HTTPException(422, f"Unknown time zone {body.timezone!r}")
            changes["timezone"] = body.timezone
        if body.language is not None:
            if body.language not in LANGUAGES:
                raise HTTPException(422, f"Unknown language {body.language!r}")
            changes["language"] = body.language
        if "theme" in body.model_fields_set:
            if body.theme and body.theme not in VALID_THEMES:
                raise HTTPException(422, f"Unknown theme {body.theme!r}")
            changes["theme"] = body.theme or None
        if body.branding is not None:
            unknown = sorted(set(body.branding) - set(_BRANDING))
            if unknown:
                raise HTTPException(422, f"Unknown branding field(s) {unknown}")
            for key in ("video_url", "feedback_url"):
                url = body.branding.get(key, "")
                if url and not url.startswith("https://"):
                    raise HTTPException(422, f"{key} must start with https://")
            changes["branding"] = {**(doc.get("branding") or {}),
                                   **{k: v.strip()[:300] for k, v in body.branding.items()}}
        repo.update_church(changes)
        return public_church(repo)

    # ── Check-In Reports module ───────────────────────────────────────────────
    @app.get("/api/modules/checkin_reports")
    def get_reports(repo: TenantRepo = Depends(church_repo)):
        return {"reports": (repo.module(checkin_reports.MODULE_ID) or {}).get("reports", [])}

    @app.put("/api/modules/checkin_reports", dependencies=[Depends(changing)])
    def put_reports(body: ReportsUpdate, repo: TenantRepo = Depends(church_repo)):
        try:
            specs = checkin_reports.parse(body.reports) if body.reports else ()
        except ReportConfigError as exc:
            raise HTTPException(422, str(exc)) from exc
        reports = [checkin_reports.spec_to_dict(s) for s in specs]
        repo.save_module(checkin_reports.MODULE_ID, {"reports": reports})
        return {"reports": reports}

    # ── Planning Center lookups (for choosing events) ─────────────────────────
    def pco(repo: TenantRepo):
        try:
            return connections.pco_client(repo, settings)
        except connections.NotConnected as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/pco/events")
    def pco_events(repo: TenantRepo = Depends(church_repo)):
        try:
            return {"events": pco(repo).list_events()}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(502, "Planning Center could not be reached") from exc

    @app.get("/api/pco/events/{event_id}/locations")
    def pco_locations(event_id: str, repo: TenantRepo = Depends(church_repo)):
        if not event_id.replace("-", "").isalnum():
            raise HTTPException(404, "Unknown event")
        try:
            return {"locations": pco(repo).get_locations(event_id)}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(502, "Planning Center could not be reached") from exc

    # ── Runs ──────────────────────────────────────────────────────────────────
    def public_run(run: dict, with_log: bool) -> dict:
        out = {k: run.get(k) for k in ("id", "trigger", "started_by", "status", "created_at",
                                       "started_at", "finished_at", "error", "usage", "timings")}
        out["files"] = len(run.get("outputs") or [])
        if with_log:
            out["log"] = run.get("log") or []
            out["outputs"] = run.get("outputs") or []
        return out

    @app.post("/api/runs", status_code=202, dependencies=[Depends(changing)])
    def start_run(who: dict = Depends(current), repo: TenantRepo = Depends(church_repo)):
        if not (repo.module(checkin_reports.MODULE_ID) or {}).get("reports"):
            raise HTTPException(409, "Set up at least one report first")
        if repo.active_run():
            raise HTTPException(409, "A run is already in progress for this church")
        run = repo.create_run("manual", started_by=who["name"])
        launcher.launch(repo.org_id, run["id"])
        return public_run(run, with_log=False)

    @app.get("/api/runs")
    def list_runs(repo: TenantRepo = Depends(church_repo)):
        return {"runs": [public_run(r, with_log=False) for r in repo.runs()]}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str, repo: TenantRepo = Depends(church_repo)):
        run = repo.run(run_id)
        if run is None:
            raise HTTPException(404, "Run not found")
        return public_run(run, with_log=True)

    @app.get("/api/runs/{run_id}/files/{file_path:path}")
    def run_file(run_id: str, file_path: str, repo: TenantRepo = Depends(church_repo)):
        target = repo.run_file(run_id, file_path)
        if target is None or target.suffix != ".pdf":
            raise HTTPException(404, "File not found")
        return FileResponse(target, media_type="application/pdf", content_disposition_type="inline",
                            headers={"Cache-Control": "private, no-store"})

    # ── Disconnect ────────────────────────────────────────────────────────────
    @app.post("/api/disconnect", dependencies=[Depends(changing)])
    def disconnect(response: Response, repo: TenantRepo = Depends(church_repo)):
        repo.delete_everything()
        response.delete_cookie(session.COOKIE)
        return {"ok": True}

    # ── The dashboard page ────────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(_STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    return app
