# tests/golden/test_golden_config.py
#
# Golden snapshots of what reports.yaml parses into, for the shipped example
# and for IBL's file (fixtures/ibl_reports.yaml, a copy of the tracked
# reports.yaml). The IBL importer and the Firestore settings format must carry
# every one of these values across.

import dataclasses
import os
import warnings
from datetime import date
from pathlib import Path

import pytest
import yaml

from planning_center_reports import legacy
from planning_center_reports.reports import parse_reports

from . import harness

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIGS = {
    "example": PROJECT_ROOT / "reports.yaml.example",
    "ibl": harness.FIXTURE_DIR / "ibl_reports.yaml",
}


def _describe(spec) -> dict:
    return {
        **dataclasses.asdict(spec),
        "derived": {
            "pdf_subtitle": spec.pdf_subtitle,
            "env_prefix": legacy.env_prefix(spec),
            "resolved_weeks": legacy.resolved_weeks(spec),
            "resolved_theme": legacy.resolved_theme(spec),
            "history_start": spec.history_start(date.today()),
            "public_dict": legacy.public_dict(spec),
        },
    }


@pytest.fixture(autouse=True)
def no_report_overrides(monkeypatch):
    for name in list(os.environ):
        if name.endswith(("_DEFAULT_WEEKS", "_DEFAULT_THEME")):
            monkeypatch.delenv(name)


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_parsed_reports(name, update_golden):
    path = CONFIGS[name]
    specs = parse_reports(yaml.safe_load(path.read_text(encoding="utf-8")), source=path.name)
    harness.check(f"config/{name}.json", harness.to_json([_describe(s) for s in specs]), update_golden)


def test_ibl_fixture_matches_tracked_reports_yaml():
    """The fixture is a copy. Warn (don't fail) when the live file has moved on,
    so the snapshot gets refreshed deliberately rather than by accident."""
    live = PROJECT_ROOT / "reports.yaml"
    if live.exists() and live.read_text(encoding="utf-8") != CONFIGS["ibl"].read_text(encoding="utf-8"):
        warnings.warn(
            "reports.yaml differs from tests/golden/fixtures/ibl_reports.yaml — the IBL golden "
            "snapshots no longer describe the live config. Copy it over and run pytest --update-golden.",
            stacklevel=1,
        )


def test_legacy_defaults_are_ibls_settings(monkeypatch):
    """The golden tests build IBL's church by hand (harness.ibl_church). This
    ties that hand-written church to what legacy.py builds from an empty
    environment, so the two cannot drift apart."""
    for name in (*legacy.DEFAULTS, "GOOGLE_DRIVE_PARENT_FOLDER_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GOOGLE_DRIVE_PARENT_FOLDER_ID", harness.FAKE_DRIVE_PARENT)
    built = legacy.church()
    assert dataclasses.replace(built, reports=()) == harness.ibl_church()
    assert legacy.setting("RUTAS_SUBTITLE") == harness.IBL_RUTAS_SUBTITLE
