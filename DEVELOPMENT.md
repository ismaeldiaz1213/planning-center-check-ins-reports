# Development Guide

Day-to-day reference for working with the codebase: running tests, generating
PDF previews, developing the web UI locally, and deploying to Google Cloud.

---

## Table of Contents

1. [Project layout](#project-layout)
2. [Backend — tests and previews](#backend--tests-and-previews)
3. [Frontend — running the web UI](#frontend--running-the-web-ui)
4. [Local full-stack workflow](#local-full-stack-workflow)
5. [Deploying code to Google Cloud](#deploying-code-to-google-cloud)
6. [Understanding CI](#understanding-ci)
7. [Development workflow summary](#development-workflow-summary)

---

## Project layout

```
planning-center-check-ins-reports/
│
├── backend/                        ← All Python source
│   ├── planning_center_reports/    ←   Main package
│   │   ├── config.py               ←     Constants, themes, env vars
│   │   ├── models.py               ←     Data types + pure helpers
│   │   ├── pco_client.py           ←     Planning Center API calls
│   │   ├── drive_client.py         ←     Google Drive upload
│   │   ├── services.py             ←     Fetch → transform → generate → upload
│   │   ├── cli.py                  ←     argparse entrypoint
│   │   └── pdf/
│   │       ├── layout.py           ←     ReportLab primitives
│   │       └── rosters.py          ←     PDF generators
│   ├── main.py                     ←   Cloud Run entrypoint
│   ├── preview.py                  ←   Local PDF preview (no credentials needed)
│   ├── api.py                      ←   FastAPI web server (optional, local use)
│   ├── tests/                      ←   pytest test suite
│   ├── requirements.txt            ←   Core deps (used by Docker)
│   ├── requirements-web.txt        ←   FastAPI + uvicorn (API server only)
│   └── requirements-dev.txt        ←   pytest + ruff (dev tools)
│
├── frontend/                       ← React web UI (TypeScript + Vite)
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/             ←   Navbar, tiles, modals
│   │   ├── i18n/                   ←   Spanish/English translations + context
│   │   ├── api/client.ts           ←   fetch wrappers for the backend API
│   │   └── hooks/useJob.ts         ←   Job polling hook
│   ├── package.json
│   └── vite.config.ts              ←   Dev proxy → localhost:8000
│
├── Dockerfile                      ← Cloud Run job image (Python only, no frontend)
├── manage.sh                       ← Cloud management menu
├── setup_gcloud.sh                 ← One-time GCP setup
├── credentials.json                ← Service account key (never commit)
└── .env                            ← Local secrets (never commit)
```

**Key rule:** the `Dockerfile` builds the Cloud Run job image only. It does not
include the frontend. The frontend is deployed separately (see `DEPLOYMENT.md`).

---

## Backend — tests and previews

All backend commands run from inside the `backend/` directory.

```bash
cd backend
```

### First-time setup

```bash
# Core dependencies (same as the Docker image)
pip install -r requirements.txt

# Dev tools (linter + tests)
pip install -r requirements-dev.txt

# API server dependencies (only needed if you want to run api.py locally)
pip install -r requirements-web.txt
```

### Run all tests

```bash
pytest
```

Expected output: `175 passed`.

### Run one file or one test

```bash
pytest tests/test_address_parsing.py
pytest tests/test_grade_logic.py::TestResolveGrade::test_infant_returns_nursery
```

### Linter

```bash
ruff check .
```

Ruff catches unused imports and style issues. Fix flagged lines, then re-run
until it prints nothing.

### Mirror CI locally

```bash
ruff check . && pytest
```

### Generate PDF previews (no credentials needed)

```bash
# All themes × all PDF types
python preview.py

# One theme
python preview.py --theme primavera

# Only Escuela Dominical rosters
python preview.py --type escuela

# Generate and open immediately
python preview.py --open
```

Output goes to `backend/previews/`. Edit `MOCK_ATTENDEES` in `preview.py` to
test edge cases (missing fields, toddlers, visitors, helpers).

---

## Frontend — running the web UI

The frontend is a React + TypeScript app built with Vite. It communicates with
the backend through the FastAPI server (`api.py`).

### First-time setup

```bash
cd frontend
npm install
```

### Start the dev server

```bash
npm run dev
```

Opens at `http://localhost:5173`. Vite automatically proxies `/api/*` and
`/previews/*` requests to the backend at `http://localhost:8000`, so you need
the backend API server running too (see below).

### Type-check without building

```bash
npx tsc --noEmit
```

### Build for production

```bash
npm run build
```

Writes the built app to `backend/static/`. When that directory exists, `api.py`
serves the SPA at `/*` (so the API and frontend are on the same origin in
production).

---

## Local full-stack workflow

You need two terminals — one for the API server, one for the frontend dev server.

**Terminal 1 — Backend API:**
```bash
cd backend
uvicorn api:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`.

The Vite proxy forwards:
- `GET/POST /api/*`       → FastAPI at port 8000
- `GET /previews/*.pdf`   → FastAPI static file mount
- `GET /ibl_logo.png`     → FastAPI

No CORS configuration is needed because Vite handles the proxy in development.
The backend only has CORS enabled for `localhost:5173` and `localhost:3000`.

### Running without the frontend

The backend works standalone — either as the CLI job:
```bash
cd backend
python main.py "Rutas"
python main.py "Escuela Dominical"
```

Or as the API server without a frontend (use the auto-generated docs at
`http://localhost:8000/docs` to call endpoints manually):
```bash
cd backend
uvicorn api:app --reload --port 8000
```

The frontend is entirely optional. The Cloud Run jobs and manage.sh continue
to work exactly as before without any frontend involvement.

---

## Deploying code to Google Cloud

The Cloud Run jobs run the Python pipeline only. The frontend is not part of
this deployment. See `DEPLOYMENT.md` for the complete production guide.

### Steps for a code change to the Cloud Run jobs

1. Make your change in `backend/planning_center_reports/` (or other backend files).
2. Run `ruff check . && pytest` from `backend/`.
3. Commit and push — CI will run automatically.
4. From the **project root**, run `./manage.sh → option 6`.
5. The script checks for `backend/main.py`, builds the Docker image, and updates
   both Cloud Run jobs.

### Changing the campaign theme (no rebuild needed)

```bash
./manage.sh → option 7
```

This updates the `--args` on the Cloud Run jobs. The existing image is reused.

### What the Docker image contains

```
/app/
  main.py
  planning_center_reports/
  ibl_logo.png
  assets/
  credentials.json
```

The image does **not** contain `api.py`, `preview.py`, `tests/`, or anything
from the `frontend/` directory.

### Deploying the API Service

The API service (`Dockerfile.api`) is a separate Cloud Run **Service** (always-on
HTTP) that serves both the FastAPI backend and the built React SPA.

**First-time deploy:**

```bash
# 1. Build the React app (output goes to backend/static/)
cd frontend && npm run build && cd ..

# 2. From the project root, run manage.sh
./manage.sh → option 16
```

Option 16 runs `npm run build` automatically and then calls `gcloud builds
submit --config cloudbuild-api.yaml`.

**Subsequent deploys (code change):**

```bash
./manage.sh → option 16   # builds frontend, rebuilds image, updates service
```

**View the live URL:**

```bash
./manage.sh → option 17
```

**View logs:**

```bash
./manage.sh → option 18
```

**CORS configuration:**

In production the API and frontend share the same Cloud Run URL, so CORS is not
needed. For local development the API allows `localhost:5173` and `localhost:3000`
by default.

To add extra allowed origins (e.g. a custom domain), set the `ALLOWED_ORIGINS`
environment variable on the Cloud Run service before redeploying:

```bash
gcloud run services update roster-api \
  --update-env-vars ALLOWED_ORIGINS="https://roster.yourdomain.com" \
  --region us-central1 \
  --project ibl-planning-center-check-ins
```

---

## Understanding CI

GitHub Actions runs on every push:

- **backend job** — `ruff check .` + `pytest` (from `backend/`, Python 3.11)
- **frontend job** — `tsc --noEmit` + `vite build` (from `frontend/`, Node 20)

CI never deploys to production — that is always a manual step via `manage.sh`.

To see results: **GitHub → Actions tab** → look for green checks or red Xs.

---

## Development workflow summary

```
Backend change (Python):
  1. Edit files in backend/planning_center_reports/
  2. cd backend && ruff check . && pytest
  3. python preview.py --open   ← if PDF layout changed
  4. git add / commit / push
  5. CI passes → ./manage.sh option 6 to deploy

Frontend change (React/TypeScript):
  1. Edit files in frontend/src/
  2. cd frontend && npx tsc --noEmit   ← type-check
  3. Verify in browser at localhost:5173 (with API server running)
  4. git add / commit / push
  5. CI passes → deploy frontend per DEPLOYMENT.md

Adding a new test:
  - Add a class/method in backend/tests/test_something.py
  - cd backend && pytest tests/test_something.py

Adding a theme asset:
  1. Drop the PNG into backend/assets/
  2. Set visitor_icon or campaign_icon in backend/planning_center_reports/config.py
  3. python preview.py --theme <theme> --open
  4. ./manage.sh option 6  ← assets/ is copied by the Dockerfile
```
