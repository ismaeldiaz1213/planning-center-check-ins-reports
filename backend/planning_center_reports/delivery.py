# planning_center_reports/delivery.py
#
# Where finished PDFs go. The run pipeline only knows the Delivery interface:
#
#   delivery.deliver(path, folders, filename, fingerprint=None)
#
# `folders` is the nested folder path under the church's destination (for
# example ["Voluntarios", "Rutas"]). With a `fingerprint`, a destination that
# can remember it skips the upload when the same content is already there.
#
#   LocalDelivery                 copy into a directory (dry runs, tests)
#   DriveServiceAccountDelivery   IBL's original setup: a service-account key
#                                 with access to a folder shared with it
#   DriveOAuthDelivery            the platform: the church's own Google account,
#                                 limited to files this app created (drive.file)
#   FanOutDelivery                several of the above at once

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Sequence
from typing import Protocol

from planning_center_reports.drive_client import (
    get_drive_service,
    get_oauth_drive_service,
    get_or_create_folder,
    upload_and_replace,
    upload_if_changed,
)


class Delivery(Protocol):
    def deliver(self, path: str, folders: Sequence[str], filename: str,
                fingerprint: str | None = None) -> None: ...


def slug(name: str) -> str:
    """Filesystem-safe form of a location or folder name."""
    return name.replace("/", "-").replace(" ", "_").replace('"', "")


class LocalDelivery:
    """Copy each file under `output_dir`, mirroring the folder nesting."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    def deliver(self, path, folders, filename, fingerprint=None) -> None:
        dest_dir = os.path.join(self.output_dir, *[slug(f) for f in folders])
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, filename)
        shutil.copy(path, dest)
        print(f"  [dry-run] Saved → {dest}", flush=True)


class _DriveDelivery:
    """Upload into nested folders under one Drive parent folder."""

    def __init__(self, parent_folder_id: str, connect: Callable[[], object]):
        if not parent_folder_id:
            raise ValueError("a Drive parent folder id is required")
        self.parent_folder_id = parent_folder_id
        self._connect = connect
        self._service = None

    @property
    def service(self):
        if self._service is None:
            print("\nConnecting to Google Drive...", flush=True)
            self._service = self._connect()
        return self._service

    def deliver(self, path, folders, filename, fingerprint=None) -> None:
        folder_id = self.parent_folder_id
        for name in folders:
            folder_id = get_or_create_folder(self.service, folder_id, name)
        if fingerprint:
            if upload_if_changed(self.service, folder_id, path, filename, fingerprint):
                print(f"  ✓ Uploaded {filename}", flush=True)
        else:
            upload_and_replace(self.service, folder_id, path, filename)
            print(f"  ✓ Uploaded {filename}", flush=True)


class DriveServiceAccountDelivery(_DriveDelivery):
    """Legacy: a service-account key file (credentials.json, full Drive scope)."""

    def __init__(self, parent_folder_id: str, credentials_path: str):
        super().__init__(parent_folder_id, lambda: get_drive_service(credentials_path))


class DriveOAuthDelivery(_DriveDelivery):
    """Platform: the church's Google connection, with the drive.file scope.

    drive.file only shows this app the files and folders it created itself, so
    the parent folder must be one the app made (or one the user picked for it).
    `credentials` is a google.oauth2.credentials.Credentials for that church.
    """

    def __init__(self, parent_folder_id: str, credentials):
        super().__init__(parent_folder_id, lambda: get_oauth_drive_service(credentials))


class FanOutDelivery:
    """Send every file to several destinations."""

    def __init__(self, deliveries: Sequence[Delivery]):
        self.deliveries = tuple(deliveries)

    def deliver(self, path, folders, filename, fingerprint=None) -> None:
        for delivery in self.deliveries:
            delivery.deliver(path, folders, filename, fingerprint)
