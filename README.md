# IBL Planning Center — Automated Roster System

Automatically generates PDF rosters from Planning Center check-ins and uploads them to Google Drive every Monday at 2 AM. A web UI lets administrators manage the system from any browser. Built for **Iglesia Bautista Libertad** in Houston, TX.

---

## Features

- 📋 **Two roster types per bus route** — an address-grouped PDF for bus secretaries and a clean alphabetical roster for drivers
- 🏫 **Sunday school rosters** — one per class with grade, attendance rate, and route column showing which bus each child rides
- 📈 **Attendance summary tables** at the bottom of each Sunday school roster — per-Sunday regular/visitor counts and a per-route headcount
- 🟡 **Yellow highlights** for missing data (phone, birthday, address, grade) so staff know what needs updating
- 🟠 **Visitor dot** — gold circle marks people added to PCO within the last 7 days; visitor status is recalculated per Sunday for historical accuracy
- 📊 **Attendance rate** — shows how many of the last N weeks each person attended (e.g. `3/5`)
- 🎨 **Campaign themes** — seasonal colour schemes for special events
- 🌐 **Web UI** — dashboard for triggering jobs, previewing PDFs, editing settings, and viewing logs; served from the same Cloud Run URL as the API
- 🔐 **Google OAuth login** — access restricted to `iblibertad.org` / `iblibertad.com` Google accounts; unauthenticated requests are rejected before reaching any API route
- ☁️ **Fully automated** via Google Cloud Run + Cloud Scheduler

---

## Project Structure

The codebase is split into `backend/` (Python pipeline + FastAPI server) and
`frontend/` (React web UI). The Cloud Run jobs and `manage.sh` workflow are
unchanged for production use. The web UI is deployed as a separate Cloud Run
Service alongside the existing jobs.

```
planning-center-check-ins-reports/
│
├── backend/                       # All Python source
│   ├── planning_center_reports/   #   Main package
│   │   ├── config.py              #     Environment variables, layout constants, themes
│   │   ├── models.py              #     Attendee type + pure helper functions
│   │   ├── pco_client.py          #     Planning Center API calls
│   │   ├── drive_client.py        #     Google Drive upload logic
│   │   ├── services.py            #     Orchestration: fetch → transform → generate → upload
│   │   ├── cli.py                 #     argparse entrypoint
│   │   └── pdf/
│   │       ├── layout.py          #     Low-level ReportLab drawing primitives
│   │       └── rosters.py         #     generate_address_pdf, generate_simple_roster_pdf
│   ├── main.py                    #   Cloud Run job entrypoint
│   ├── preview.py                 #   Local preview tool — generates PDFs with mock data
│   ├── api.py                     #   FastAPI server — serves web UI + REST API
│   ├── static/                    #   Built React app (output of npm run build, not committed)
│   ├── tests/                     #   pytest test suite (185 tests)
│   ├── requirements.txt           #   Core deps — used by the job Dockerfile
│   ├── requirements-web.txt       #   FastAPI + uvicorn — API service only
│   └── requirements-dev.txt       #   Dev tools: pytest, ruff
│
├── frontend/                      # React + TypeScript web UI (Vite)
│   ├── src/
│   │   ├── auth/AuthContext.tsx    #   Google OAuth credential state + login/logout
│   │   ├── components/
│   │   │   ├── LoginOverlay.tsx    #   Full-screen Google sign-in gate
│   │   │   └── ...                #   Navbar, tiles, modals
│   │   └── api/client.ts          #   fetch wrappers — auto-injects Authorization header
│
├── Dockerfile                     # Cloud Run job image (Python only, no frontend)
├── Dockerfile.api                 # Cloud Run service image (FastAPI + built React SPA)
├── cloudbuild-api.yaml            # Cloud Build config for the API service image
├── .github/workflows/ci.yml       # GitHub Actions CI — backend lint+test, frontend type-check+build+test
├── credentials.json               # Google service account key (never commit this)
├── .env                           # Local credentials (never commit this)
├── .env.example                   # Template — copy to .env and fill in
├── .gcloudignore                  # Tells gcloud what to exclude from builds
├── .gitignore                     # Excludes credentials.json, .env, build output
├── setup_gcloud.sh                # Run ONCE to deploy Cloud Run jobs to Google Cloud
├── manage.sh                      # Day-to-day management (deploy, theme, logs, web UI)
```

---

## PDF Output

### Rutas (Bus Routes)

Each bus route folder in Google Drive receives two PDFs every Monday:

| File | Description |
|------|-------------|
| `Direcciones-Roster.pdf` | People grouped by apartment complex, sorted by unit number. Includes empty writable rows for walk-ins, address prefilled. |
| `Roster.pdf` | Clean alphabetical list sorted by last name. Good for drivers. |

### Escuela Dominical (Sunday School)

Each class location receives:

| File | Description |
|------|-------------|
| `Roster.pdf` | Alphabetical roster with grade, bus route number, attendance rate, and visitor indicators. Includes attendance summary tables at the bottom showing per-Sunday regular/visitor counts and a per-route headcount. |

Bus workers (helpers age 16+ from Junta de Rutas Attendance) appear on the roster with a blank Ruta column — they are present but not counted toward route totals.

### Column Reference

| Column | Notes |
|--------|-------|
| ● / ⚽ | Visitor marker — gold dot by default; soccer ball PNG for the `primavera` theme |
| Nombre / Apellido | First and last name |
| Cumpleaños | Birthday in MM/DD/YYYY format |
| Teléfono | Primary phone number |
| Grado | PCO grade field; auto-filled as Nursery / 3 años / 4 años for children under 5 |
| Apto. | Apartment number extracted from address |
| Ruta | Bus route number (e.g. `1`, `2`) — Escuela Dominical rosters only; blank for helpers |
| Asist. | Attendance rate over the selected window (e.g. `4/5`) |
| Dirección | Street address without apartment number |

**Yellow highlighting** means the cell is missing or incomplete — phone, birthday, grade (for minors), and bad/city-only addresses all trigger this.

---

## Campaign Themes

Pass `--theme` to apply a seasonal colour scheme. The campaign name appears centered in the header. Yellow warning highlights are always preserved regardless of theme.

```bash
python main.py "Rutas" --theme primavera
python main.py "Rutas" --theme verano
python main.py "Rutas" --theme otono
python main.py "Rutas" --theme invierno
```

| Theme | Colours | Label | Visitor marker | Header icon |
|-------|---------|-------|----------------|-------------|
| *(none)* | IBL navy/blue (default) | — | Gold dot | — |
| `primavera` | Greens | Campaña de Primavera | Soccer ball PNG | Gold medal PNG |
| `verano` | Orange/red | Campaña de Verano | Gold dot | — |
| `otono` | Brown/tan | Campaña de Otoño | Gold dot | — |
| `invierno` | Deep indigo/blue | Campaña de Invierno | Gold dot | — |

Theme image assets live in `assets/`. To add a custom visitor or header icon to any theme, drop the PNG in `assets/` and set `visitor_icon` or `campaign_icon` to its filename in the theme dict inside `planning_center_reports/config.py`.

---

## Local Development & Testing

All backend commands run from the `backend/` directory.

### Running the test suite

```bash
cd backend
pip install -r requirements.txt -r requirements-web.txt -r requirements-dev.txt   # first time only
pytest
```

185 backend tests cover address parsing, grade logic, date formatting, attendance deduplication, route mapping, helper identification, Escuela Dominical route/visitor logic, PDF generation, the full API layer (settings, job store, run endpoints, .env helpers), CORS configuration, and Google OAuth token verification. 74 frontend tests cover all React components including the login overlay. None require Planning Center or Google Drive credentials.

```bash
ruff check .   # linter — run from backend/
```

For the full testing guide (including frontend tests), see [DEPLOYMENT.md](DEPLOYMENT.md#running-the-test-suites).

### Generating PDF previews

```bash
cd backend
python preview.py                          # all themes × all PDF types
python preview.py --theme primavera        # one theme
python preview.py --type escuela           # Escuela Dominical only
python preview.py --type direcciones --theme otono
python preview.py --open                   # open in PDF viewer after generating
```

Output goes to `previews/` in your project folder. Edit `MOCK_ATTENDEES` at the top of `preview.py` to test edge cases like missing fields, toddlers, or visitors.


---

## First-Time Setup

### Prerequisites

| Tool | Install |
|------|---------|
| Python 3.10+ | `python3 --version` to check |
| Google Cloud CLI | See below |

**Install Google Cloud CLI on Fedora:**
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

### Step 1 — Planning Center API Credentials

1. Go to **https://api.planningcenteronline.com/oauth/applications**
2. Click **New Personal Access Token**
3. Enable **Check-Ins** and **People**
4. Copy the **Application ID** and **Secret**

Test that they work:
```bash
curl -u YOUR_APP_ID:YOUR_SECRET \
  https://api.planningcenteronline.com/check-ins/v2/events
```

### Step 2 — Google Service Account

The project uses:
`ministry-account-pc@ibl-planning-center-check-ins.iam.gserviceaccount.com`

To generate a new key:
1. Go to **Cloud Console → IAM → Service Accounts**
2. Click the account → **Keys** tab → **Add Key → JSON**
3. Download, rename to `credentials.json`, place in project root

The service account needs **Editor** access to your Google Drive roster folder. Right-click the folder → **Share** → paste the email → set to **Editor**.

### Step 3 — Local `.env` File

```bash
cp .env.example .env
```

Fill in:
```
PCO_APP_ID=your_app_id_here
PCO_SECRET=your_secret_here
GOOGLE_DRIVE_PARENT_FOLDER_ID=your_drive_folder_id_here
```

The folder ID is the last part of the URL when you open the folder in Drive:
`https://drive.google.com/drive/folders/THIS_PART`

### Step 4 — Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 5 — Test Locally

```bash
python main.py "Rutas"
python main.py "Escuela Dominical"
```

### Step 6 — Deploy to Google Cloud

Run once:
```bash
chmod +x setup_gcloud.sh
./setup_gcloud.sh
```

The script walks through everything interactively — project setup, API enablement, secret storage, Docker build, job creation, and scheduling.

> ⚠️ `credentials.json` is baked into the Docker image at build time. The `.gcloudignore` file ensures gcloud includes it even though `.gitignore` excludes it from git. **Never commit `credentials.json`.**

---

## Web UI

The web UI is served by the `roster-api` Cloud Run Service — the same URL
hosts both the React frontend and the FastAPI backend.

```bash
./manage.sh → option 19   # open in browser
./manage.sh → option 17   # print the URL
```

Access is restricted to Google accounts with an `@iblibertad.org` or
`@iblibertad.com` email address. Visiting the URL shows a **Sign in with
Google** screen; the dashboard only loads after a successful sign-in. All API
routes reject requests without a valid Google ID token.

Dashboard tiles:
- **Rutas / Escuela Dominical** — trigger a job and watch live terminal output
- **Vista Previa** — generate and preview PDFs in-browser by season and type
- **Configuración** — edit PCO credentials, Drive folder, and job defaults
- **Registros** — browse all job history with expandable output logs

To deploy or redeploy the web UI after any code change: `manage.sh → option 16`.
Option 16 reads `GOOGLE_CLIENT_ID` from `.env` and passes it to Cloud Run automatically.

---

## Day-to-Day Management

```bash
./manage.sh
```

```
╔══════════════════════════════════════════════════════════╗
║        Church Roster — Cloud Management Menu             ║
╚══════════════════════════════════════════════════════════╝

  SECRETS
  1)  Update PCO App ID
  2)  Update PCO Secret
  3)  Update Google Drive Folder ID
  4)  View current secret values

  DEPLOYMENT
  5)  Update credentials.json (rebuild + redeploy jobs)
  6)  Deploy updated code to Cloud (jobs)
  7)  Change campaign theme

  TESTING & LOGS
  8)  Run Rutas job now (test)
  9)  Run Escuela Dominical job now (test)
  10) View logs — Rutas
  11) View logs — Escuela Dominical
  12) View job status (last run results)

  SCHEDULER
  13) View scheduled jobs
  14) Pause scheduled jobs
  15) Resume scheduled jobs

  API SERVICE
  16) Deploy / redeploy API service (web UI + API)
  17) View API service URL
  18) View API service logs
  19) Open API service in browser
```

---

## Deploying Code Changes

When you edit any file in `planning_center_reports/` (or `main.py`), deploy with:

```bash
# Option A — management menu
./manage.sh → option 6

# Option B — manual
gcloud builds submit \
    --tag us-central1-docker.pkg.dev/ibl-planning-center-check-ins/roster-repo/roster:latest \
    --project=ibl-planning-center-check-ins

gcloud run jobs update roster-rutas \
    --image=us-central1-docker.pkg.dev/ibl-planning-center-check-ins/roster-repo/roster:latest \
    --region=us-central1 --project=ibl-planning-center-check-ins

gcloud run jobs update roster-escuela-dominical \
    --image=us-central1-docker.pkg.dev/ibl-planning-center-check-ins/roster-repo/roster:latest \
    --region=us-central1 --project=ibl-planning-center-check-ins
```

> You must run **both** the build and the job update. Building alone does not update the running jobs.

---

## Changing the Campaign Theme

Via `manage.sh` → option 7 — pick from the menu, no rebuild needed.

Or manually:
```bash
gcloud run jobs update roster-rutas \
    --args="Rutas,--theme,primavera" \
    --region=us-central1 --project=ibl-planning-center-check-ins
```

> **Note:** Cloud Run `--args` is a comma-separated list of individual tokens. `--theme primavera` (with a space) is wrong — it becomes a single unrecognised argument. Use `--theme,primavera` (comma-separated) instead.

To revert to default:
```bash
gcloud run jobs update roster-rutas \
    --args="Rutas" \
    --region=us-central1 --project=ibl-planning-center-check-ins
```

---

## Auto Check-In (`auto_checkin.py`)

Bulk checks in all members of a PCO Group to the most recent event period.

**Configure at the top of the file:**
```python
EVENT_NAME    = "Escuela Dominical"
GROUP_NAME    = "11th and 12th Grade"
LOCATION_NAME = "11th and 12th Grade"
BATCH_SIZE    = 25
```

**Get your browser session cookie:**
1. Open **https://check-ins.planningcenteronline.com** while logged in
2. DevTools (`F12`) → **Application** → **Cookies** → copy `planning_center_session`
3. In DevTools Console run: `document.querySelector('meta[name=csrf-token]').content`

Add to `.env`:
```
PCO_SESSION_COOKIE=your_value
PCO_CSRF_TOKEN=your_value
```

```bash
python auto_checkin.py
```

> Session cookies expire on logout. Grab a fresh one if the script fails with a session error.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `429 Too Many Requests` | Script auto-retries with exponential backoff. Wait for it. |
| `SSL EOF / ReadTimeout` | Auto-retries up to 7 times. If persistent, try again later. |
| `Event 'X' not found` | Event name is case-sensitive — check exact name in PCO. |
| `No such file: main.py` in Cloud | Job is using a stale image. Run `manage.sh → option 6`. |
| PDFs not appearing in Drive | Confirm `ministry-account-pc` has Editor access to the Drive folder. |
| Job timed out | Both jobs are set to 3600s (1 hour). Should be sufficient for any church size. |
| Session cookie expired | Grab fresh `planning_center_session` from your browser. |
| Theme not applying | Remember to run both build + job update, or use `manage.sh → option 6` which does both. |
| `unrecognized arguments: --theme primavera` in logs | The deployed image is stale — run `manage.sh → option 6` to rebuild. Also ensure `--args` uses commas, not spaces, between tokens. |

---

## Security

- **Never commit** `.env` or `credentials.json` — both are in `.gitignore`
- `credentials.json` lives in the Docker image which is private to your Artifact Registry
- PCO credentials live in Google Secret Manager — never in the image
- Rotate your PCO token at **https://api.planningcenteronline.com/oauth/applications** if exposed
- Rotate your service account key in Cloud Console → IAM → Service Accounts if exposed

---

## Schedule

| Job | Cron | Time |
|-----|------|------|
| Rutas | `0 8 * * 1` | Monday 2:00 AM CST (8:00 AM UTC) |
| Escuela Dominical | `0 8 * * 1` | Monday 2:00 AM CST (8:00 AM UTC) |

During CDT (March–November) this runs at 3 AM instead. Adjust to `0 7 * * 1` in Cloud Scheduler during summer if needed.