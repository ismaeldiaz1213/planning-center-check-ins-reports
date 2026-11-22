# advanced_reports/core/google_oauth.py
#
# "Connect Google Drive": the church admin signs in with Google and lets the app
# save rosters into their Drive. The only Drive permission asked for is
# drive.file, which lets the app see only files and folders it created itself
# (Google treats it as non-sensitive, so no security review). "openid email"
# lets the dashboard show which Google account is connected.
#
# On connect, the app creates (or finds again) one folder, "Advanced Reports",
# in that account's Drive. Every run's PDFs go there, mirroring the class
# folders, and replace last week's files in place.

from __future__ import annotations

import time
from urllib.parse import urlencode

import requests

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
SCOPES = f"openid email {DRIVE_SCOPE}"
FOLDER_NAME = "Advanced Reports"
FOLDER_MIME = "application/vnd.google-apps.folder"


class GoogleError(Exception):
    pass


def redirect_uri(base_url: str) -> str:
    return f"{base_url}/auth/google/callback"


def authorize_url(client_id: str, base_url: str, state: str) -> str:
    return AUTHORIZE_URL + "?" + urlencode({
        "client_id": client_id, "redirect_uri": redirect_uri(base_url), "response_type": "code",
        "scope": SCOPES, "state": state,
        # A refresh token, every time (Google only sends one with prompt=consent).
        "access_type": "offline", "prompt": "consent", "include_granted_scopes": "false",
    })


def exchange_code(client_id: str, client_secret: str, base_url: str, code: str, http=requests) -> dict:
    response = http.post(TOKEN_URL, data={
        "grant_type": "authorization_code", "code": code, "client_id": client_id,
        "client_secret": client_secret, "redirect_uri": redirect_uri(base_url),
    }, timeout=30)
    if response.status_code != 200:
        raise GoogleError(f"Google refused the sign-in ({response.status_code})")
    body = response.json()
    if DRIVE_SCOPE not in (body.get("scope") or "").split():
        raise GoogleError("Google Drive access was not granted. Please tick the Drive box and try again.")
    if not body.get("refresh_token"):
        raise GoogleError("Google returned no refresh token")
    return {"kind": "oauth", "access_token": body["access_token"], "refresh_token": body["refresh_token"],
            "expires_at": int(time.time()) + int(body.get("expires_in") or 3600)}


def email(access_token: str, http=requests) -> str:
    response = http.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
    if response.status_code != 200:
        raise GoogleError(f"Google refused the account lookup ({response.status_code})")
    return response.json().get("email") or ""


def credentials(token: dict, client_id: str, client_secret: str):
    """google.oauth2 Credentials that refresh themselves, for the Drive client."""
    from google.oauth2.credentials import Credentials
    return Credentials(token=None, refresh_token=token["refresh_token"], token_uri=TOKEN_URL,
                       client_id=client_id, client_secret=client_secret, scopes=[DRIVE_SCOPE])


def ensure_folder(service, folder_id: str = "") -> str:
    """The id of the app's "Advanced Reports" folder: the stored one if it still
    exists and isn't in the trash, else a new one at the top of My Drive."""
    if folder_id:
        try:
            found = service.files().get(fileId=folder_id, fields="id, trashed").execute()
            if not found.get("trashed"):
                return found["id"]
        except Exception:  # deleted, or access removed: make a new one
            pass
    created = service.files().create(body={"name": FOLDER_NAME, "mimeType": FOLDER_MIME},
                                     fields="id").execute()
    return created["id"]
