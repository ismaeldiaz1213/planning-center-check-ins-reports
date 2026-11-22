# Platform guide: Advanced Reports for Planning Center

How the multi-church platform is put together, how to run it locally, how to deploy it, and
how to look after it once it's live. For *why* and *what's next*, read
[`advanced-reports-plan.md`](advanced-reports-plan.md) (decisions, milestones, status). For the
step-by-step launch checklist, read [`launch-guide.md`](launch-guide.md).

_Written 2026-11-22, the night staging first worked end to end._

---

## 1. What runs where

| Piece | Where | What it does |
|---|---|---|
| Website + API | Cloud Run **service** `advanced-reports` | Dashboard pages (`advanced_reports/static/`), sign-in, settings, starting runs, serving PDFs |
| Runner | Cloud Run **job** `advanced-reports-runner` | One execution per run: `python -m advanced_reports.runner <org_id> <run_id>` |
| Scheduler | Cloud Scheduler `advanced-reports-dispatch` | `POST /internal/dispatch` every 10 minutes with the `X-AR-Dispatch-Key` header; starts weekly runs that are due |
| Documents | Firestore (default database) | Churches, settings, runs, sealed connection tokens (`churches/{org_id}/…`) |
| Files | Cloud Storage bucket `<project>-files` | The latest run's PDFs and each church's logo, encrypted per church |
| Keys | Secret Manager | `ar-master-key`, `ar-session-secret`, `ar-dispatch-key`, `pco-oauth-client-id/-secret`, `google-oauth-client-id/-secret` |
| Images | Artifact Registry `advanced-reports` | Keeps the 3 newest `platform:<git sha>` images |

Projects: `mannabyte-reports-staging` and `mannabyte-reports-prod` (Mannabyte account).
Staging: `https://advanced-reports-300061322405.us-central1.run.app`. Production isn't deployed
yet. IBL's original weekly job lives in `ibl-planning-center-check-ins` (IBL account) and is
separate: nothing here touches it.

## 2. Code map (`backend/advanced_reports/`)

| File | Responsibility |
|---|---|
| `app.py` | FastAPI app: routes, session, CSRF check, Planning Center and Google sign-in, run start, PDF download, `/internal/dispatch` |
| `settings.py` | Every environment setting, read once at start-up (`from_env`) |
| `runner.py` | One run: loads the church, runs the engine, records progress/stages/ETA, saves PDFs, copies to Drive (best effort) |
| `dispatch.py` | The weekly schedule: which churches are due, one run each |
| `core/tenant_repo.py` | **The only code that touches storage.** Everything for one church, every path under `churches/{org_id}` |
| `core/store.py` | Document store interface; `MemoryStore` (tests), `FileStore` (local), `open_store()` |
| `core/firestore_store.py` | Production document store (one JSON string per document) |
| `core/blobs.py` | File store: `LocalBlobs` (local), `GcsBlobs` (bucket), `open_blobs()` |
| `core/crypto.py` | Envelope encryption: per-church data keys, AES-GCM, bound to the path |
| `core/pco_oauth.py` | Planning Center OAuth: authorize, exchange, refresh, who signed in, admin check |
| `core/google_oauth.py` | Google OAuth for Drive (`drive.file` only) and the *Advanced Reports* folder |
| `core/connections.py` | Stored Planning Center connection → engine client (oauth, pat, demo) |
| `core/cloud_run.py` | Starts a run as a Cloud Run job execution with per-run arguments |
| `core/session.py` | Signed session cookies |
| `modules/checkin_reports.py` | The reports module: settings ↔ the engine's `ReportSpec` and `ChurchConfig` |
| `importers/ibl.py` | One-off: copy IBL's `.env` + `reports.yaml` setup into a church |
| `demo.py` | The made-up sample church for local demos and tests |
| `static/` | The dashboard: `app.js` (views), `i18n.js` (English/Spanish), `app.css` |

The report engine (`backend/planning_center_reports/`) is shared with the original single-church
tool. Its output is pinned by the golden tests (`backend/tests/golden/`): never change IBL's
output without a deliberate snapshot update.

### Rules the code enforces (plan §3.7)
1. The church id comes only from the signed session, never from the URL or body.
2. Only `TenantRepo` builds storage paths, and every one starts with `churches/{org_id}`.
3. One run = one process (one job execution) for one church.
4. Secrets and PDFs are sealed with the church's own data key, bound to their path, so a copied
   blob doesn't decrypt elsewhere.
5. `tests/platform/test_platform.py` has two-church tests for every route.

## 3. Running it locally

```bash
cd backend
.venv/bin/python -m pytest                       # 480+ tests, no credentials needed
AR_DEV_LOGIN=1 .venv/bin/uvicorn advanced_reports.app:create_app --factory --port 8000
# open http://localhost:8000 → sign in as the sample church or as IBL (imported from .env)
```

- `AR_DEV_LOGIN=1` adds a "local developer" sign-in, generates throwaway keys in
  `out/platform-data/`, and runs the schedule in-process once a minute.
- `AR_DEMO_STEP_SECONDS=0.5` slows the sample church down so progress is visible.
- Real Planning Center sign-in locally: put `PCO_OAUTH_CLIENT_ID/SECRET` in the environment and
  leave `AR_DEV_LOGIN` unset (it then needs `AR_MASTER_KEY` and `AR_SESSION_SECRET`). The OAuth
  app has `http://localhost:8000/auth/pco/callback` registered.
- Against real cloud storage: `AR_FIRESTORE_PROJECT=…`, `AR_BUCKET=…`, plus
  `gcloud auth application-default login` as the Mannabyte account.
- Store checks against real staging Firestore:
  `GOOGLE_CLOUD_QUOTA_PROJECT=mannabyte-reports-staging AR_TEST_FIRESTORE_PROJECT=mannabyte-reports-staging .venv/bin/python -m pytest tests/platform -k Stores`
  (writes under a throwaway `ci-tests/…` prefix and deletes it).

## 4. Deploying

```bash
bash deploy/platform.sh staging            # or prod
DRY_RUN=1 bash deploy/platform.sh staging  # prints every step, changes nothing
GOOGLE_CLIENT_JSON=~/Downloads/client_secret_….json bash deploy/platform.sh staging   # first time with Drive
```

The script is idempotent. It enables services, makes the registry, service account, bucket
(private, 45-day lifecycle) and secrets, builds the image **locally** (`Dockerfile.platform`)
and pushes it, deploys the job and the service, and creates or updates the scheduler. It never
prints a secret. The owner runs it: creating cloud resources needs their approval.

Things that were learned the hard way:
- **The website is public via `--no-invoker-iam-check`.** The organization restricts IAM members
  to mannabyte.com, so `allUsers` can't be granted.
- **The runner's whole command is in `--command`, args empty.** Execution overrides replace the
  job's args. With `--args=-m,advanced_reports.runner`, the first real run crashed with
  "can't open file '/app/418197'".
- **Cloud Build isn't used.** The org's defaults leave its service account without permissions.
- Callback addresses to register per environment:
  `<url>/auth/pco/callback` in the Planning Center app, `<url>/auth/google/callback` in the
  Google client.

## 5. Operating it

| Task | How |
|---|---|
| See the website's requests | `gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="advanced-reports"' --project=<p> --limit=20` |
| See a run's output | `gcloud run jobs executions list --job=advanced-reports-runner --project=<p> --region=us-central1`, then logs filtered by `labels."run.googleapis.com/execution_name"` |
| Re-run a stuck run in place | `gcloud run jobs execute advanced-reports-runner --args=<org_id>,<run_id> --async …`: the runner picks up the existing run document, so the dashboard keeps following it |
| Read a church's documents | Firestore documents hold a `json` string field: `json.loads(doc.to_dict()["json"])` |
| Rotate the dispatch key | `gcloud secrets versions add ar-dispatch-key …`, disable the old version, redeploy (the script updates the scheduler header) |
| Disconnect a church | The church does it from Settings → Disconnect: deletes its documents and files |

**Never print secret values in logs or tool output.** On 2026-11-22 the staging dispatch key
showed up in a `gcloud scheduler jobs describe` output (the sed meant to hide it didn't match).
Rotating it is still on the to-do list (launch guide).

## 6. Known gaps (as of 2026-11-22)

- **Google app is in *Testing*:** only listed test users can connect Drive, and connections
  expire after 7 days. Publishing needs the privacy page and the domain.
- **Planning Center token refresh** (every ~2 hours) is written and unit-tested but hadn't been
  exercised against the real service yet.
- **The Planning Center OAuth app is owned by IBL's organization.** Move it to a Mannabyte
  organization before the public launch (launch guide, "Moving the app to Mannabyte later").
- **Speed:** 81 of 88 seconds of the first real run were sequential Planning Center requests;
  Drive uploads added ~50 s. Next: parallel requests, faster Drive uploads, then the sync store.
- **Not built yet:** privacy and terms pages, custom domain, production deploy, picking an
  existing Drive folder (Google Picker), failure emails, the Route Builder, the Grade Promotion
  Helper and Sheets sync.
