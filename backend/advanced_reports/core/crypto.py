# advanced_reports/core/crypto.py
#
# Envelope encryption (plan §3.5). Each church gets its own random 256-bit data
# key. Secrets and stored data are encrypted with AES-GCM under that key; the
# data key itself is stored encrypted ("wrapped") under one master key, which
# lives outside the database (Secret Manager in production).
#
# Every ciphertext is bound to where it belongs (the church id and the document
# name) through AES-GCM's associated data, so a blob copied from one church's
# record into another's fails to decrypt instead of being read.

from __future__ import annotations

import base64
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE = 12


class DecryptError(Exception):
    """The ciphertext was damaged, moved, or encrypted under another key."""


def _encrypt(key: bytes, plaintext: bytes, bound_to: str) -> str:
    nonce = os.urandom(_NONCE)
    sealed = AESGCM(key).encrypt(nonce, plaintext, bound_to.encode())
    return base64.urlsafe_b64encode(nonce + sealed).decode()


def _decrypt(key: bytes, token: str, bound_to: str) -> bytes:
    try:
        raw = base64.urlsafe_b64decode(token.encode())
        return AESGCM(key).decrypt(raw[:_NONCE], raw[_NONCE:], bound_to.encode())
    except (InvalidTag, ValueError, TypeError) as exc:
        raise DecryptError(f"could not decrypt data bound to {bound_to!r}") from exc


def seal(key: bytes, value: dict, bound_to: str) -> str:
    """Encrypt a JSON-serialisable dict under a church's data key."""
    return _encrypt(key, json.dumps(value, separators=(",", ":")).encode(), bound_to)


def unseal(key: bytes, token: str, bound_to: str) -> dict:
    return json.loads(_decrypt(key, token, bound_to))


class Vault:
    """Holds the master key; makes and unwraps per-church data keys."""

    def __init__(self, master_key: bytes):
        if len(master_key) != 32:
            raise ValueError("the master key must be 32 bytes")
        self._master = master_key

    @classmethod
    def from_b64(cls, text: str) -> Vault:
        return cls(base64.urlsafe_b64decode(text.strip().encode()))

    @staticmethod
    def generate_b64() -> str:
        return base64.urlsafe_b64encode(os.urandom(32)).decode()

    def new_wrapped_key(self, org_id: str) -> str:
        return _encrypt(self._master, os.urandom(32), f"data-key:{org_id}")

    def unwrap(self, wrapped: str, org_id: str) -> bytes:
        return _decrypt(self._master, wrapped, f"data-key:{org_id}")
