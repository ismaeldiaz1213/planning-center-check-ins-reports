# tests/golden/conftest.py
#
# Every golden test runs with the clock frozen and builds IBL's church
# explicitly (harness.ibl_church), so nothing comes from the environment.

import pytest
import time_machine

from . import harness
from .fake_pco import FakePCO


@pytest.fixture
def update_golden(request) -> bool:
    return harness.update_requested(request.config)


@pytest.fixture(autouse=True)
def frozen_clock():
    with time_machine.travel(harness.FROZEN_NOW, tick=False):
        yield


@pytest.fixture
def fake_pco(monkeypatch):
    """Serve the fake Planning Center through requests.get, with no real waiting."""
    fake = FakePCO()
    monkeypatch.setattr("planning_center_reports.pco_client.requests.get", fake.get)
    monkeypatch.setattr("planning_center_reports.pco_client.time.sleep", lambda _s: None)
    return fake
