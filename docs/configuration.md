# Configuration Reference

All runtime configuration is done through environment variables. Copy `.env.example` to `.env`
and fill in the values before running anything.

---

## Required variables

| Variable | Description |
|----------|-------------|
| `PCO_APP_ID` | Planning Center Personal Access Token — Application ID |
| `PCO_SECRET` | Planning Center Personal Access Token — Secret |
| `GOOGLE_DRIVE_PARENT_FOLDER_ID` | ID of the Google Drive folder where rosters are uploaded |

### Getting PCO credentials

1. Go to **https://api.planningcenteronline.com/oauth/applications**
2. Click **New Personal Access Token**
3. Enable the **Check-Ins** and **People** scopes
4. Copy **Application ID** → `PCO_APP_ID` and **Secret** → `PCO_SECRET`

Test that they work:
```bash
curl -u YOUR_APP_ID:YOUR_SECRET \
  https://api.planningcenteronline.com/check-ins/v2/events
```

### Getting the Drive folder ID

The folder ID is the last segment of the URL when you open the folder in Google Drive:
```
https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUv
                                       ^^^^^^^^^^^^^^^^^^^^^^^^
                                       this is the folder ID
```

The service account (see below) must have **Editor** access to this folder.

---

## Google credentials

### Service account (`credentials.json`)

The roster job uses a Google Cloud service account to upload files to Drive.

1. Go to **Cloud Console → IAM & Admin → Service Accounts → Create Service Account**
2. Give it a name (e.g. `ministry-roster-account`)
3. Click the account → **Keys** tab → **Add Key → JSON**
4. Download the key, rename it to `credentials.json`, place it in the project root

Share the Drive roster folder with the service account email (shown in Cloud Console):
- Right-click folder → **Share** → paste the service account email → set to **Editor**

```
GOOGLE_APPLICATION_CREDENTIALS=./credentials.json
```

### Web UI OAuth (`GOOGLE_CLIENT_ID`)

Only needed if you run the web UI (`api.py`). If this variable is not set, the API
runs without authentication (any request is accepted — local development only).

1. Go to **Cloud Console → APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
2. Application type: **Web application**
3. Add your Cloud Run URL to **Authorized JavaScript Origins**
4. Copy the **Client ID** → `GOOGLE_CLIENT_ID`

---

## Optional variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOWED_GOOGLE_DOMAINS` | *(empty — any Google account)* | Comma-separated list of Google Workspace domains allowed to log in (e.g. `mychurch.org,mychurch.com`). Leave blank to allow any authenticated Google account. |
| `RUTAS_SUBTITLE` | `Ministerio de Autobuses` | Subtitle shown in bus roster headers |
| `CHURCH_VERSE_TEXT` | `"Id por todo el mundo y predicad el evangelio a toda criatura"` | Verse text shown in PDF footers |
| `CHURCH_VERSE_REF` | `Marcos 16:15 — RV1960` | Verse reference shown in PDF footers |

### Examples

**Restrict login to your church's Google Workspace domain:**
```
ALLOWED_GOOGLE_DOMAINS=mychurch.org
```

**Multiple domains:**
```
ALLOWED_GOOGLE_DOMAINS=mychurch.org,mychurch.com
```

**Allow any Google account (useful for churches without Google Workspace):**
```
ALLOWED_GOOGLE_DOMAINS=
```

**Custom verse:**
```
CHURCH_VERSE_TEXT="For God so loved the world..."
CHURCH_VERSE_REF=John 3:16 — NIV
```

---

## Google Cloud deployment variables

Only needed if deploying to Google Cloud Run via `manage.sh` or `setup_gcloud.sh`.

| Variable | Description |
|----------|-------------|
| `GCP_PROJECT_ID` | Your GCP project ID (visible in Cloud Console header) |
| `GCP_SA_EMAIL` | Service account email (e.g. `name@project.iam.gserviceaccount.com`) |

`manage.sh` reads these from `.env` automatically. If not set, the script will prompt you.

---

## Logo replacement

The church logo appears in PDF headers and the web UI footer.

1. Prepare your logo as a PNG file (~300 × 80 px recommended)
2. Replace `backend/logo.png` with your file (keep the filename `logo.png`)
3. Rebuild the Docker image if deployed: `./manage.sh → option 6`

---

## Planning Center permissions

The Personal Access Token needs these two scopes:

| Scope | What it's used for |
|-------|--------------------|
| **Check-Ins** | Fetch attendance records and event check-ins |
| **People** | Fetch member profiles (name, birthday, address, grade, phone) |

No write access to Planning Center is required — the token is read-only.
