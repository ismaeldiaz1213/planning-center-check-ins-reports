# advanced_reports/core/blobs.py
#
# Where files live: a run's PDFs and a church's logo. Keys are slash-separated
# paths that always start with churches/{org_id}/ (TenantRepo builds them).
#
#   LocalBlobs  a folder on disk: tests, local development, the local demo
#   GcsBlobs    a Cloud Storage bucket: production. The web service and the
#               runner are separate containers there, so they share files
#               through the bucket instead of a disk.
#
# Blob stores keep bytes as given. TenantRepo encrypts with the church's data key
# before putting and decrypts after getting, so the bucket only ever holds
# ciphertext. Decision D2 (launch guide): only the latest run's PDFs are kept.
#
# Only TenantRepo may use a blob store (plan §3.7 rule 2).

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Protocol

# Any name a class or file can have (accents included), but never a separator,
# a control character, "..", or a leading dot.
_PART = re.compile(r"^[^/\\\x00-\x1f.][^/\\\x00-\x1f]{0,199}$")


def check_key(key: str) -> list[str]:
    parts = key.split("/")
    if not parts or not all(_PART.match(p) and ".." not in p for p in parts):
        raise ValueError(f"not a file key: {key!r}")
    return parts


class BlobStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes | None: ...
    def exists(self, key: str) -> bool: ...
    def delete_prefix(self, prefix: str) -> None: ...


class LocalBlobs:
    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)

    def _file(self, key: str) -> Path:
        return self.root.joinpath(*check_key(key))

    def put(self, key, data):
        target = self._file(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, target)

    def get(self, key):
        try:
            return self._file(key).read_bytes()
        except (FileNotFoundError, IsADirectoryError):
            return None

    def exists(self, key):
        return self._file(key).is_file()

    def delete_prefix(self, prefix):
        target = self._file(prefix.rstrip("/"))
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)


class GcsBlobs:
    """Objects in one bucket, under an optional `prefix` (tests use a throwaway one)."""

    def __init__(self, bucket: str, prefix: str = "", client=None):
        from google.cloud import storage  # needs google-cloud-storage
        self.client = client or storage.Client()
        self.bucket = self.client.bucket(bucket)
        self.prefix = prefix.strip("/")
        if self.prefix:
            check_key(self.prefix)

    def _name(self, key: str) -> str:
        check_key(key)
        return f"{self.prefix}/{key}" if self.prefix else key

    def put(self, key, data):
        self.bucket.blob(self._name(key)).upload_from_string(data, content_type="application/octet-stream")

    def get(self, key):
        from google.api_core import exceptions
        try:
            return self.bucket.blob(self._name(key)).download_as_bytes()
        except exceptions.NotFound:
            return None

    def exists(self, key):
        return self.bucket.blob(self._name(key)).exists()

    def delete_prefix(self, prefix):
        name = self._name(prefix.rstrip("/"))
        blobs = list(self.client.list_blobs(self.bucket, prefix=name + "/"))
        exact = self.bucket.blob(name)
        if exact.exists():
            blobs.append(exact)
        for blob in blobs:
            blob.delete()


def open_blobs(settings) -> BlobStore:
    """Cloud Storage when a bucket is set, else the local files folder."""
    if settings.bucket:
        return GcsBlobs(settings.bucket)
    return LocalBlobs(settings.files_dir)
