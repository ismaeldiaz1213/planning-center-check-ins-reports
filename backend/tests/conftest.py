import pytest


@pytest.fixture(autouse=True)
def clear_google_client_id(monkeypatch):
    """Clear GOOGLE_CLIENT_ID before every test so api.py starts with auth disabled.
    Tests that need auth explicitly call monkeypatch.setenv("GOOGLE_CLIENT_ID", ...).
    This prevents load_dotenv (called when planning_center_reports is imported) from
    leaking the real GOOGLE_CLIENT_ID from .env into the test environment."""
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
