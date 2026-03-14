# IBL Planning Center — Automated Roster & Check-In System

This project does two things automatically:

1. **Generates PDF rosters** from Planning Center check-ins and uploads them to Google Drive every Monday at 2 AM
2. **Bulk checks in entire groups** to an event (optional, run manually)

---

## Project Structure

```
planning-center-check-ins-reports/
├── main.py               # Roster generator (Rutas + Escuela Dominical)
├── groups_to_check_ins.py # Optional: bulk check-in a group to an event
├── ibl_logo.png          # Church logo used in PDFs
├── credentials.json      # Google service account key (never commit this)
├── .env                  # Local credentials (never commit this)
├── .gitignore            # Excludes .env and credentials.json
├── requirements.txt      # Python dependencies
├── Dockerfile            # Container definition for Cloud Run
├── entrypoint.sh         # Writes credentials at runtime, then runs main.py
├── setup_gcloud.sh       # Run ONCE to deploy everything to Google Cloud
└── manage.sh             # Day-to-day management (update keys, test, logs)
```

---

## How It Works

### Roster Generator (`main.py`)

Run with either of two event names as an argument:

```bash
python main.py "Rutas"
python main.py "Escuela Dominical"
```

**`Rutas`** — generates one PDF per bus route. People are grouped by apartment complex, sorted by unit number within each group. Empty rows are included for walk-ins. Highlights missing birthdays, phones, and bad addresses in yellow.

**`Escuela Dominical`** — generates one simple alphabetical roster per Sunday school class location. Same yellow highlighting for missing data.

Both PDFs include:
- IBL Libertad logo
- Route/class name as the title
- Generated date and time (in Spanish)
- Grade column (auto-filled from PCO; age-based for children under 5)
- Marcos 16:15 verse in the footer
- Page numbers

### Auto Check-In (`auto_checkin.py`)

Looks up all members of a PCO Group and bulk checks them into the most recent event period. Uses your browser session cookie to call the same internal endpoint the PCO web UI uses.

---

## First-Time Setup

### Prerequisites

| Tool | Install |
|------|---------|
| Python 3.10+ | Already on most systems; check with `python3 --version` |
| Google Cloud CLI | See below |
| Docker | `sudo dnf install docker` (Fedora) |

#### Install Google Cloud CLI on Fedora

```bash
sudo tee -a /etc/yum.repos.d/google-cloud-sdk.repo << EOM
[google-cloud-cli]
name=Google Cloud CLI
baseurl=https://packages.cloud.google.com/yum/repos/cloud-sdk-el9-x86_64
enabled=1
gpgcheck=1
repo_gpgcheck=0
gpgkey=https://packages.cloud.google.com/yum/doc/rpm-package-key.gpg
EOM

sudo dnf install google-cloud-cli
```
I recognize most people do not use a Linux computer. Google has documentation for people though! Please see this link for specific instructions for your device: 

#### Install and start Docker

```bash
sudo dnf install docker
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker
```

---

### Step 1 — Planning Center API Credentials

1. Log into Planning Center
2. Go to **https://api.planningcenteronline.com/oauth/applications**
3. Click **New Personal Access Token**
4. Enable **Check-Ins** and **People**
5. Copy the **Application ID** and **Secret**

Test that they work:
```bash
curl -u YOUR_APP_ID:YOUR_SECRET \
  https://api.planningcenteronline.com/check-ins/v2/events
```
You should get JSON back with your events listed.

---

### Step 2 — Google Service Account

The project already has a service account set up:
`ministry-account-pc@ibl-planning-center-check-ins.iam.gserviceaccount.com`

If you need to regenerate the key:
1. Go to **https://console.cloud.google.com/iam-admin/serviceaccounts?project=ibl-planning-center-check-ins**
2. Click the service account → **Keys** tab
3. **Add Key → Create New Key → JSON**
4. Download and rename it to `credentials.json`
5. Place it in the project root folder

The service account must have **Editor** access to your Google Drive roster folder. Right-click the folder in Drive → **Share** → paste the service account email → set to **Editor**.

---

### Step 3 — Google Drive Folder ID

1. Open your Google Drive roster folder in a browser
2. The URL looks like: `https://drive.google.com/drive/folders/XXXXXXXXXXXXXXXX`
3. Copy the `XXXXXXXXXXXXXXXX` part — that is your folder ID

---

### Step 4 — Local `.env` File (for running locally)

Copy the example:
```bash
cp .env.example .env
```

Fill in your values:
```
PCO_APP_ID=your_app_id_here
PCO_SECRET=your_secret_here
GOOGLE_DRIVE_PARENT_FOLDER_ID=your_folder_id_here
```

---

### Step 5 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

### Step 6 — Test Locally

```bash
python main.py "Rutas"
```

You should see output like:
```
Finding event 'Rutas'...
Event ID: 754993
Finding recent event periods (last 5 weeks)...
  Using 5 event period(s):
    - 44164721 (2026-03-15T14:00:00Z)
    ...
Fetching check-ins...
  [1] Fetching Isaac Ramirez (id: 149426747)...
  [2] Cached: Regina Cruz
  ...
Generating PDF for Ruta 1 - Bus (42 attendees)...
  ✓ Uploaded roster for Ruta 1 - Bus
Done.
```

---

### Step 7 — Deploy to Google Cloud (Automated Monday Runs)

Run the setup script **once**:

```bash
chmod +x setup_gcloud.sh
./setup_gcloud.sh
```

This will walk you through:
- Logging into Google Cloud
- Creating/selecting a project
- Enabling required APIs
- Storing all secrets securely in Secret Manager
- Building and pushing the Docker image
- Creating Cloud Run Jobs for Rutas and Escuela Dominical
- Scheduling both to run every Monday at 2 AM US Central

> ⚠️ `credentials.json` is **never** uploaded to the cloud. It is stored as a Secret Manager secret and written to disk only at container runtime.

---

## Day-to-Day Management

Use the management menu for everything after initial setup:

```bash
chmod +x manage.sh
./manage.sh
```

```
╔══════════════════════════════════════════════════════════╗
║        Church Roster — Cloud Management Menu             ║
╚══════════════════════════════════════════════════════════╝

  SECRETS & CREDENTIALS
  1) Update PCO App ID
  2) Update PCO Secret
  3) Update Google Drive Folder ID
  4) Update credentials.json (service account key)
  5) View current secret values

  DEPLOYMENT
  6) Deploy updated main.py to Cloud

  TESTING & LOGS
  7) Run Rutas job now (test)
  8) Run Escuela Dominical job now (test)
  9) View logs — Rutas
  10) View logs — Escuela Dominical
  11) View job status (last run results)

  SCHEDULER
  12) View scheduled jobs
  13) Pause scheduled jobs (stop auto-run)
  14) Resume scheduled jobs
```

---

## Making Changes to the Script

When you edit `main.py`, deploy the update in two steps:

**Option A — Use the management menu:**
```
./manage.sh → option 6
```

**Option B — Run the command directly:**
```bash
gcloud builds submit \
    --tag us-central1-docker.pkg.dev/ibl-planning-center-check-ins/roster-repo/roster:latest \
    --project=ibl-planning-center-check-ins
```

The new code will be used on the next scheduled run. To test it immediately, use option 7 or 8 in `manage.sh`.

---

## Auto Group to Check-In Script (`groups_to_check_ins.py`)

This script looks up all members of a Planning Center Group and checks them all into the most recent event period in one shot.

### Configuration

At the top of `auto_checkin.py`, set:

```python
EVENT_NAME    = "Escuela Dominical"   # The Check-Ins event name
GROUP_NAME    = "11th and 12th Grade" # The PCO Group name
LOCATION_NAME = "11th and 12th Grade" # The location within the event
BATCH_SIZE    = 25                    # People per request (keep at 25)
```

### Browser Session Setup

This script uses the PCO web interface internally (not the public API), so it needs your browser session cookie.

**Getting your session cookie:**
1. Open **https://check-ins.planningcenteronline.com** while logged in
2. Open DevTools (`F12`) → **Application** tab → **Cookies** → `check-ins.planningcenteronline.com`
3. Copy the value of `planning_center_session`

**Getting your CSRF token:**
1. In DevTools → **Console**, run:
   ```javascript
   document.querySelector('meta[name=csrf-token]').content
   ```
2. Copy the output

Add both to your `.env`:
```
PCO_SESSION_COOKIE=your_session_cookie_value
PCO_CSRF_TOKEN=your_csrf_token_value
```

> ⚠️ Session cookies expire when you log out or after a period of inactivity. If the script fails with a session error, grab a fresh cookie from your browser.

### Running It

```bash
python auto_checkin.py
```

Expected output:
```
=======================================================
  Auto Check-In: 11th and 12th Grade → Escuela Dominical
=======================================================
Looking up group: '11th and 12th Grade'...
  Found group ID: 12345
Fetching members of group 12345...
  Found 18 members.
Finding Check-Ins event: 'Escuela Dominical'...
  Found event ID: 937274
Finding last Sunday's event period...
  Last Sunday: 2026-03-15
  ✓ Matched event period: 44188503
Building session from browser cookie...
  ✓ Session valid

Bulk checking in 18 members in batches of 25...

  Sending batch 1 (18 people)...
  ✓ 18 checked in, 0 duplicates skipped

=======================================================
  Done! 18 checked in, 0 duplicates, 0 errors.
=======================================================
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `429 Too Many Requests` | The script auto-retries with backoff. Wait for it. |
| `SSL EOF / ReadTimeout` | Same — auto-retries up to 7 times. If it keeps failing, try again later. |
| `Event 'X' not found` | Check the exact event name in Planning Center — it's case-sensitive. |
| `credentials.json not found` | Make sure the file is in the project root for local runs. For cloud, use `manage.sh` option 4. |
| Session cookie expired (`auto_checkin.py`) | Grab a fresh `planning_center_session` cookie from your browser. |
| PDF only shows 1 person | You may be running an older version of `main.py`. Pull the latest. |
| Build fails with `file not found` | Never put `credentials.json` in the Docker build — it's handled via Secret Manager. |

---

## Security

- **Never commit** `.env` or `credentials.json` to git
- Both are in `.gitignore` by default
- In production, all secrets live in Google Secret Manager — not in the image or environment files
- Rotate your PCO token at **https://api.planningcenteronline.com/oauth/applications** if it is ever exposed
- Rotate your Google service account key in the Cloud Console if it is ever exposed

---

## Schedule Reference

| Job | Schedule | Time |
|-----|----------|------|
| Rutas | Every Monday | 2:00 AM US Central |
| Escuela Dominical | Every Monday | 2:00 AM US Central |

The scheduler runs at `0 8 * * 1` UTC (= 2 AM CST / 3 AM CDT). If the PDFs are showing the wrong week's data, it may be a daylight saving time offset — adjust the scheduler hour in the Cloud Console or via `manage.sh` option 12.