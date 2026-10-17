import os
from pathlib import Path

import pytest

from planning_center_reports import reports as _reports

# Pin the report registry to the shipped example config for the whole session.
# Without this the suite would assert against whatever reports.yaml the operator
# happens to have edited locally.
_EXAMPLE_CONFIG = Path(__file__).resolve().parents[2] / "reports.yaml.example"


def pytest_configure(config):
    os.environ["REPORTS_CONFIG"] = str(_EXAMPLE_CONFIG)
    _reports.load_reports(refresh=True)


@pytest.fixture(autouse=True)
def clear_google_client_id(monkeypatch):
    """Clear GOOGLE_CLIENT_ID before every test so api.py starts with auth disabled.
    Tests that need auth explicitly call monkeypatch.setenv("GOOGLE_CLIENT_ID", ...).
    This prevents load_dotenv (called when planning_center_reports is imported) from
    leaking the real GOOGLE_CLIENT_ID from .env into the test environment."""
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)


@pytest.fixture(autouse=True)
def reset_pco_pacing():
    """Each test starts with an empty rate window, so hundreds of mocked requests
    across the suite never trip the real 20-second throttle."""
    from planning_center_reports import pco_client
    pco_client._request_times.clear()
    pco_client._person_cache.clear()
    yield
