# planning_center_reports/drive_client.py
#
# All Google Drive interaction lives here: authenticating with the service
# account, finding/creating subfolders, and uploading (or replacing) PDF files.
#
# Authentication uses a credentials.json service-account key. The file must be
# present at the path resolved by _CREDS_PATH at runtime — it is never baked into
# the Docker image. Supply it via a mounted secret (Cloud Run) or a bind-mount
# (local Docker). The service account must have Editor access to the target Drive folder.
#
# On Cloud Run the key is mounted from Secret Manager at GOOGLE_APPLICATION_CREDENTIALS
# rather than /app/credentials.json — Cloud Run secret volumes replace the *entire*
# last directory in the mount path with the secret volume, which would hide main.py
# and planning_center_reports/ if mounted directly into /app. Mounting to a dedicated
# path (e.g. /secrets/credentials.json) avoids that collision.

import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Path to the service-account key file. GOOGLE_APPLICATION_CREDENTIALS overrides this
# (used on Cloud Run, where the secret is mounted outside /app). Otherwise falls back to
# the project root so it works for local (non-Docker) runs and the local bind-mount.
_CREDS_PATH = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "credentials.json",
    ),
)
_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


def get_drive_service():
    """Build and return an authenticated Google Drive API client.

    Uses the service account key at credentials.json. Raises FileNotFoundError
    if the key is missing from the expected location.
    """
    credentials = service_account.Credentials.from_service_account_file(
        _CREDS_PATH, scopes=_DRIVE_SCOPES
    )
    return build("drive", "v3", credentials=credentials)


def _escape(value: str) -> str:
    """Escape a value for use inside a single-quoted Drive query literal.

    Folder names come from PCO location names and reports.yaml, so they can
    legitimately contain quotes (e.g. '"B" Escuela Dominical').
    """
    return value.replace("\\", "\\\\").replace("'", "\\'")


def get_or_create_folder(service, parent_id: str, folder_name: str) -> str:
    """Return the Drive folder ID for `folder_name` under `parent_id`, creating
    it if it does not already exist."""
    query = (
        f"name='{_escape(folder_name)}' and "
        f"mimeType='application/vnd.google-apps.folder' and "
        f"'{parent_id}' in parents and trashed=false"
    )
    results = service.files().list(
        q=query, supportsAllDrives=True, includeItemsFromAllDrives=True
    ).execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    return service.files().create(
        body=metadata, fields="id", supportsAllDrives=True
    ).execute()["id"]


def upload_and_replace(service, folder_id: str, local_path: str, drive_name: str = None):
    """Upload `local_path` to Drive as `drive_name`, overwriting any existing file
    with the same name in `folder_id`.

    If `drive_name` is omitted the local filename is used.
    """
    drive_name = drive_name or os.path.basename(local_path)
    query      = f"name='{_escape(drive_name)}' and '{folder_id}' in parents and trashed=false"
    results    = service.files().list(
        q=query, supportsAllDrives=True, includeItemsFromAllDrives=True
    ).execute()
    files = results.get("files", [])
    media = MediaFileUpload(local_path, mimetype="application/pdf")
    if files:
        service.files().update(
            fileId=files[0]["id"], media_body=media, supportsAllDrives=True
        ).execute()
    else:
        service.files().create(
            body={"name": drive_name, "parents": [folder_id]},
            media_body=media,
            supportsAllDrives=True,
        ).execute()


def upload_if_changed(service, folder_id: str, local_path: str, drive_name: str,
                      fingerprint: str) -> bool:
    """Upload `local_path` as `drive_name` unless the copy already in `folder_id`
    carries the same `fingerprint` (stored in the file's appProperties).

    Returns True if a file was uploaded. Used for files that rarely change, such
    as Instrucciones.pdf, so a weekly run doesn't rewrite dozens of identical copies.
    """
    query   = f"name='{_escape(drive_name)}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(
        q=query, fields="files(id, appProperties)",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    files = results.get("files", [])
    if files and (files[0].get("appProperties") or {}).get("fingerprint") == fingerprint:
        return False

    media = MediaFileUpload(local_path, mimetype="application/pdf")
    props = {"appProperties": {"fingerprint": fingerprint}}
    if files:
        service.files().update(
            fileId=files[0]["id"], body=props, media_body=media, supportsAllDrives=True
        ).execute()
    else:
        service.files().create(
            body={"name": drive_name, "parents": [folder_id], **props},
            media_body=media,
            supportsAllDrives=True,
        ).execute()
    return True
