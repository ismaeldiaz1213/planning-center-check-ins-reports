# advanced_reports/core/store.py
#
# A small document store: JSON documents addressed by a slash-separated path
# ("churches/123/runs/abc"), the same shape as Firestore (plan §3.6).
#
#   MemoryStore   tests
#   FileStore     one JSON file per document under a folder: local development
#                 and the local demo. The web process and the runner process
#                 share it through the filesystem.
#
#   FirestoreStore  production (core/firestore_store.py)
#
# create() writes a document only if it does not exist yet, atomically. It is
# what makes "one run at a time" hold when two requests race (TenantRepo.start_run).
#
# Only TenantRepo may use a store (plan §3.7 rule 2).

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Protocol

_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def check_path(path: str) -> list[str]:
    parts = path.split("/")
    if len(parts) % 2 or not all(_SEGMENT.match(p) and ".." not in p for p in parts):
        raise ValueError(f"not a document path: {path!r}")
    return parts


class Store(Protocol):
    def get(self, path: str) -> dict | None: ...
    def set(self, path: str, data: dict) -> None: ...
    def create(self, path: str, data: dict) -> bool: ...
    def list(self, collection: str) -> list[tuple[str, dict]]: ...
    def delete_tree(self, path: str) -> None: ...


class MemoryStore:
    def __init__(self):
        self.docs: dict[str, dict] = {}

    def get(self, path):
        check_path(path)
        return copy.deepcopy(self.docs.get(path))

    def set(self, path, data):
        check_path(path)
        self.docs[path] = json.loads(json.dumps(data))

    def create(self, path, data):
        check_path(path)
        if path in self.docs:
            return False
        self.set(path, data)
        return True

    def list(self, collection):
        depth = collection.count("/") + 2
        return sorted((p, copy.deepcopy(d)) for p, d in self.docs.items()
                      if p.startswith(collection + "/") and p.count("/") + 1 == depth)

    def delete_tree(self, path):
        check_path(path)
        for p in [p for p in self.docs if p == path or p.startswith(path + "/")]:
            del self.docs[p]


class FileStore:
    """`root/<collection>/<id>.json`, with subcollections in `root/<collection>/<id>/`."""

    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _file(self, path: str) -> Path:
        return self.root.joinpath(*check_path(path)).with_suffix(".json")

    def get(self, path):
        try:
            return json.loads(self._file(path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def set(self, path, data):
        target = self._file(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Write then rename, so a reader in another process never sees half a file.
        fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(tmp, target)

    def create(self, path, data):
        target = self._file(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        try:
            os.link(tmp, target)  # fails if the target exists, atomically
            return True
        except FileExistsError:
            return False
        finally:
            os.unlink(tmp)

    def list(self, collection):
        folder = self.root.joinpath(*collection.split("/"))
        if not folder.is_dir():
            return []
        out = []
        for f in sorted(folder.glob("*.json")):
            try:
                out.append((f"{collection}/{f.stem}", json.loads(f.read_text(encoding="utf-8"))))
            except FileNotFoundError:
                continue
        return out

    def delete_tree(self, path):
        self._file(path).unlink(missing_ok=True)
        shutil.rmtree(self.root.joinpath(*check_path(path)), ignore_errors=True)


def open_store(settings) -> Store:
    """The store the settings ask for: Firestore when a project is set, else files."""
    if settings.firestore_project:
        from advanced_reports.core.firestore_store import FirestoreStore  # needs google-cloud-firestore
        return FirestoreStore(settings.firestore_project, settings.firestore_database)
    return FileStore(settings.store_dir)
