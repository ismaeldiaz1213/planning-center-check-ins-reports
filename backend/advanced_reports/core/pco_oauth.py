# advanced_reports/core/pco_oauth.py
#
# Planning Center OAuth: the sign-in redirect, exchanging the code, refreshing a
# token, and asking Planning Center who signed in and for which organization.
#
# First real sign-in: 2026-11-21, locally, against IBL's organization (app
# "Advanced Reports", owned by IBL for now). Authorize, code exchange, /people/v2,
# /people/v2/me and the site_administrator admin check all worked as written.
# Token refresh has not yet been exercised against the real service.

from __future__ import annotations

import time
from urllib.parse import urlencode

import requests

AUTHORIZE_URL = "https://api.planningcenteronline.com/oauth/authorize"
TOKEN_URL = "https://api.planningcenteronline.com/oauth/token"
API = "https://api.planningcenteronline.com"
SCOPES = "people check_ins"


class OAuthError(Exception):
    pass


def redirect_uri(base_url: str) -> str:
    return f"{base_url}/auth/pco/callback"


def authorize_url(client_id: str, base_url: str, state: str) -> str:
    return AUTHORIZE_URL + "?" + urlencode({
        "client_id": client_id, "redirect_uri": redirect_uri(base_url),
        "response_type": "code", "scope": SCOPES, "state": state,
    })


def _token_request(payload: dict, http=requests) -> dict:
    response = http.post(TOKEN_URL, data=payload, timeout=30)
    if response.status_code != 200:
        raise OAuthError(f"Planning Center refused the token request ({response.status_code})")
    body = response.json()
    if not body.get("access_token"):
        raise OAuthError("Planning Center returned no access token")
    return {
        "kind": "oauth",
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token", ""),
        "expires_at": int(time.time()) + int(body.get("expires_in") or 7200),
    }


def exchange_code(client_id: str, client_secret: str, base_url: str, code: str, http=requests) -> dict:
    return _token_request({
        "grant_type": "authorization_code", "code": code, "client_id": client_id,
        "client_secret": client_secret, "redirect_uri": redirect_uri(base_url),
    }, http)


def refresh(client_id: str, client_secret: str, refresh_token: str, http=requests) -> dict:
    if not refresh_token:
        raise OAuthError("no refresh token stored; the church must reconnect")
    return _token_request({
        "grant_type": "refresh_token", "refresh_token": refresh_token,
        "client_id": client_id, "client_secret": client_secret,
    }, http)


def who_am_i(access_token: str, http=requests) -> dict:
    """{"org_id", "org_name", "time_zone", "person_id", "name", "admin"} for a fresh token."""
    headers = {"Authorization": f"Bearer {access_token}"}

    def get(path: str) -> dict:
        response = http.get(f"{API}{path}", headers=headers, timeout=30)
        if response.status_code != 200:
            raise OAuthError(f"Planning Center refused {path} ({response.status_code})")
        return response.json()["data"]

    org, me = get("/people/v2"), get("/people/v2/me")
    attrs = me.get("attributes", {})
    return {
        "org_id": str(org["id"]),
        "org_name": org.get("attributes", {}).get("name") or "",
        "time_zone": org.get("attributes", {}).get("time_zone") or "",
        "person_id": str(me["id"]),
        "name": attrs.get("name") or " ".join(filter(None, [attrs.get("first_name"), attrs.get("last_name")])),
        # Organization administrator. Confirmed on real data 2026-11-21.
        "admin": bool(attrs.get("site_administrator")),
    }
