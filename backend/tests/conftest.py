import os
from pathlib import Path

import pytest

from planning_center_reports import legacy as _legacy

# Pin the report registry to the shipped example config for the whole session.
# Without this the suite would assert against whatever reports.yaml the operator
# happens to have edited locally.
_EXAMPLE_CONFIG = Path(__file__).resolve().parents[2] / "reports.yaml.example"


def pytest_addoption(parser):
    # Golden snapshots (tests/golden/) are IBL's PDF text, filenames and folder
    # paths. They only change on purpose: pytest --update-golden (or UPDATE_GOLDEN=1).
    parser.addoption("--update-golden", action="store_true", default=False,
                     help="Rewrite the golden snapshots in tests/golden/snapshots/ instead of comparing.")


def pytest_configure(config):
    os.environ["REPORTS_CONFIG"] = str(_EXAMPLE_CONFIG)
    _legacy.load_reports(refresh=True)


@pytest.fixture(autouse=True)
def clear_google_client_id(monkeypatch):
    """Clear GOOGLE_CLIENT_ID before every test so api.py starts with auth disabled.
    Tests that need auth explicitly call monkeypatch.setenv("GOOGLE_CLIENT_ID", ...).
    This prevents load_dotenv (called when planning_center_reports.legacy is imported)
    from leaking the real GOOGLE_CLIENT_ID from .env into the test environment."""
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
