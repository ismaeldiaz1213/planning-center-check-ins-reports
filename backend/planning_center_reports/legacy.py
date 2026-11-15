# planning_center_reports/legacy.py
#
# The single-church adapter: IBL's original setup, where one process serves one
# church configured by a .env file and reports.yaml.
#
# This is the ONLY module that reads church settings from the environment,
# loads .env, or keeps module-level state (the parsed reports.yaml). It turns
# all of that into the explicit objects the engine takes — ChurchConfig,
# PcoClient, Delivery, RunContext — so main.py, the old Cloud Run job, the web
# UI (api.py) and the maintenance scripts behave exactly as they did before the
# engine learned about more than one church.
#
# The platform (advanced_reports/) never imports this module.

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import yaml
from dotenv import load_dotenv

from planning_center_reports.church import Branding, ChurchConfig
from planning_center_reports.config import LOGO_PATH
from planning_center_reports.delivery import Delivery, DriveServiceAccountDelivery, LocalDelivery
from planning_center_reports.pco_client import PcoClient, PersonalAccessToken
from planning_center_reports.pdf.context import RenderContext
from planning_center_reports.reports import (
    VALID_THEMES,
    ReportConfigError,
    ReportSpec,
    find_report,
    parse_reports,
)
from planning_center_reports.services import RunContext

_PACKAGE_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _PACKAGE_DIR.parent
_PROJECT_DIR = _BACKEND_DIR.parent

# Search for .env starting from the project root, then backend/.
# This handles: local dev (root .env), Docker (env vars injected, no .env needed).
load_dotenv(_PROJECT_DIR / ".env")   # project root
load_dotenv(_BACKEND_DIR / ".env")   # backend/ (fills in anything still unset)

# ── IBL's defaults ────────────────────────────────────────────────────────────
# Used when the matching environment variable is not set.
LANGUAGE = "es"
DEFAULTS = {
    "CHURCH_NAME":          "Iglesia Bautista Libertad",
    "CHURCH_TIMEZONE":      "America/Chicago",
    "CHURCH_VERSE_TEXT":    '"Id por todo el mundo y predicad el evangelio a toda criatura"',
    "CHURCH_VERSE_REF":     "Marcos 16:15 — RV1960",
    "RUTAS_SUBTITLE":       "Ministerio de Autobuses",
    # Video walkthrough linked (and QR-coded) on the Instrucciones.pdf cover page.
    "CHECKIN_VIDEO_URL":    "https://drive.google.com/file/d/1yTSZM-FTPZHbKlRrMizAm06eUM-E6Mc4/view",
    # Feedback form linked from every PDF — questions, confusion, ideas, venting.
    "FEEDBACK_FORM_URL":    "https://docs.google.com/forms/d/e/"
                            "1FAIpQLSfSflUQmzCsL1TekFt_lQVCddGIInJw0QRoBjE8f6VrX0Hz6g/viewform",
    # Who volunteers should find when the app can't sort something out.
    "CHECKIN_HELP_CONTACT": "Hna. Lira — cuarto de impresoras",
}


def setting(name: str) -> str | None:
    """An environment setting, falling back to IBL's default for it."""
    return os.getenv(name, DEFAULTS.get(name))


# ── reports.yaml ──────────────────────────────────────────────────────────────

def default_reports() -> tuple[ReportSpec, ...]:
    """The reports used when no reports.yaml exists: the original hardcoded
    "Rutas" + "Escuela Dominical" behaviour."""
    return (
        ReportSpec(
            id="rutas",
            label="Rutas",
            pco_event="Rutas",
            icon="🚌",
            subtitle=setting("RUTAS_SUBTITLE"),   # "Ministerio de Autobuses" unless overridden
            outputs=("simple",),
            demo_locations=("Ruta 1 - Bus", "Ruta 2 - Van", "Ruta 3 - Carro"),
        ),
        ReportSpec(
            id="escuela",
            label="Escuela Dominical",
            pco_event="Escuela Dominical",
            icon="📚",
            outputs=("simple",),
            route_source_event="Rutas",
            show_route=True,
            attendance_summary=True,
            demo_locations=("Clase Primaria", "Clase Secundaria"),
        ),
    )


_cache: tuple[ReportSpec, ...] | None = None


def config_path() -> Path | None:
    """Return the reports config file that will be used, or None if there is none."""
    override = os.environ.get("REPORTS_CONFIG", "").strip()
    if override:
        p = Path(override).expanduser()
        if not p.exists():
            raise ReportConfigError(f"REPORTS_CONFIG points at a missing file: {p}")
        return p
    for candidate in (_PROJECT_DIR / "reports.yaml", _BACKEND_DIR / "reports.yaml"):
        if candidate.exists():
            return candidate
    return None


def load_reports(refresh: bool = False) -> tuple[ReportSpec, ...]:
    """Return every configured report (enabled and disabled), cached after first call."""
    global _cache
    if _cache is not None and not refresh:
        return _cache

    path = config_path()
    if path is None:
        _cache = default_reports()
        return _cache

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ReportConfigError(f"{path}: could not parse YAML — {exc}") from exc

    _cache = parse_reports(raw, source=str(path))
    return _cache


def enabled_reports() -> tuple[ReportSpec, ...]:
    """Reports the UI and schedulers should offer."""
    return tuple(s for s in load_reports() if s.enabled)


def get_report(key: str) -> ReportSpec:
    """Resolve a configured report by id, then by exact PCO event name."""
    return find_report(load_reports(), key)


# ── Per-report environment overrides ──────────────────────────────────────────
# The web UI's Settings panel writes <PREFIX>_DEFAULT_WEEKS / _DEFAULT_THEME to
# .env. Precedence: CLI flag → environment variable → reports.yaml.

def env_prefix(spec: ReportSpec) -> str:
    """Prefix for a report's env-var overrides, e.g. 'rutas' → 'RUTAS'.

    Chosen so the pre-existing RUTAS_DEFAULT_WEEKS / ESCUELA_DEFAULT_WEEKS
    names keep working without migration.
    """
    return spec.id.upper().replace("-", "_")


def resolved_weeks(spec: ReportSpec) -> int:
    """default_weeks, unless <PREFIX>_DEFAULT_WEEKS overrides it in the environment."""
    raw = os.environ.get(f"{env_prefix(spec)}_DEFAULT_WEEKS", "").strip()
    if raw.isdigit() and 1 <= int(raw) <= 52:
        return int(raw)
    return spec.default_weeks


def resolved_theme(spec: ReportSpec) -> str | None:
    """default_theme, unless <PREFIX>_DEFAULT_THEME overrides it in the environment."""
    raw = os.environ.get(f"{env_prefix(spec)}_DEFAULT_THEME", "").strip()
    if raw in VALID_THEMES:
        return raw
    return spec.default_theme


def resolved(spec: ReportSpec) -> ReportSpec:
    """The spec with its environment overrides applied, as the engine should run it."""
    return replace(spec, default_weeks=resolved_weeks(spec), default_theme=resolved_theme(spec))


def public_dict(spec: ReportSpec) -> dict:
    """The subset of a spec the frontend needs (no PCO event names)."""
    return {
        "id":            spec.id,
        "label":         spec.label,
        "icon":          spec.icon,
        "outputs":       list(spec.outputs),
        "show_route":    spec.show_route,
        "default_weeks": resolved_weeks(spec),
        "default_theme": resolved_theme(spec) or "",
    }


# ── Engine objects ────────────────────────────────────────────────────────────

def branding() -> Branding:
    return Branding(
        logo_path=LOGO_PATH,
        verse_text=setting("CHURCH_VERSE_TEXT"),
        verse_ref=setting("CHURCH_VERSE_REF"),
        help_contact=setting("CHECKIN_HELP_CONTACT"),
        video_url=setting("CHECKIN_VIDEO_URL"),
        feedback_url=setting("FEEDBACK_FORM_URL"),
    )


def church() -> ChurchConfig:
    """The one church this install serves, from .env and reports.yaml."""
    return ChurchConfig(
        org_id="legacy",
        name=setting("CHURCH_NAME"),
        timezone=setting("CHURCH_TIMEZONE"),
        language=LANGUAGE,
        branding=branding(),
        drive_parent_folder_id=os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID"),
        reports=tuple(resolved(s) for s in load_reports()),
    )


def render_context(theme: str | None = None) -> RenderContext:
    """Words, branding and colours for drawing a PDF outside a run (previews, demo)."""
    return RenderContext.for_church(church(), theme)


def pco_client() -> PcoClient:
    """A client signed in with the Personal Access Token in .env."""
    return PcoClient(PersonalAccessToken(os.getenv("PCO_APP_ID"), os.getenv("PCO_SECRET")))


def drive_credentials_path() -> str:
    """The service-account key file. GOOGLE_APPLICATION_CREDENTIALS says where it is
    on Cloud Run (the secret is mounted outside /app); otherwise it sits in backend/,
    which is also where the local Docker bind-mount puts it."""
    return os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", str(_BACKEND_DIR / "credentials.json"))


def delivery(dry_run: bool = False, output_dir: str = "./out") -> Delivery:
    if dry_run:
        return LocalDelivery(output_dir)
    return DriveServiceAccountDelivery(os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID"), drive_credentials_path())


def run_context(dry_run: bool = False, output_dir: str = "./out") -> RunContext:
    """Everything a run needs, built from .env and reports.yaml."""
    return RunContext(church(), pco_client(), delivery(dry_run, output_dir))
