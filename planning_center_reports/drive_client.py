# planning_center_reports/drive_client.py
#
# All Google Drive interaction lives here: authenticating with the service
# account, finding/creating subfolders, and uploading (or replacing) PDF files.
#
# Authentication uses a credentials.json service-account key that is baked into
# the Docker image at build time. The service account must have Editor access to
# the target Drive folder.

import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Path to the service-account key file. Resolved relative to the project root
# so it works both locally and inside the Docker container (/app/credentials.json).
_CREDS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "credentials.json",
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


def get_or_create_folder(service, parent_id: str, folder_name: str) -> str:
    """Return the Drive folder ID for `folder_name` under `parent_id`, creating
    it if it does not already exist."""
    query = (
        f"name='{folder_name}' and "
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
    query      = f"name='{drive_name}' and '{folder_id}' in parents and trashed=false"
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
