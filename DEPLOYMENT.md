# Deployment Guide

This project has two independent deployment targets:

| Target | What it is | Where it runs |
|--------|-----------|---------------|
| **Cloud Run jobs** | The Python roster pipeline (`main.py`) | Google Cloud Run |
| **Frontend** | The React web UI (`frontend/`) | Any static host (your choice) |

The two targets are completely decoupled. The Cloud Run jobs run on a schedule
and never depend on the frontend being up. The frontend is purely a management
interface and can be deployed (or not) independently.

---

## 1. Cloud Run Jobs (the roster pipeline)

This is the existing, working deployment. No changes to the overall approach —
the code just lives under `backend/` now.

### Prerequisites

- `gcloud` CLI installed and authenticated
- `setup_gcloud.sh` has been run at least once
- `credentials.json` at the project root

### Deploy a code change

```bash
# From the PROJECT ROOT (where Dockerfile and manage.sh live)
./manage.sh
# → option 6: Deploy updated code
```

Behind the scenes this runs:
```bash
gcloud builds submit --tag <IMAGE> --project=ibl-planning-center-check-ins
gcloud run jobs update roster-rutas ...
gcloud run jobs update roster-escuela-dominical ...
```

The Dockerfile packages only the Python job — no frontend, no API server.

### What triggers a rebuild

Rebuild and redeploy (option 6) any time you change:
- Anything under `backend/planning_center_reports/`
- `backend/main.py`
- `backend/assets/` (theme images)
- `Dockerfile`

Do NOT rebuild just to change:
- The campaign theme → use `manage.sh` option 7 (updates args only)
- PCO or Drive secrets → use `manage.sh` options 1–3

### Environment variables in production

The Cloud Run jobs receive secrets via Google Secret Manager, injected at
runtime by the job definition. They are not baked into the Docker image.

| Secret name | How it's set |
|-------------|-------------|
| `PCO_APP_ID` | `manage.sh` option 1 |
| `PCO_SECRET` | `manage.sh` option 2 |
| `GOOGLE_DRIVE_PARENT_FOLDER_ID` | `manage.sh` option 3 |

`credentials.json` (the service account key) is baked into the image. If you
rotate the key, replace the file and redeploy with option 5 (not option 6).

---

## 2. Web API Server (`backend/api.py`)

`api.py` is the FastAPI server that the frontend talks to. It is **not** part
of the Cloud Run jobs — it needs to be deployed separately if you want the
frontend to work in production.

### Options for hosting the API

**Option A — Cloud Run service (recommended)**

A Cloud Run *service* (not a job) is always-on and receives HTTP requests.

```bash
# Build an image that runs the API server instead of main.py
# You need a separate Dockerfile for this, e.g. Dockerfile.api:

# FROM python:3.11-slim
# WORKDIR /app
# COPY backend/requirements.txt backend/requirements-web.txt ./
# RUN pip install --no-cache-dir -r requirements.txt -r requirements-web.txt
# COPY backend/ .
# COPY credentials.json .
# CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]

gcloud run deploy roster-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --project ibl-planning-center-check-ins
```

**Option B — Any Python host**

The API is a standard ASGI app. It runs on Render, Railway, Fly.io, or any
host that can run `uvicorn api:app`. Install `requirements.txt` +
`requirements-web.txt`, set the environment variables, and point it at the
`backend/` directory.

**Option C — Skip it for now**

If you only want the Cloud Run jobs (no web UI in production), don't deploy the
API. Everything else keeps working — `manage.sh`, the scheduled jobs, PDF
uploads — with no API server involved.

### Environment variables for the API server

The API imports `planning_center_reports`, which reads `.env` on startup.
In a cloud deployment, inject these as environment variables directly:

```
PCO_APP_ID=...
PCO_SECRET=...
GOOGLE_DRIVE_PARENT_FOLDER_ID=...
```

---

## 3. Frontend (`frontend/`)

The React app is a pure static site after `npm run build`. It can be hosted
anywhere that serves static files.

### Build

```bash
cd frontend
npm run build
# Output goes to backend/static/ for local use.
# For a standalone deployment, specify a different outDir or just use the dist:
npm run build -- --outDir dist
```

### Option A — Netlify (simplest)

1. Push the repo to GitHub (already done).
2. Go to [netlify.com](https://netlify.com) → New site from Git.
3. Set:
   - **Base directory:** `frontend`
   - **Build command:** `npm run build`
   - **Publish directory:** `frontend/dist`
4. Add environment variable (if needed — the frontend itself has no secrets;
   it just needs the API URL to be correct, see below).
5. Deploy. Netlify gives you a URL like `https://ibl-roster.netlify.app`.

### Option B — Vercel

```bash
cd frontend
npx vercel --prod
```

Vercel auto-detects Vite. Set the output directory to `dist` if it asks.

### Option C — Firebase Hosting (already on GCP)

```bash
npm install -g firebase-tools
firebase login
firebase init hosting   # select your project, public dir = frontend/dist
cd frontend && npm run build -- --outDir dist
firebase deploy
```

### Pointing the frontend at the production API

In development, `vite.config.ts` proxies `/api/*` to `localhost:8000`. In
production the frontend and API are on different origins, so you need to:

1. Set the API base URL. The simplest approach is to add an environment
   variable at build time:

   ```typescript
   // frontend/src/api/client.ts
   const BASE = import.meta.env.VITE_API_URL ?? ''
   ```

2. Set `VITE_API_URL=https://your-api-url.run.app` in the hosting platform's
   environment variables (Netlify / Vercel / Firebase).

3. Make sure the production API server has CORS configured to allow your
   frontend's origin. In `backend/api.py`, add the production URL:

   ```python
   allow_origins=[
       "http://localhost:5173",
       "https://your-frontend-url.netlify.app",  # ← add this
   ]
   ```

---

---

## Running the test suites

Both the backend and frontend have complete test suites that run without
credentials, network access, or Docker.

---

### Backend tests (pytest)

Tests live in `backend/tests/`. They cover PDF generation, address parsing,
attendance logic, grade logic, escuela dominical logic, helpers/routes, and
the full API layer (settings endpoints, job store, run endpoints, .env helpers).

#### Setup (first time)

```bash
cd backend
pip install -r requirements.txt -r requirements-web.txt -r requirements-dev.txt
```

> `requirements-dev.txt` adds `pytest`, `ruff`, and `httpx` (needed by
> FastAPI's `TestClient`).

#### Run all tests

```bash
cd backend
python -m pytest
```

#### Run just the API tests

```bash
cd backend
python -m pytest tests/test_api.py -v
```

#### Run the linter

```bash
cd backend
ruff check .
```

Expected result: **168 tests, 0 failures.**

---

### Frontend tests (Vitest + Testing Library)

Tests live in `frontend/src/components/__tests__/`. They cover every React
component — Footer, Navbar, StatusBadge, TileCard, HomePage, PreviewModal,
JobModal, SettingsModal, and LogsModal — using `jsdom` and
`@testing-library/react`. API calls are mocked with `vi.mock`.

#### Setup (first time)

```bash
cd frontend
npm install
```

#### Run all tests (single pass)

```bash
cd frontend
npm test
```

#### Watch mode (re-runs on file change)

```bash
cd frontend
npm run test:watch
```

Expected result: **69 tests, 0 failures.**

---

## Production checklist

Before going live, confirm:

- [ ] Cloud Run jobs deploy successfully (`manage.sh` option 6)
- [ ] Jobs run successfully on demand (`manage.sh` option 8 and 9)
- [ ] PDFs appear in Google Drive after the test runs
- [ ] API server is reachable at its production URL (`/api/health` returns `{"status":"ok"}`)
- [ ] Frontend is live and can reach the API (`/api/previews` returns PDF list)
- [ ] CORS in `backend/api.py` includes the frontend's production origin
- [ ] `VITE_API_URL` is set in the frontend hosting platform
- [ ] No secrets are committed to git (`.env`, `credentials.json` are in `.gitignore`)
- [ ] Google Secret Manager has the latest values for all three secrets

---

## Summary of what talks to what

```
Cloud Scheduler
  → triggers Cloud Run jobs (roster-rutas, roster-escuela-dominical)
      → runs backend/main.py inside Docker
          → calls Planning Center API
          → uploads PDFs to Google Drive
          (completely independent of the frontend)

Browser (user)
  → React frontend (static host: Netlify / Vercel / Firebase)
      → calls backend/api.py (Cloud Run service or other Python host)
          → calls Planning Center API   (for running jobs)
          → calls backend/preview.py   (for PDF previews)
          → serves PDFs from backend/previews/
```
