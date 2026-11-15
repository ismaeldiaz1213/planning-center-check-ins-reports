# advanced_reports/core/session.py
#
# Signed session cookies. The cookie carries who is signed in and for which
# church; the church id is ONLY ever read from here (plan §3.7 rule 1). The
# value is signed with HMAC-SHA256 and expires; it is not encrypted, so it must
# never contain a secret.

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

COOKIE = "ar_session"
MAX_AGE = 12 * 3600


def _sign(secret: str, body: bytes) -> str:
    return base64.urlsafe_b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def issue(secret: str, *, org_id: str, person_id: str, name: str, now: float | None = None) -> str:
    payload = {"org": org_id, "person": person_id, "name": name,
               "exp": int((now or time.time()) + MAX_AGE)}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
    return f"{body.decode()}.{_sign(secret, body)}"


def read(secret: str, cookie: str | None, now: float | None = None) -> dict | None:
    """The session inside a cookie, or None if it is missing, forged or expired."""
    if not cookie or cookie.count(".") != 1:
        return None
    body, signature = cookie.split(".")
    if not hmac.compare_digest(signature, _sign(secret, body.encode())):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(body.encode()))
    except ValueError:
        return None
    if not isinstance(payload, dict) or payload.get("exp", 0) < (now or time.time()):
        return None
    if not payload.get("org") or not payload.get("person"):
        return None
    return payload
