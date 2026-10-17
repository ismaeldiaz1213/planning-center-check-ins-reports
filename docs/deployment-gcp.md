# Deploying to Google Cloud

The roster system runs as two **Cloud Run Jobs** (one for bus routes, one for Sunday school)
on a weekly Cloud Scheduler trigger. An optional **Cloud Run Service** hosts the web UI
(FastAPI + React) for administrators.

---

## Prerequisites

- A Google Cloud project with billing enabled
- Google Cloud CLI installed (`gcloud --version`)
- `credentials.json` in the project root (see [configuration.md](configuration.md))
- `.env` file filled in with `GCP_PROJECT_ID`, `GCP_SA_EMAIL`, `PCO_APP_ID`, `PCO_SECRET`,
  `GOOGLE_DRIVE_PARENT_FOLDER_ID`

---

## First-time setup

Run once to create all Cloud resources:

```bash
chmod +x setup_gcloud.sh
./setup_gcloud.sh
```

The script walks through interactively:

1. Enables required GCP APIs (Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Scheduler)
2. Creates an Artifact Registry repository for Docker images
3. Stores PCO credentials and `credentials.json` as secrets in Secret Manager
4. Builds the Docker image and pushes to Artifact Registry
5. Creates one Cloud Run Job per report in `reports.yaml` (`roster-rutas`, `roster-escuela`, `roster-escuela-b`, …)
6. Creates the Cloud Scheduler jobs (Monday 8:00 AM UTC = 2:00 AM CST)

> After setup, run `./manage.sh` → **10 (Sync)** once. It adds the single `roster-weekly` job
> (`main.py --all`) with its Monday schedule and offers to remove the per-report schedules,
> which `roster-weekly` replaces.

After it finishes, run `./manage.sh → option 11` to confirm every report's job has a green status.

---

## Day-to-day management

```bash
./manage.sh
```

All routine operations go through this menu:

```
SECRETS
  1)  Update PCO App ID
  2)  Update PCO Secret
  3)  Update Google Drive Folder ID
  4)  View current secret values

DEPLOYMENT
  5)  Update credentials.json (upload secret + redeploy jobs)
  6)  Deploy updated code to Cloud (jobs)
  7)  Change campaign theme

TESTING & LOGS
  8)  Run a report job now (test)
  9)  View logs for a report
  10) Sync Cloud Run jobs with reports.yaml
  11) View job status (last run results)

SCHEDULER
  12) View scheduled jobs
  13) Pause scheduled jobs
  14) Resume scheduled jobs

API SERVICE
  15) Deploy / redeploy API service (web UI + API)
  16) View API service URL
  17) View API service logs
  18) Open API service in browser

LOCAL TESTING
  19) Build local Docker image
  20) Dry-run a report — all locations
  21) Dry-run a report — single location

DEMO SERVICE
  22) Deploy Demo Service
  23) View Demo URL
  24) Open Demo in browser
```

Options 8, 9, 20 and 21 list the reports from `reports.yaml` and let you pick one.

### Option 10 — Sync Cloud Run jobs

Reconciles Cloud Run with `reports.yaml`:

- **Creates** a `roster-<id>` job (unscheduled, for one-off runs) for any report that doesn't
  have one, and the `roster-weekly` job + `run-roster-weekly` Monday schedule that runs every
  report in one process. A report newly added to `reports.yaml` is picked up by `roster-weekly`
  with no further setup.
- **Offers to delete per-report schedules** (`run-roster-<id>`) left from before
  `roster-weekly` — otherwise rosters would be generated twice.
- **Reports orphans** — any `roster-*` job with no matching report — and offers to delete them
  along with their schedules. This matters after renaming a report id.

Option 6 (deploy code) also creates missing jobs, but only option 10 finds orphans.

---

## Deploying a code change

When you edit anything in `backend/`:

```bash
cd backend && ruff check . && pytest   # verify first
cd ..
./manage.sh → option 6
```

Option 6 builds a new Docker image and updates every report's Cloud Run Job in one step.
You must do both — pushing the image alone does not update the running jobs.

To do it manually (replace `YOUR_PROJECT` with your GCP project ID):

```bash
gcloud builds submit \
    --tag us-central1-docker.pkg.dev/YOUR_PROJECT/roster-repo/roster:latest \
    --project=YOUR_PROJECT

gcloud run jobs update roster-rutas \
    --image=us-central1-docker.pkg.dev/YOUR_PROJECT/roster-repo/roster:latest \
    --region=us-central1 --project=YOUR_PROJECT

gcloud run jobs update roster-escuela \
    --image=us-central1-docker.pkg.dev/YOUR_PROJECT/roster-repo/roster:latest \
    --region=us-central1 --project=YOUR_PROJECT

# …repeat for each remaining roster-<report-id> job
```

---

## Changing the campaign theme

No rebuild needed — this only updates the job arguments:

```bash
./manage.sh → option 7
```

Or manually:

```bash
gcloud run jobs update roster-rutas \
    --args="rutas,--theme,primavera" \
    --region=us-central1 --project=YOUR_PROJECT
```

> **Important:** `--args` uses comma-separated tokens. `--theme primavera` (space) is wrong and
> will fail silently. Use `--theme,primavera` (comma).

To revert to no theme:

```bash
gcloud run jobs update roster-rutas \
    --args="rutas" \
    --region=us-central1 --project=YOUR_PROJECT
```

---

## Schedule

| Job | Cron | Default time |
|-----|------|-------------|
| `roster-weekly` | `0 8 * * 1` | Monday 8:00 AM UTC (2:00 AM CST / 3:00 AM CDT) |

To adjust for daylight saving time:
```bash
gcloud scheduler jobs update http run-roster-weekly --location=us-central1 \
    --schedule="0 7 * * 1" \
    --project=YOUR_PROJECT
```

---

## Web UI deployment

The web UI is served by a separate Cloud Run Service (`roster-api`). It hosts both the
React frontend and the FastAPI backend at the same URL.

Build the frontend first:

```bash
cd frontend && npm run build
```

This writes the built app to `backend/static/`. Then deploy:

```bash
./manage.sh → option 15
```

Option 15 reads `GOOGLE_CLIENT_ID` from `.env` and passes it to Cloud Run as an environment
variable automatically.

To get the service URL after deployment:

```bash
./manage.sh → option 16
```

---

## Credentials at runtime

`credentials.json` is **not** baked into the Docker image. It is stored in Secret Manager
under the name `google-service-account-key` and mounted into the container at runtime by
Cloud Run at `/secrets/credentials.json` — outside `/app`, since a Cloud Run secret volume
replaces the *entire* last directory of its mount path, which would hide `main.py` and
`planning_center_reports/` if mounted straight into `/app`. The `GOOGLE_APPLICATION_CREDENTIALS`
env var tells the app where to find it. `setup_gcloud.sh` handles this configuration for you.

To update `credentials.json` after rotating your service account key:

```bash
./manage.sh → option 5
```

This uploads the new file to Secret Manager and redeploys every report's job.

---

## Local Docker test

To verify the Docker image works with your credentials before deploying:

```bash
docker build -f Dockerfile -t roster-job .

docker run --rm \
  -v $(pwd)/credentials.json:/app/credentials.json \
  --env-file .env \
  roster-job python main.py rutas
```

This uses your local credentials and `.env` without touching any Cloud resources.
