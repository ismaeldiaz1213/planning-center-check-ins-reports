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
5. Creates the two Cloud Run Jobs (`roster-rutas`, `roster-escuela-dominical`)
6. Creates the Cloud Scheduler jobs (Monday 8:00 AM UTC = 2:00 AM CST)

After it finishes, run `./manage.sh → option 12` to confirm both jobs have a green status.

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

## Deploying a code change

When you edit anything in `backend/`:

```bash
cd backend && ruff check . && pytest   # verify first
cd ..
./manage.sh → option 6
```

Option 6 builds a new Docker image and updates both Cloud Run Jobs in one step. You must
do both — pushing the image alone does not update the running jobs.

To do it manually (replace `YOUR_PROJECT` with your GCP project ID):

```bash
gcloud builds submit \
    --tag us-central1-docker.pkg.dev/YOUR_PROJECT/roster-repo/roster:latest \
    --project=YOUR_PROJECT

gcloud run jobs update roster-rutas \
    --image=us-central1-docker.pkg.dev/YOUR_PROJECT/roster-repo/roster:latest \
    --region=us-central1 --project=YOUR_PROJECT

gcloud run jobs update roster-escuela-dominical \
    --image=us-central1-docker.pkg.dev/YOUR_PROJECT/roster-repo/roster:latest \
    --region=us-central1 --project=YOUR_PROJECT
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
    --args="Rutas,--theme,primavera" \
    --region=us-central1 --project=YOUR_PROJECT
```

> **Important:** `--args` uses comma-separated tokens. `--theme primavera` (space) is wrong and
> will fail silently. Use `--theme,primavera` (comma).

To revert to no theme:

```bash
gcloud run jobs update roster-rutas \
    --args="Rutas" \
    --region=us-central1 --project=YOUR_PROJECT
```

---

## Schedule

| Job | Cron | Default time |
|-----|------|-------------|
| `roster-rutas` | `0 8 * * 1` | Monday 8:00 AM UTC (2:00 AM CST / 3:00 AM CDT) |
| `roster-escuela-dominical` | `0 8 * * 1` | Monday 8:00 AM UTC (2:00 AM CST / 3:00 AM CDT) |

To adjust for daylight saving time:
```bash
gcloud scheduler jobs update http roster-rutas-schedule \
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
./manage.sh → option 16
```

Option 16 reads `GOOGLE_CLIENT_ID` from `.env` and passes it to Cloud Run as an environment
variable automatically.

To get the service URL after deployment:

```bash
./manage.sh → option 17
```

---

## Credentials at runtime

`credentials.json` is **not** baked into the Docker image. It is stored in Secret Manager
and mounted into the container at runtime by Cloud Run. `setup_gcloud.sh` handles this
configuration for you.

To update `credentials.json` after rotating your service account key:

```bash
./manage.sh → option 5
```

This uploads the new file to Secret Manager and redeploys both jobs.

---

## Local Docker test

To verify the Docker image works with your credentials before deploying:

```bash
docker build -f Dockerfile -t roster-job .

docker run --rm \
  -v $(pwd)/credentials.json:/app/credentials.json \
  --env-file .env \
  roster-job python main.py "Rutas"
```

This uses your local credentials and `.env` without touching any Cloud resources.
