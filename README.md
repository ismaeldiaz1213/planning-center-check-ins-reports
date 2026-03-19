# IBL Planning Center — Automated Roster & Check-In System

This project does two things automatically:

1. **Generates PDF rosters** from Planning Center check-ins and uploads them to Google Drive every Monday at 2 AM
2. **Bulk checks in entire groups** to an event (optional, run manually)

---

## Project Structure

```
planning-center-check-ins-reports/
├── main.py                  # Roster generator (Rutas + Escuela Dominical)
├── auto_checkin.py          # Optional: bulk check-in a group to an event
├── ibl_logo.png             # Church logo used in PDFs
├── credentials.json         # Google service account key (never commit this)
├── .env                     # Local credentials (never commit this)
├── .env.example             # Template — copy to .env and fill in
├── .gcloudignore            # Tells gcloud what to exclude from builds (.env only)
├── .gitignore               # Excludes credentials.json and .env from git
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container definition for Cloud Run
├── setup_gcloud.sh          # Run ONCE to deploy everything to Google Cloud
└── manage.sh                # Day-to-day management (update keys, test, logs)
```

---

## How It Works

### Roster Generator (`main.py`)

Run with an event name as the argument:

```bash
python main.py "Rutas"
python main.py "Escuela Dominical"
```

**`Rutas`** generates one PDF per bus route. People are grouped by apartment complex and sorted by unit number within each group. Empty rows are included for walk-ins. Missing birthdays, phones, and bad addresses are highlighted yellow.

**`Escuela Dominical`** generates one simple alphabetical roster per Sunday school class location with the same yellow highlighting for missing data.

Both PDFs include:
- IBL Libertad logo
- Route/class name as the title
- Generated date and time in Spanish
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
| Python 3.10+ | `python3 --version` to check |
| Google Cloud CLI | See below |

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

You should see JSON with your events listed.

---

### Step 2 — Google Service Account

The project uses:
`ministry-account-pc@ibl-planning-center-check-ins.iam.gserviceaccount.com`

If you need to generate a new key:
1. Go to **https://console.cloud.google.com/iam-admin/serviceaccounts?project=ibl-planning-center-check-ins**
2. Click the service account → **Keys** tab
3. **Add Key → Create New Key → JSON**
4. Download and rename it to `credentials.json`
5. Place it in the project root

The service account must have **Editor** access to your Google Drive roster folder. Right-click the folder in Drive → **Share** → paste the service account email → set to **Editor**.

---

### Step 3 — Google Drive Folder ID

1. Open your Google Drive roster folder in a browser
2. The URL looks like: `https://drive.google.com/drive/folders/XXXXXXXXXXXXXXXX`
3. The `XXXXXXXXXXXXXXXX` part is your folder ID

---

### Step 4 — Local `.env` File (for running locally)

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

Expected output:
```
Finding event 'Rutas'...
Event ID: 754993
Finding recent event periods (last 5 weeks)...
  [1] Fetching Isaac Ramirez (id: 149426747)...
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

This walks you through every step interactively:
- Logs into Google Cloud
- Creates/selects your project
- Enables required APIs
- Stores PCO credentials in Secret Manager
- Creates a `.gcloudignore` so `credentials.json` is included in builds
- Builds and pushes the Docker image
- Creates Cloud Run Jobs for Rutas and Escuela Dominical (using `ministry-account-pc`)
- Schedules both to run every Monday at 2 AM US Central

> ⚠️ `credentials.json` is baked into the Docker image at build time. The `.gcloudignore` file ensures gcloud includes it even though `.gitignore` excludes it from git. Never commit `credentials.json` to git.

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

  SECRETS
  1) Update PCO App ID
  2) Update PCO Secret
  3) Update Google Drive Folder ID
  4) View current secret values

  DEPLOYMENT
  5) Update credentials.json (rebuild + redeploy jobs)
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

When you edit `main.py`, deploy the update:

**Option A — Management menu (recommended):**
```
./manage.sh → option 6
```

**Option B — Manual commands:**
```bash
# 1. Rebuild the image
gcloud builds submit \
    --tag us-central1-docker.pkg.dev/ibl-planning-center-check-ins/roster-repo/roster:latest \
    --project=ibl-planning-center-check-ins

# 2. Update both jobs to use the new image
gcloud run jobs update roster-rutas \
    --image=us-central1-docker.pkg.dev/ibl-planning-center-check-ins/roster-repo/roster:latest \
    --region=us-central1 \
    --project=ibl-planning-center-check-ins

gcloud run jobs update roster-escuela-dominical \
    --image=us-central1-docker.pkg.dev/ibl-planning-center-check-ins/roster-repo/roster:latest \
    --region=us-central1 \
    --project=ibl-planning-center-check-ins
```

> ⚠️ You must run **both** the build and the job update. Building alone does not update the running jobs — they cache the image until explicitly told to refresh.

---

## Updating credentials.json

If your service account key expires or is rotated:

1. Download the new key from Cloud Console → rename to `credentials.json` → place in project folder
2. Run `./manage.sh` → option 5

This rebuilds the image with the new credentials and recreates both jobs cleanly.

---

## Auto Check-In Script (`auto_checkin.py`)

Looks up all members of a PCO Group and checks them all in at once.

### Configuration

At the top of `auto_checkin.py`:

```python
EVENT_NAME    = "Escuela Dominical"   # The Check-Ins event name
GROUP_NAME    = "11th and 12th Grade" # The PCO Group name
LOCATION_NAME = "11th and 12th Grade" # The location within the event
BATCH_SIZE    = 25                    # People per request (keep at 25)
```

### Browser Session Setup

This script uses the PCO web interface internally so it needs your browser session cookie.

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

> ⚠️ Session cookies expire when you log out. If the script fails with a session error, grab a fresh cookie from your browser.

### Running It

```bash
python auto_checkin.py
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `429 Too Many Requests` | Script auto-retries with backoff. Wait for it. |
| `SSL EOF / ReadTimeout` | Auto-retries up to 7 times. If persistent, try again later. |
| `Event 'X' not found` | Event name is case-sensitive — check exact name in Planning Center. |
| `No such file or directory: main.py` | Job is using an old cached image. Run `manage.sh → option 6` to rebuild and update. |
| `credentials.json not found` locally | Make sure the file is in the project root. |
| `credentials.json` excluded from build | Make sure `.gcloudignore` exists and only contains `.env`. |
| Job timed out after 10 minutes | Task timeout was too short. Both jobs are set to 3600s (1 hour) which is sufficient. |
| PDFs not appearing in Drive | Check that `ministry-account-pc` has Editor access to the Drive folder. |
| Session cookie expired (`auto_checkin.py`) | Grab a fresh `planning_center_session` cookie from your browser. |

---

## Security

- **Never commit** `.env` or `credentials.json` to git — both are in `.gitignore`
- `credentials.json` is baked into the Docker image at build time, which stays private in your Artifact Registry
- PCO credentials live in Google Secret Manager and are never in the image
- Rotate your PCO token at **https://api.planningcenteronline.com/oauth/applications** if ever exposed
- Rotate your Google service account key in Cloud Console → IAM → Service Accounts if ever exposed

---

## Schedule Reference

| Job | Schedule | Time |
|-----|----------|------|
| Rutas | Every Monday | 2:00 AM US Central |
| Escuela Dominical | Every Monday | 2:00 AM US Central |

The scheduler runs at `0 8 * * 1` UTC. During daylight saving time (CDT, March–November) this is 3 AM Central instead of 2 AM. To keep it at 2 AM year-round, update the schedule to `0 7 * * 1` in Cloud Scheduler during summer months via `manage.sh → option 12`.