# tests/test_drive_client.py
#
# drive_client.py against an in-memory stand-in for the Drive API client. This
# checks which Drive calls we make (find, create, replace, skip when unchanged),
# not that Google accepts them: nothing here talks to Google.

import re

import pytest

from planning_center_reports import delivery, drive_client
from planning_center_reports.drive_client import (
    get_or_create_folder,
    upload_and_replace,
    upload_if_changed,
)


class _Call:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class FakeDrive:
    """Just enough of googleapiclient's `service.files()` for drive_client."""

    def __init__(self):
        self.items: dict[str, dict] = {}     # id → {name, parents, appProperties, uploads}
        self.log: list[str] = []

    def files(self):
        return self

    def list(self, q, **_kw):
        name, folder, parent = re.fullmatch(
            r"name='(.*?)'( and mimeType='application/vnd\.google-apps\.folder')?"
            r" and '([^']*)' in parents and trashed=false", q).groups()
        name = name.replace("\\'", "'").replace("\\\\", "\\")
        found = [{"id": i, "appProperties": f.get("appProperties")}
                 for i, f in self.items.items()
                 if f["name"] == name and parent in f["parents"] and bool(folder) == ("mimeType" in f)]
        return _Call({"files": found})

    def create(self, body, media_body=None, **_kw):
        new_id = f"id{len(self.items) + 1}"
        self.items[new_id] = {**body, "uploads": 1 if media_body else 0}
        self.log.append(f"create {body['name']}")
        return _Call({"id": new_id})

    def update(self, fileId, media_body=None, body=None, **_kw):  # noqa: N803 — Drive's name
        self.items[fileId].update(body or {})
        self.items[fileId]["uploads"] += 1
        self.log.append(f"update {self.items[fileId]['name']}")
        return _Call({"id": fileId})


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "local-name.pdf"
    path.write_bytes(b"%PDF-1.4\n")
    return str(path)


class TestFolders:
    def test_created_once_then_reused(self):
        drive = FakeDrive()
        first = get_or_create_folder(drive, "root", "Ruta 1")
        assert get_or_create_folder(drive, "root", "Ruta 1") == first
        assert drive.log == ["create Ruta 1"]

    def test_same_name_under_another_parent_is_a_different_folder(self):
        drive = FakeDrive()
        assert get_or_create_folder(drive, "a", "Clase") != get_or_create_folder(drive, "b", "Clase")

    def test_names_with_quotes_are_found_again(self):
        drive = FakeDrive()
        first = get_or_create_folder(drive, "root", '"B" Escuela d\'Oro')
        assert get_or_create_folder(drive, "root", '"B" Escuela d\'Oro') == first


class TestUploadAndReplace:
    def test_second_upload_replaces_the_first(self, pdf):
        drive = FakeDrive()
        upload_and_replace(drive, "folder", pdf, "Roster.pdf")
        upload_and_replace(drive, "folder", pdf, "Roster.pdf")
        assert drive.log == ["create Roster.pdf", "update Roster.pdf"]
        assert len(drive.items) == 1

    def test_defaults_to_the_local_file_name(self, pdf):
        drive = FakeDrive()
        upload_and_replace(drive, "folder", pdf)
        assert drive.log == ["create local-name.pdf"]


class TestUploadIfChanged:
    def test_skips_when_the_fingerprint_matches(self, pdf):
        drive = FakeDrive()
        assert upload_if_changed(drive, "folder", pdf, "Instrucciones.pdf", "v1") is True
        assert upload_if_changed(drive, "folder", pdf, "Instrucciones.pdf", "v1") is False
        assert drive.log == ["create Instrucciones.pdf"]

    def test_replaces_when_the_fingerprint_changes(self, pdf):
        drive = FakeDrive()
        upload_if_changed(drive, "folder", pdf, "Instrucciones.pdf", "v1")
        assert upload_if_changed(drive, "folder", pdf, "Instrucciones.pdf", "v2") is True
        assert drive.log == ["create Instrucciones.pdf", "update Instrucciones.pdf"]
        (item,) = drive.items.values()
        assert item["appProperties"] == {"fingerprint": "v2"}

    def test_replaces_a_file_that_has_no_fingerprint(self, pdf):
        """A file uploaded before fingerprints existed is replaced, not duplicated."""
        drive = FakeDrive()
        upload_and_replace(drive, "folder", pdf, "Instrucciones.pdf")
        assert upload_if_changed(drive, "folder", pdf, "Instrucciones.pdf", "v1") is True
        assert len(drive.items) == 1


class TestDeliveries:
    """Both Drive deliveries end in the same calls; only the sign-in differs."""

    def test_service_account_delivery_uses_the_given_key_file(self, pdf, monkeypatch):
        drive, asked = FakeDrive(), []
        monkeypatch.setattr(delivery, "get_drive_service", lambda path: asked.append(path) or drive)
        d = delivery.DriveServiceAccountDelivery("root", "/secrets/key.json")
        d.deliver(pdf, ["Voluntarios", "Rutas"], "Voluntarios.pdf")
        d.deliver(pdf, ["Voluntarios", "Rutas"], "Voluntarios.pdf")
        assert asked == ["/secrets/key.json"]          # connected once
        assert drive.log == ["create Voluntarios", "create Rutas",
                             "create Voluntarios.pdf", "update Voluntarios.pdf"]

    def test_oauth_delivery_uses_the_churchs_credentials(self, pdf, monkeypatch):
        drive, asked = FakeDrive(), []
        monkeypatch.setattr(delivery, "get_oauth_drive_service", lambda creds: asked.append(creds) or drive)
        creds = object()
        d = delivery.DriveOAuthDelivery("root", creds)
        d.deliver(pdf, ["Clase"], "Instrucciones.pdf", fingerprint="v1")
        d.deliver(pdf, ["Clase"], "Instrucciones.pdf", fingerprint="v1")
        assert asked == [creds]
        assert drive.log == ["create Clase", "create Instrucciones.pdf"]

    def test_fan_out_sends_to_every_destination(self, pdf, tmp_path):
        a, b = delivery.LocalDelivery(str(tmp_path / "a")), delivery.LocalDelivery(str(tmp_path / "b"))
        delivery.FanOutDelivery([a, b]).deliver(pdf, ['"B" Clase', "Ruta 1/2"], "Roster.pdf")
        for name in ("a", "b"):
            assert (tmp_path / name / "B_Clase" / "Ruta_1-2" / "Roster.pdf").exists()

    def test_key_file_is_read_only_when_connecting(self, monkeypatch):
        """No module-level key path any more: two churches could use two keys."""
        assert not hasattr(drive_client, "_CREDS_PATH")
