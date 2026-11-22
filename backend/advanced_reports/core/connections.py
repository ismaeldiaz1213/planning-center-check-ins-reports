# advanced_reports/core/connections.py
#
# Turn a church's stored Planning Center connection into a client for the engine.
#
#   "oauth"  the real thing: the church admin signed in with Planning Center
#   "pat"    a Personal Access Token (IBL's original credentials, imported by
#            importers/ibl.py so IBL can run before OAuth exists)
#   "demo"   the made-up church in demo.py; only when AR_DEV_LOGIN is on

from __future__ import annotations

from advanced_reports import demo
from advanced_reports.core import pco_oauth
from advanced_reports.core.tenant_repo import TenantRepo
from advanced_reports.settings import Settings
from planning_center_reports.pco_client import OAuthBearer, PcoClient, PersonalAccessToken


class NotConnected(Exception):
    """The church has no usable Planning Center connection."""


def pco_client(repo: TenantRepo, settings: Settings):
    conn = repo.secret("pco")
    if not conn:
        raise NotConnected("Planning Center is not connected")
    kind = conn.get("kind")
    if kind == "demo" and settings.dev_login:
        return demo.DemoPco(step_s=settings.demo_step_s)
    if kind == "pat":
        return PcoClient(PersonalAccessToken(conn["app_id"], conn["secret"]))
    if kind == "oauth":
        def renew() -> str:
            try:
                fresh = pco_oauth.refresh(settings.pco_client_id, settings.pco_client_secret,
                                          conn.get("refresh_token", ""))
            except pco_oauth.OAuthError:
                repo.update_church({"status": "needs_reconnect"})
                raise
            conn.update(fresh)
            repo.save_secret("pco", conn, kind="oauth", status="connected")
            return fresh["access_token"]
        return PcoClient(OAuthBearer(conn["access_token"], refresh=renew))
    raise NotConnected(f"unknown Planning Center connection kind {kind!r}")
