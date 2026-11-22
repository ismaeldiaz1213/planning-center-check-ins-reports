# advanced_reports/core/firestore_store.py
#
# The production document store: the same five methods as MemoryStore and
# FileStore (core/store.py), backed by Google Cloud Firestore (plan §3.6).
#
# Each document is kept as one JSON string in a field named "json". Firestore's
# native types would make some of our documents unstorable (it rejects arrays of
# arrays and integers past 64 bits) and would quietly turn others into different
# types on the way back (tuples, large floats). Our store only gets, sets, lists
# and deletes whole documents, so nothing is lost by not querying fields.
#
# Only TenantRepo may use a store (plan §3.7 rule 2).

from __future__ import annotations

import json

from google.api_core import exceptions
from google.cloud import firestore

from advanced_reports.core.store import check_path

_FIELD = "json"


def _encode(data: dict) -> dict:
    return {_FIELD: json.dumps(data, ensure_ascii=False, separators=(",", ":"))}


def _decode(snapshot) -> dict | None:
    if not snapshot.exists:
        return None
    return json.loads((snapshot.to_dict() or {}).get(_FIELD) or "{}")


class FirestoreStore:
    """Documents under an optional `prefix` document path, e.g. "ci-tests/abc123"
    (tests use one so they never touch real data)."""

    def __init__(self, project: str, database: str = "(default)", prefix: str = "", client=None):
        self.client = client or firestore.Client(project=project, database=database)
        self.prefix = prefix.strip("/")
        if self.prefix:
            check_path(self.prefix)  # a document path, so prefix + document path stays even

    def _path(self, path: str) -> str:
        check_path(path)
        return f"{self.prefix}/{path}" if self.prefix else path

    def get(self, path):
        return _decode(self.client.document(self._path(path)).get())

    def set(self, path, data):
        self.client.document(self._path(path)).set(_encode(data))

    def create(self, path, data):
        try:
            self.client.document(self._path(path)).create(_encode(data))
            return True
        except exceptions.AlreadyExists:
            return False

    def list(self, collection):
        full = f"{self.prefix}/{collection}" if self.prefix else collection
        out = [(f"{collection}/{snap.id}", _decode(snap)) for snap in self.client.collection(full).stream()]
        return sorted(out, key=lambda pair: pair[0])

    def delete_tree(self, path):
        ref = self.client.document(self._path(path))
        self.client.recursive_delete(ref)  # every subcollection, at any depth
        ref.delete()
