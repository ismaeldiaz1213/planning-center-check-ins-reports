# Advanced Reports for Planning Center — Implementation Plan

Working plan for turning this single-church roster tool (built for Iglesia Bautista
Libertad, IBL) into **Advanced Reports for Planning Center**: a hosted, multi-church
platform that any church sets up through a **setup wizard** by signing in with Planning
Center. Church admins need zero technical experience: no terminal, no `.env`, no
`reports.yaml`. (Owner-side manual or hacky setup steps are fine.)

This document is the hand-off point between work sessions. **Update the Status section
whenever something is finished or a decision changes.** A new session cannot see earlier
chats, so this file must stay complete on its own.

---

## 0. Start here (for the implementing session)

1. Read this whole file, then `docs/IBL.md`, `docs/reports.md`, `docs/grade-promotion.md`.
2. Ask the owner for the answers in **§9 Blockers** that are still open. Don't guess them.
3. Work on a new branch off `main` (e.g. `feat/platform-m1`). **Never commit, push or
   open PRs.** The owner does all git operations. Make file changes freely.
4. Order of work is **§6 Milestone 1**, top to bottom. Golden tests and the benchmark
   baseline come first, because everything after depends on them.
5. **Record numbers as you go** in `docs/benchmarks.md` (see §5). The owner wants
   measurable before/after results for every performance claim, especially to justify
   the Rust work.
6. Keep IBL's current system (`roster-weekly` Cloud Run job, GCP project
   `ibl-planning-center-check-ins`) working and untouched until the cutover step says
   to pause it. Pause, never delete.

---

## Status

_Last updated: 2026-11-14 (Saturday, late; session paused mid step 3)_

| Item | State |
|---|---|
| Plan and decisions (this doc) | ✅ Rewritten 2026-11-14 |
| Onboarding meeting with Liberty Baptist Church | ✅ Done. They tried Check-Ins before and it didn't stick (complexity, no training). Clean, professional reports and a short setup are the priority. |
| Mannabyte Workspace email (`hello@`, `support@`, `admin@`) | ✅ Done per owner (2026-11-14) |
| Google Cloud organization and billing account | ✅ Exist (owner, 2026-11-14) |
| Google Cloud staging/production projects | ⬜ Not created |
| Planning Center Mannabyte account, OAuth app, fake test church | ⬜ None of it exists |
| Google OAuth client and consent screen | ⬜ Not started |
| Working branch | `feat/platform-m1`, branched from `chore/dependency-bumps` at the owner's request (see "Branch" below) |
| Milestone 1 step 1: golden tests | ✅ Done 2026-11-14 (`backend/tests/golden/`) |
| Milestone 1 step 2: benchmark baseline | 🟡 Local and render baselines recorded in `docs/benchmarks.md`. Production baseline (real `roster-weekly` runs), image size and cold start still missing. |
| Milestone 1 step 3: engine refactor | 🟡 **Code and tests done 2026-11-14** (375 tests pass, golden snapshots untouched). One check left: a live dry run against IBL, which needs the owner's go-ahead. See "Step 3" below. |
| Milestone 1 steps 4–7 | ⬜ Not started; steps 6–7 are blocked on the accounts above |
| Milestones 2–5 | ⬜ Not started |

**Next action:** owner approves one live `main.py --all --dry-run` (read-only, no upload) to close step 3; then step 4 (platform core). Production baseline still needs `gcloud auth login`.

### Step 3: engine refactor (code done 2026-11-14)

Nothing is committed; everything is in the working tree on `feat/platform-m1`. Run tests
with `cd backend && .venv/bin/pytest -q` and `.venv/bin/ruff check .`.

**State:** 375 passed, ruff clean. The 19 golden tests pass against snapshots last written
at 14:53 on 2026-11-14, before the refactor started (IBL's PDF text, drawing fingerprints,
filenames, Drive paths and request counts are identical). Two seams in
`test_golden_pipeline.py` moved with the code (the Drive patches now sit on `delivery`, and
the service-account delivery takes a key path); no snapshot was regenerated.

**Left to close the step:**
1. One live `main.py --all --dry-run` against IBL with the refactored engine, comparing its
   PDFs' text with `out/baseline-2026-11-14/`. Not run: the owner's earlier approval
   covered one live run, so this one needs a new yes.

**What step 3 changed (all files under `backend/`):**
- New: `planning_center_reports/i18n/{__init__,es,en}.py` (text catalogs; Spanish is
  IBL's wording exactly, English is an unreviewed first pass), `church.py` (`ChurchConfig`,
  `Branding`), `pdf/context.py` (`RenderContext`, replaces `config._theme` and `config.T`),
  `delivery.py` (`LocalDelivery`, `DriveServiceAccountDelivery`, `DriveOAuthDelivery`,
  `FanOutDelivery`), `legacy.py` (the only module that loads `.env`, reads settings from
  the environment, or caches `reports.yaml`), `tests/test_i18n.py`,
  `tests/test_drive_client.py`.
- Rewritten: `pco_client.py` (`PcoClient` class with its own pacing, stats and cache;
  `PersonalAccessToken` and `OAuthBearer` with one refresh on 401), `services.py`
  (`RunContext(church, pco, delivery)`; `run_report(ctx, spec, …)`, `run_all(ctx, theme)`),
  `reports.py` (no env, no loader; `find_report`, `OUTPUT_KINDS`), `config.py` (layout and
  colour constants only), `pdf/layout.py`, `pdf/rosters.py`, `pdf/volunteers.py`,
  `pdf/instructions.py`, `tests/test_run_report.py` (stub client + real deliveries),
  `tests/test_cli.py`.
- Adjusted: `roster_data.py` (`SundayCount.day` and `SundayVolunteers.day` are dates,
  `Period.label` removed, `Member.grade_num`, unassigned volunteer group is `None`),
  `models.py`, `mock_data.py`, `drive_client.py` (`get_oauth_drive_service`;
  `get_drive_service(credentials_path)` no longer reads `GOOGLE_APPLICATION_CREDENTIALS`
  itself, `legacy.drive_credentials_path()` does), `cli.py`, `api.py`, `preview.py`,
  `demo_run.py`, `promote_checkins.py`, `backfill_bus_class.py`, `bench/*.py`, and the
  remaining tests.
- `requirements-dev.txt`: `time-machine`, `reportlab==5.1.0`, `pypdf==7.1.0` (owner chose
  to pin for tests/CI only).
- Docs: `DEVELOPMENT.md` (layout, golden tests, how the engine is put together),
  `docs/benchmarks.md` (power-state caveat, old-versus-new render comparison).
  `docs/reports.md` and `docs/configuration.md` needed no change: they describe settings,
  and every setting behaves as before.

**Isolation checks that now exist (plan §3.7, engine level only):**
- Pipeline: `TestTwoChurchesRunBackToBack` in `test_run_report.py` runs church A, church B,
  church A again with real PDFs and the same Planning Center ids in both. Verified by
  breaking it on purpose: making the check-in cache shared between runs fails the test.
- Renderer: `TestTwoChurches` in `test_pdfs.py`. Client: `TestClientsShareNothing` in
  `test_pco_client.py`. Drive: two deliveries can use two key files (`test_drive_client.py`).
- Sweep for process-wide state in the engine outside `legacy.py`: no environment reads, no
  module-level caches. What remains is the naive clock (below).

**Checked by running, with mock data only:** `main.py --list-reports` (text and ids),
`preview.py` (all types, and `--report escuela-c --theme otono`), `demo_run.py escuela
verano`; `promote_checkins.py --help` and importing `backfill_bus_class`. The `Dockerfile`
copies the whole `planning_center_reports/` directory and `Dockerfile.api` copies
`backend/`, so the new `i18n/` package is included; neither image was built.

**Not verified, say so if asked:**
- The refactored engine has not run against live Planning Center (item 1 above).
- `DriveOAuthDelivery` has never talked to Google. `test_drive_client.py` checks which
  Drive calls we make against an in-memory stand-in, not that Google accepts them, and not
  how `drive.file` behaves.
- `promote_checkins.py` and `backfill_bus_class.py` were edited mechanically; only their
  argument parsing and imports were exercised, not a real run.
- `api.py` and `demo_run.py` rely on their existing tests plus the one demo run above.
- Ages and the "Generado" time still use the server's clock (`date.today()` in
  `pco_client.py`, `models.py`, `reports.py`'s fallback; `datetime.now()` in
  `pdf/layout.py`). Deliberately unchanged, because fixing it changes IBL's output.
- No Docker image was built.

**Found along the way:**
- `drive_client.py` had no tests at all. A missing `import os` there (introduced and
  caught in this step, by ruff, not by a test) would have broken uploads that pass no file
  name. `tests/test_drive_client.py` now covers folder lookup/creation, replace, and
  skip-when-unchanged.
- `backend/previews/*.pdf` contains files that are tracked in git, and `preview.py` /
  `demo_run.py` overwrite them. Running them dirtied two tracked PDFs and added seven
  untracked ones; the two were restored to their committed bytes (`git show HEAD:… >`) and
  the seven deleted. Suggestion for the owner: untrack that folder and gitignore it.
- Without `GOOGLE_APPLICATION_CREDENTIALS`, the service-account key is looked for at
  `backend/credentials.json`, while the file on this machine is at the project root and
  `.env` does not set the variable. That is how the code already behaved before this work
  (the old comment said "project root" but the path resolved to `backend/`); it is kept
  as is. It means a non-dry local run outside Docker would not find the key.

**Benchmark caveat found during step 3:** the laptop went onto battery in power-save mode
(CPU capped at 2.0 GHz) and everything, including untouched pypdf code, ran about 2.5×
slower (IBL-sized render set 5.8 s instead of 2.3 s). An old-versus-new comparison under
that same state showed identical render times (median roster 98 ms both), so the refactor
costs nothing. The baseline in `docs/benchmarks.md` was taken at an unrecorded, faster
power state; this is now written into that file. Bench scripts do not yet record the power
state themselves.

### Answers to §9 (2026-11-14)

1. Google Cloud: organization and billing exist; the two projects do not.
2. Planning Center: nothing exists yet (no Mannabyte account, OAuth app or test church).
3. Google OAuth client and consent screen: not started.
4. IBL production baseline: the owner will re-authenticate `gcloud` on the development
   machine; the implementing session then runs read-only commands only.
5. Cutover Drive folder: **the owner wants the new platform to keep using IBL's existing
   folder** (he has a backup of it). This conflicts with the `drive.file` design; see
   "Open: IBL's Drive folder" below. Not settled.

Also decided: **the cutover date stays Sunday 2026-11-15, best effort.** The implementing
session's assessment, given to the owner: this date is unlikely to be met, because steps
3–6 are all still ahead and the accounts that steps 6–7 need do not exist. Nothing breaks
if it slips: the old job keeps producing rosters.

### Branch

The plan says "branch off `main`". Local `main` was six commits behind: v0.2.0 reached
`origin/main` through PR #21 with different commit hashes (`b55f0e3` there, `668ce43` on
`chore/dependency-bumps`), and the two trees are identical. The owner asked for
`feat/platform-m1` to be branched from `chore/dependency-bumps`, wanting one large PR
later. Consequence to remember at PR time: those six commits are already on `main` under
other hashes, so the PR will list them again (with no file differences of their own); a
squash merge hides that.

### Findings that change the plan's assumptions

- **The weekly run is not limited by Planning Center's rate limit.** Measured 2026-11-14:
  57.7 s total, 134 requests, 54.2 s waiting for responses, **0 s paused for the rate
  limit**, 2.8 s rendering. §1 "Language strategy" says the opposite and has been
  corrected below. The conclusion there still holds (fewer requests is the real win), but
  for a different reason: 134 sequential round trips at about 0.4 s each.
- **Rendering is 5% of today's run.** A Rust renderer 5× faster would save about 2.3 s of
  57.7 s. The §5.3 gate's third condition (rendering must be a meaningful share after the
  sync store) is the one most at risk.
- **PDFs print the generation time in the server's clock, not the church's.** `Page.gen_dt`
  and the age calculations use naive `datetime.now()` / `date.today()`. On Cloud Run that is
  UTC, so IBL's Monday run prints "a las 08:0x" for a 2–3 AM local run, and ages roll over
  by UTC date. The golden tests pin this behaviour as it is today. Fixing it is an IBL
  output change and needs a deliberate golden update; not done.
- **51 copies of a 1.5 MB instructions PDF** make up about 75 MB of each run's 79 MB
  output. Drive uploads skip unchanged copies (fingerprint), so this costs little today,
  but it matters for any design that stores PDF copies in Cloud Storage.
- **`reportlab` and `pypdf` are not version-pinned** (`requirements.txt`). The golden tests
  compare extracted text and drawing fingerprints, so a new release of either library can
  fail them on untouched code. `backend/tests/golden/snapshots/VERSIONS.txt` records what
  the snapshots were made with. Pinning both is recommended; not done without the owner.

### Open: IBL's Drive folder at cutover

The owner wants the existing folder reused. With the `drive.file` scope the new app can
only see files it created or the user picked, so it cannot find the old `Roster.pdf` files
to replace them: it would create second files with the same names beside them. Options:

- **A. Keep service-account delivery for IBL only** (`DriveServiceAccountDelivery`, already
  planned as the legacy path). Same folder, files replaced in place, teachers' links keep
  working. Cost: IBL's service-account key lives in the new platform's Secret Manager, a
  per-church special case. Recommended by the implementing session if the old folder must
  be kept.
- **B. Google Picker on the old folder** (Milestone 2). Unverified whether `drive.file`
  then allows creating files inside it (§8); even if it does, the old files stay invisible
  and duplicates appear unless the old files are removed first.
- **C. Fresh folder** (the plan's original recommendation).

### What exists on the branch now

- `backend/tests/golden/`: 19 golden tests. `harness.py` (frozen clock at Monday
  2026-10-12 08:00 UTC, pinned IBL settings, PDF → text + links + per-page drawing
  fingerprint, compare-or-update), `fake_pco.py` (a deterministic fake Planning Center
  served through `requests.get`), `test_golden_render.py` (every PDF type and theme from
  `mock_data`), `test_golden_pipeline.py` (`run_all()` end to end for the example config
  and IBL's: every delivered file, Drive folder path, upload mode, page count, dry-run file
  tree, request counts), `test_golden_config.py` (`parse_reports()` output),
  `fixtures/ibl_reports.yaml` (copy of the tracked `reports.yaml`), `snapshots/`.
  Refresh only with `pytest --update-golden` or `UPDATE_GOLDEN=1`.
- Verified by deliberately breaking the engine eight ways (PDF wording, output filename,
  Drive folder name, highlight colour, attendance-dot colour, extra API requests, who
  counts as new, dry-run folder naming): every one failed the golden tests.
- `PcoClient.stats` (`RequestStats`, per client since step 3): requests, network retries, 429s, response time,
  pacing and back-off waits. `main.py` prints a one-line summary at the end of a run. This
  is the only engine change so far; PDFs are unaffected.
- `backend/bench/live_baseline.py`, `backend/bench/render_bench.py`, `docs/benchmarks.md`.
- `time-machine` added to `requirements-dev.txt` (freezes the clock in golden tests).
- Local only, not in git: a Python 3.11 virtualenv at `backend/.venv` (listed in
  `.git/info/exclude`), and the live baseline's real rosters under `out/baseline-2026-11-14/`.

### Known limits of the golden tests

- The fake Planning Center's JSON shapes are inferred from what the engine reads, not
  recorded from the live API. The tests prove the engine behaves the same as before, not
  that it matches Planning Center.
- The drawing fingerprint says that something on a page changed, not what. When only a
  `[drawing]` line differs, compare the PDFs by eye.
- The instructions bundle's two guide PDFs are snapshotted as extracted text; their images
  are covered only by the fingerprint.
- The pipeline test patches Drive on `planning_center_reports.delivery`
  (`get_or_create_folder`, `upload_*`). Those patches moved there in step 3 with the
  `Delivery` interface; the snapshots stayed byte-for-byte the same.
- Not covered: `--location` and `--weeks` CLI flags, a single-report run with a CLI theme,
  `demo_run.py`, `api.py` job endpoints, and failure paths (Planning Center down,
  parent lookup failing).

---

## 1. Decisions

### Product
- **Name:** "Advanced Reports for Planning Center". Never "Planning Center Advanced
  Reports", which reads as an official Planning Center product.
- **Form:** a **connected app** (Planning Center OAuth). Org admins can see and
  disconnect it under Planning Center **Account Settings → Integrations**. Later, apply
  to the Planning Center integrations directory.
- **Vision:** a platform with **modules**, not just check-in PDFs. Check-In Reports is
  module #1. Planned modules (§4): Google Sheets sync, Bus/Van Route Builder, Grade
  Promotion Helper, follow-up lists, cross-product insights.
- **Setup wizard for churches** is a hard requirement. Every church-facing setting is
  chosen in the dashboard from their real Planning Center data (dropdowns, not typing IDs).
- **Works for any ministry setup:** bus routes, Sunday school, children's church,
  nursery, any combination, or only one. Nothing church-specific lives in code.
- **Official APIs only.** `promote_checkins.py` and `backfill_bus_class.py` use Planning
  Center's internal endpoint with a session cookie and CSRF token. They **stay out of
  the product** and remain IBL-only legacy tools. See §4.4 for what the product does
  about grade promotion instead.

### Platform and stack
- **Google Cloud.** It makes Google Drive, Sheets and Maps integration easiest.
  Region **`us-central1`** (free tiers apply there).
- **Language strategy, two tracks:**
  - **Now (Milestones 1–2):** keep the **Python** engine, refactored for many churches.
    The platform backend is Python (FastAPI) too, reusing the engine.
  - **Then (Milestone 4):** a **Rust report engine using Typst** for PDF rendering,
    built only if benchmarks justify it (gate in §5.3). Golden tests are the parity spec.
  - Why not Rust first: the current job's time is spent waiting on Planning Center.
    _Corrected 2026-11-14 after measuring (`docs/benchmarks.md`):_ it is not the rate
    limit (100 requests / 20 s; we pace at 80 / 20 s in `pco_client.py`), which never
    engaged. It is 134 requests made one after another at about 0.4 s each: 94% of a
    57.7 s run. A faster language makes the same calls and waits just as long. **The
    real speed win is the synced data store (§3.3)**, which cuts API calls per run. Once
    runs stop waiting on the API, rendering becomes a larger share and Rust's gains
    become measurable; today rendering is 5% of the run.
- **Modular monolith, not microservices.** One web service, one runner job, one
  database. Modules plug into a shared core (§3.1).

### Data
- **Decision reversed (2026-11-14): we now store people data**, because fast reports,
  live previews, route building and Sheets sync need it. Constraints:
  - **Only relevant people**, never the whole Planning Center database (IBL has 6,000+
    profiles). "Relevant" is defined in §3.3.
  - **Stay inside Google Cloud free tiers.** Size and read budgets in §3.4.
  - **Encrypted at rest** with a per-church key (§3.5).
  - **Deleted completely** when a church disconnects, and on request.
  - An honest privacy page saying exactly what is stored, why, and for how long.
- PDFs still go to each church's own Google Drive.

### Ownership and money
- **Owner:** Mannabyte Labs LLC. IBL and the developer both consent. Code license stays MIT.
- **IBL and Liberty Baptist are "founding churches": free forever,** for testing and feedback.
- **Pricing after public launch** (design for it, don't build yet): a generous free plan
  sized for a small church; a flat yearly paid plan above it (roughly $20–50/year, not
  final; metered billing rejected because amounts fall below Stripe's fees); an optional
  "Support the project" link (not "donation": payments to an LLC aren't tax-deductible);
  free to self-host.
- **Cost control from day one:** per-church usage counters and limits; a global monthly
  spend cap that sends new free signups to a waitlist; budget alerts on every project.

### Accounts (owner sets these up)
- **Domain:** `reports.mannabyte.com` (not final). Not a subdomain of iblibertad.org.
- **Email:** Google Workspace on mannabyte.com, aliases `hello@`, `support@`, `admin@`. ✅ Done.
- **Google Cloud:** new organization under mannabyte.com; projects **staging** and
  **production**; billing to the LLC; budget alerts. **IBL's project is not transferred.**
- **Planning Center:** a free account for **Mannabyte Labs** owns the OAuth app and
  doubles as a **test church with fake data**. Never register the app under IBL's account.

### Schedule
- **IBL switches to the new platform Sunday night, 2026-11-15**, with the old job paused
  (not deleted) as a fallback. The owner accepts this risk: rosters for 2026-11-15 are
  already printed, and next Sunday's are generated Monday morning, leaving a week to fix
  problems or re-enable the old job.
- The rest of the old Dec–Mar timeline is compressed into weeks (§6).

---

## 2. Where the code is today (single-church assumptions)

Engine is small: about 3,000 lines in `backend/planning_center_reports/` (largest files:
`pco_client.py` 541, `pdf/layout.py` 534, `roster_data.py` 416, `reports.py` 350,
`services.py` 335). PDFs are rendered with **reportlab**; tests extract text with **pypdf**.
Line numbers are as of v0.2.0 (commit `668ce43`).

| Location | Current behaviour | Problem for multiple churches |
|---|---|---|
| `backend/planning_center_reports/config.py` | `load_dotenv()` at import; `PCO_APP_ID`, `PCO_SECRET`, `GOOGLE_DRIVE_PARENT_FOLDER_ID`, `CHURCH_TIMEZONE`, `CHECKIN_VIDEO_URL`, `FEEDBACK_FORM_URL`, `CHECKIN_HELP_CONTACT`, etc. are module globals with IBL defaults; `_theme` is a mutable global read by `T()` | One church's settings and theme apply to the whole process |
| `pco_client.py:36` | `_auth = HTTPBasicAuth(PCO_APP_ID, PCO_SECRET)` built at import (Personal Access Token) | One church's credentials; no OAuth bearer tokens |
| `pco_client.py:45,53` | Module-level `_person_cache` and `_request_times` | Cached people and rate-limit state shared across churches: data could leak between them |
| `reports.py:250` | `_cache` holds the one parsed `reports.yaml` | Only one set of reports |
| `drive_client.py` | Service-account key (`credentials.json`) with the full `drive` scope | Each church would share a folder with our service account by hand; scope too broad |
| `services.py` | `RunContext` takes timezone from the global; `run_all()` mutates `config._theme` | Must receive church config explicitly |
| `pdf/*.py` | About 70 hardcoded Spanish strings (`MESES_ES`, "Lista", "Hace tiempo que no viene", "Resumen", "Maestros y ayudantes", "Padre/Tutor", "Nuevo este domingo", "Falta información", …). `instructions.py` bundles the Spanish guide plus `assets/guides/check-in-guide-en.pdf` | English-only churches get Spanish PDFs |
| `backend/api.py` `/api/settings` | GET returns `PCO_SECRET` to the browser; PUT writes `.env` inside the container | Secret leaks to the browser; settings lost on restart |
| `backend/api.py` `_jobs` + `_run_subprocess` | In-memory job dict; reports run as subprocesses of the web server | Lost on restart; no per-church separation |
| `backend/api.py` `_verify_google_token` | Google sign-in; blank `ALLOWED_GOOGLE_DOMAINS` means any Google account | Fails open; wrong identity provider for this product |
| `frontend/src/i18n/translations.ts:131` | Footer hardcodes "Iglesia Bautista Libertad" | Church name must come from settings |

Works in our favour: `ReportSpec` (`reports.py`) is config-driven and validated;
`RunContext` is already a per-run cache; `pco_client._get()` paces, honours
`Retry-After` and retries; tests exist (`backend/tests/`, PDF text checks in
`test_pdfs.py` using `mock_data`); rosters fetch check-ins with `include=person`.

---

## 3. Target architecture

### 3.1 Shape

```
                       ┌───────────────────────────────────────────────┐
 Church admin ─HTTPS──▶│ Firebase Hosting: React dashboard + wizard    │
 (browser)             │   /api/** rewritten to the Cloud Run service  │
                       └───────────────────────┬───────────────────────┘
                                               ▼
                       ┌───────────────────────────────────────────────┐
                       │ Web service (Cloud Run, FastAPI)              │
                       │  core: auth (PCO OAuth), TenantRepo, wizard,  │
                       │        connections, runs, files, usage        │
                       │  modules: checkin_reports, sheets_sync,       │
                       │           routes, grade_helper, ...           │
                       └──────┬────────────────────────┬───────────────┘
                              │ settings, tokens,      │ start execution
                              │ synced data            ▼ (CHURCH_ID, RUN_ID)
                ┌─────────────▼────────────┐   ┌──────────────────────────────┐
                │ Firestore                │◀──│ Runner (Cloud Run job)       │
                │ settings · encrypted     │   │ one execution = one church   │
                │ tokens · run history ·   │   │ 1. sync (incremental)        │
                │ usage · encrypted synced │   │ 2. render modules' outputs   │
                │ data chunks              │   │ 3. deliver (Drive/Sheets/GCS)│
                └──────────────────────────┘   └──────────────────────────────┘
 Cloud Scheduler ─(hourly, OIDC)─▶ /internal/dispatch: starts due runs
 Secret Manager: master key that wraps each church's data key; OAuth client secrets
```

- **Frontend on Firebase Hosting** (free tier, easy custom domain, rewrites `/api/**` to
  Cloud Run). This avoids Cloud Run domain mappings, which have regional limits.
- **Core** owns tenancy, auth, connections, scheduling, runs, delivery, usage limits.
- **A module** declares: the data it needs synced, its settings schema (which drives the
  wizard UI), and its outputs (PDFs, Sheets tabs, route sheets). Adding a capability means
  adding a module, not changing the core.

### 3.2 Repository layout (proposal)

```
backend/
  planning_center_reports/   # existing engine, refactored (Phase 1); legacy job keeps using it
  advanced_reports/          # new platform
    app.py                   # FastAPI app factory
    core/                    # auth.py, session.py, tenant_repo.py, crypto.py, usage.py,
                             # connections/{pco.py,google.py}, runs.py, dispatch.py
    sync/                    # relevant-people sync into the data store (§3.3)
    modules/
      checkin_reports/       # wraps the engine
      sheets_sync/
      routes/
      grade_helper/
    runner.py                # Cloud Run job entrypoint
    importers/ibl.py         # one-off: reports.yaml + .env → Firestore settings
  tests/
    golden/                  # Phase 0 snapshots
    platform/                # two-church isolation tests, etc.
  bench/                     # benchmark harness (§5)
Dockerfile                   # unchanged: legacy job only
Dockerfile.app               # new: web service + runner (same image, different command)
firebase.json                # hosting + rewrites
scripts/setup_mannabyte_gcp.sh   # gcloud commands for owner setup (no Terraform: keep it simple)
```

### 3.3 The synced data store ("relevant people only")

**Relevant people** for a church are:
1. Anyone checked in to a **configured event** within the church's history window
   (school-year start date, or N weeks; capped by plan, default 52 weeks), as attendee
   or worker.
2. The **guardians** of those people (household adults), only the fields reports use.
3. People a module explicitly adds (e.g. route stops) and nobody else.

People who fall out of the window are deleted from the store at the next sync.

**What is stored** (only fields some report or module uses): name, birthday/grade, gender
if a report uses it, primary phone/email/address, household links, check-in rows
(person, event period, location, kind attendee/worker, time).

**Sync strategy, v1 (pull, incremental):**
- First sync per event: backfill the window (the same calls today's job makes once).
- Later syncs: fetch only **new event periods**, plus re-fetch the **last 2 periods**
  (check-ins can be edited on the day). Older periods are treated as final.
- Refresh person details only for relevant people, using `where[updated_at]` filters if
  the People API supports them (verify, §8), otherwise batch fetches of relevant IDs.
- **Expected result:** API requests per weekly run drop from "whole history window" to
  "one or two periods". This is the key number to measure (§5).

**v2 (later):** Planning Center **webhooks** to mark data dirty between runs (verify
which Check-Ins and People events exist, §8).

### 3.4 Free-tier budget (estimates; verify current pricing pages)

Free-tier figures below are from memory and must be checked against Google's pricing
pages before relying on them (§8).

| Service | Free tier (approx.) | Our expected use |
|---|---|---|
| Firestore (default DB only) | 1 GiB stored; 50k reads, 20k writes, 20k deletes per day | See below |
| Cloud Run | ~2M requests, ~180k vCPU-s, ~360k GiB-s per month (billing account) | Dashboard traffic plus a few minutes of runner time per church per week |
| Cloud Scheduler | 3 jobs per billing account | 1 (hourly dispatch) |
| Secret Manager | ~6 active secret versions, ~10k accesses/month | Master key, OAuth secrets |
| Cloud Storage | ~5 GB-month Standard in us-central1/us-east1/us-west1 | Optional 30-day PDF copies |
| Firebase Hosting | ~10 GB stored, ~360 MB/day transfer | Static dashboard |
| Google Maps Platform | Monthly free usage per SKU (amounts vary by SKU) | Route Builder only; per-church limits |

**Size estimate per church per year** (IBL-sized: assume ~600 check-ins/week):
- Check-in rows: 600 × 52 ≈ 31k rows × ~60 bytes compact ≈ **2 MB**.
- People + guardians: ~1,500 × ~400 bytes ≈ **0.6 MB**.
- About **3 MB per church per year**, so 1 GiB holds roughly 300 IBL-sized churches.

**Read budget: the critical design rule.** One Firestore document per check-in would
cost ~31k reads per report run and blow the 50k/day limit with two churches. So:
- Store data in **compact chunk documents**, not one doc per row:
  `churches/{org}/data/periods/{event_id}_{yyyy}` (all check-ins for an event and year,
  compact arrays) and `churches/{org}/data/people/{chunk_n}` (~500 people per chunk).
  Firestore's document limit is 1 MiB; split a chunk before it reaches ~800 KB.
- A full report run then costs **tens of reads**, not thousands.
- Each chunk is an encrypted, compressed blob (§3.5).

### 3.5 Encryption and deletion
- **Envelope encryption:** each church gets a random 256-bit data key. Chunks and tokens
  are encrypted with AES-GCM (Python `cryptography`) under that key. The church's data key
  is itself encrypted with a **master key stored in Secret Manager** and kept on the
  church doc. Cloud KMS can replace the master key later without re-encrypting the data.
- **Disconnect / delete:** delete `churches/{org}` and every subcollection, plus any
  Cloud Storage objects under `churches/{org}/`. Destroying the data key alone makes
  leftover ciphertext unreadable. Add a test that proves the whole subtree is gone.
- Logs never contain tokens or people's details.

### 3.6 Firestore layout

```
churches/{org_id}                       # org_id = Planning Center organization ID
  name, timezone, language ("en"|"es"), plan ("founding"|"free"|"paid"),
  status ("active"|"needs_reconnect"|"paused"), created_at, wrapped_data_key,
  branding { logo_path, verse_text, verse_ref, help_contact, video_url, feedback_url },
  limits { reports, runs_per_day, history_weeks, maps_calls_month, ... },
  usage { month, runs, pco_requests, pages, maps_calls },   # reset monthly
  schedule { day, time_local, enabled }
churches/{org_id}/connections/pco       # encrypted refresh token, expiry, connected_by, scopes, status
churches/{org_id}/connections/google    # encrypted refresh token, scopes, drive folder id,
                                        # sheets spreadsheet id, connected_by, status
churches/{org_id}/modules/{module_id}   # module settings (e.g. checkin_reports → list of reports)
churches/{org_id}/runs/{run_id}         # trigger, status, started/finished, log, outputs[], usage, timings
churches/{org_id}/members/{person_id}   # role ("admin"), last_login
churches/{org_id}/data/...              # encrypted synced chunks (§3.4); sync cursors
system/limits                           # global monthly spend cap, waitlist on/off
```

### 3.7 Isolation rules (enforced in code, covered by tests)
1. **The church ID always comes from the server-side session**, set from the Planning
   Center token at sign-in. Never from the URL, body or headers.
2. **`TenantRepo(org_id)`** is the only code that touches Firestore or Cloud Storage.
   Every path it builds starts with `churches/{org_id}`. Route handlers never build paths.
3. **Each run is a separate Cloud Run job execution** with a single `CHURCH_ID`. It loads
   only that church's config, key and tokens. No module-level caches.
4. **No church-identifying state in module globals** anywhere in the engine.
5. **Two-fake-church tests** prove every API route rejects cross-church access (read,
   list, update, run, download) and that two runs in one process share no cached data.
6. The browser never sees Planning Center or Google secrets.

---

## 4. Modules

### 4.1 Check-In Reports (module #1, Milestone 1)
Today's rosters, made general. Building blocks, mapped from today's `ReportSpec`:

| Building block | What the admin picks | Today's field(s) |
|---|---|---|
| **Source** | One Check-Ins event (dropdown of their real events) | `pco_event` |
| **Split** | One roster per location/class (default) | implicit |
| **Linked event** (optional) | A second event whose locations become a column (e.g. bus route) | `route_source_event`, `show_route`, `attendance_summary` |
| **Sections** | Active list, "haven't been back recently", workers, summary | `outputs`, inactive split, `default_weeks` |
| **Workers** | Workers in this event, or everyone ≥ age N in another event | `volunteer_report`, `volunteer_event`, `volunteer_min_age`, `volunteer_weeks` |
| **History** | School-year start date, or rolling N weeks | `start_date`, `history_weeks`, `max_history_weeks` |
| **Columns** | Parent contact, phone, address, birthday/age, grade, route, date added | fixed in `pdf/rosters.py` today |
| **Text and look** | Title, subtitle, language, theme, logo, verse, help contact | `label`, `subtitle`, `default_theme`, config globals |
| **Helper pages** | Check-in instructions with each folder | `instructions` |
| **Delivery** | Drive folder (optional subfolder), download page | `drive_folder_prefix`, `GOOGLE_DRIVE_PARENT_FOLDER_ID` |
| **Schedule** | Day and local time | Cloud Scheduler Monday 08:00 UTC today |

**Templates:** Sunday school · Children's church · Bus/van routes · Sunday school with
transportation (linked event) · Nursery. A church with only Sunday school never sees buses.

### 4.2 Google Sheets Sync (Milestone 2)
- With the church's Google connection (`drive.file` scope covers files the app creates;
  verify that Sheets API writes work under it, §8), create one spreadsheet per church
  and update it after every run.
- Tabs (each optional): one roster tab per class; an **attendance grid** (people ×
  Sundays); "haven't been back" list; first-time guests; workers.
- Use cases: staff filtering and sorting, mail merges, sharing a live list with a teacher
  without printing.
- Cost: Sheets API is free within per-project quotas; batch updates (one `batchUpdate`
  per tab per run).

### 4.3 Bus/Van Route Builder (Milestone 3, "the gold mine")
Owner's core idea: **on the day, pick the people from your roster who may ride today and
generate a route.**
- **Flow:** pick a route (a location in the bus/transport event) → see that route's
  riders from the synced store, with checkboxes ("riding today"), pre-checked from
  recent attendance → add one-off stops (new riders, a typed address) → set the start
  and end (default: church address) → **Build route**.
- **Output:**
  - Ordered stop list on screen and as a printable **route sheet PDF** (stop #, names
    at that address, address, guardian phone, notes).
  - A **Google Maps link** for the driver's phone (check the waypoint limit for Maps
    URLs, §8; split into legs if needed).
  - An option to save the order as the route's default.
- **APIs:** Geocoding for addresses (**cache results** on the person record; check
  Google's caching terms, §8), then Routes API `computeRoutes` with
  `optimizeWaypointOrder` (roughly 25 intermediate waypoints max, verify). Larger routes
  split into chunks, or use the paid Route Optimization API later.
- **Cost control:** server-side API key restricted to those APIs; per-church monthly
  Maps call limit in `limits`; usage counted in `usage.maps_calls`.
- Works on a phone (bus captains do this on Sunday morning).

### 4.4 Grade Promotion Helper (Milestone 3)
**Constraint the owner should know:** the real pain at IBL is **Check-Ins pre-select
history**. Pre-select suggests the last location a child checked into, overriding
grade filters, and only check-in history changes it. The public Check-Ins API is
read-only, so **the official API can't rewrite that history**. That's why
`promote_checkins.py` uses the internal endpoint, and why it stays out of the product.

What the product can do with official APIs:
1. **Promotion audit report:** for each child, compare their People `grade` to the
   grade range of the class they last checked into, and list mismatches ("Ana is now in
   3rd grade but still checks into 2nd Grade").
2. **Setup guidance in the wizard:** explain pre-select versus grade/age filters, and
   walk the church through switching classes to filters, after which Planning Center's
   built-in **People → Promote grades** handles promotion properly.
3. **Bulk grade correction** through the People API, if `grade` is writable with the
   OAuth scope (verify on the test church first, §8). This would need write access,
   which raises the trust bar; make it opt-in.
4. **Ask Planning Center** (developer support) for an official way to reset pre-select.

### 4.5 Later modules (Milestone 5+)
- **Follow-up:** absentee lists sent to each teacher automatically; first, second and
  third visit guest tracking; a simple "contacted" tracker.
- **Cross-product insights:** Check-Ins + Groups + Services (+ Giving only with great
  care), e.g. "attends but in no group", "serves but stopped attending".
- **Trends:** year-over-year attendance, guest retention, staff-to-child ratios per room.

---

## 5. Measurement (the Rust justification)

The owner wants **real, measurable results** before committing to Rust, and numbers to
show for the work. Every milestone records results in **`docs/benchmarks.md`**, with
date, commit, machine and method.

### 5.1 Metrics
| Metric | How to measure |
|---|---|
| End-to-end run time per church | Runner logs start/finish timestamps per stage (sync, render, deliver) into `runs/{id}.timings` |
| Planning Center API requests per run | Counter inside `PcoClient` (count, retries, 429s, time spent waiting on the rate limiter) |
| Render time per PDF and per page | `backend/bench/render_bench.py`: render each PDF type from scaled mock data N times; report median and p95 |
| Peak memory | `resource.getrusage` / `/usr/bin/time -v` around the render bench |
| Container image size, cold start | `docker images`; time from execution start to first log line |
| Firestore reads/writes per run | Counter inside `TenantRepo` |
| Cost per church per month | Derived from the above and pricing pages |

### 5.2 Baselines to capture in Milestone 1
1. **Production baseline:** the last several `roster-weekly` executions in IBL's project
   (`gcloud run jobs executions list --job roster-weekly --project
   ibl-planning-center-check-ins --region <region>`; read durations from the execution
   details and logs). Ask the owner to run it if we lack access.
2. **Local baseline:** add the API request counter, run `main.py --all --dry-run`
   against IBL with the current engine, and record request count, wait time and total time.
3. **Render baseline:** `bench/render_bench.py` on mock data scaled to IBL size
   (and 5× IBL) with reportlab.

Then after the sync store (Milestone 2), re-measure API requests and run time. **That
before/after is the first headline number.**

### 5.3 Rust gate (Milestone 4)
Build a **spike** first: one roster type rendered by a Rust binary using Typst, from the
same JSON input the Python renderer gets. Proceed to a full Rust engine only if:
- per-page render time is **at least 5× faster** than reportlab (median, same input), **and**
- golden-test text parity is achievable for that roster, **and**
- after the sync store, rendering is a meaningful share of total run time (if runs are
  still mostly network-bound, say so plainly in `docs/benchmarks.md`).

If the gate fails, record why and keep Python. Either result is a real, reportable finding.

**Integration shape if it passes:** a standalone `report-renderer` Rust binary (JSON in,
PDFs out) called by the runner. It's language-neutral, easy to benchmark, and can replace
one report type at a time. PyO3 bindings are the alternative if process overhead matters.

---

## 6. Milestones (compressed timeline)

Keep IBL's `roster-weekly` job deployable until Milestone 2 is done. **Pause** its Cloud
Scheduler trigger at cutover; don't delete anything.

### Milestone 1: IBL on the new platform (Sat 11-14 → Sun 11-15 night)
1. **Golden tests (Phase 0).**
   - `backend/tests/golden/`: render every PDF type (roster with and without route
     column and attendance summary, inactive section, workers, volunteer report,
     instructions bundle, every theme) from `mock_data` with a fixed "today" and IBL's
     default settings.
   - Snapshot extracted text per page (pypdf), page counts, output filenames and Drive
     folder paths. Not raw bytes, which contain timestamps.
   - Compare fresh renders to snapshots; refresh only with `pytest --update-golden`
     (or an env var).
   - Snapshot `parse_reports()` output for `reports.yaml.example` and IBL's
     `reports.yaml` shape (don't commit private values).
   - Done when golden tests pass on the branch, and any change to IBL's PDF text,
     structure or filenames makes them fail.
2. **Benchmark baseline** (§5.2): API counter, `bench/render_bench.py`, `docs/benchmarks.md`.
3. **Engine refactor (Phase 1), no IBL output change:**
   - `ChurchConfig` dataclass (`planning_center_reports/church.py`): org id, name,
     timezone, language, theme, branding, Drive parent folder, `reports: tuple[ReportSpec, ...]`.
   - `PcoClient` class replacing module functions: auth strategy (Personal Access Token
     for legacy, OAuth bearer with a refresh callback), its own person cache, rate-limit
     window and request counter.
   - Remove module-global state: the theme is passed to PDF functions or a render
     context; `reports._cache` and import-time `load_dotenv` live only in the legacy adapter.
   - `RunContext(church, pco, delivery, …)`; timezone from the church.
   - `Delivery` interface: `DriveServiceAccountDelivery` (legacy), `DriveOAuthDelivery`
     (`drive.file`), `LocalDelivery` (tests and dry run); fan-out to several.
   - PDF text catalogs (`planning_center_reports/i18n/es.py`, `en.py`): move the
     hardcoded Spanish strings and `MESES_ES`; select by `church.language`. Spanish must
     be exact (golden tests). English can be a first pass now and polished before Liberty.
   - Legacy adapter `planning_center_reports/legacy.py`: builds `ChurchConfig` from
     `.env` and `reports.yaml` so `main.py`, `cli.py` and the old Cloud Run job behave
     exactly as before.
   - Two-church test: two churches with different mock data back to back in one process;
     no people, cache or theme crossover.
   - Done when golden tests pass unchanged, `ruff` and the full suite pass, and no church
     settings are read from module globals outside `legacy.py`.
4. **Platform core (minimum for IBL):**
   - Planning Center OAuth sign-in (authorization code + state; PKCE if supported),
     require org admin (verify how, §8), create the church on first sign-in, signed
     HTTP-only session cookie.
   - `TenantRepo`, envelope encryption (§3.5), token refresh, `needs_reconnect` status.
   - Google connection with `drive.file`. **MVP shortcut:** the app creates its own
     "Advanced Reports" parent folder in the admin's Drive instead of a Google Picker
     (the Picker comes in Milestone 2).
   - Routes: `GET /api/me`, `GET/PUT /api/church`, `GET /api/pco/events`,
     `GET /api/pco/events/{id}/locations`, `GET/PUT /api/modules/checkin_reports`,
     `POST /api/runs`, `GET /api/runs`, `GET /api/runs/{id}`, `POST /api/disconnect`.
   - Runner job (`advanced_reports/runner.py`): one church per execution; writes status,
     log, timings and usage. **For Milestone 1 it calls the engine directly with live
     Planning Center data** (no sync store yet).
   - `POST /internal/dispatch` (OIDC-only) called hourly by Cloud Scheduler; starts due
     runs; a Firestore lock allows one active run per church.
   - **IBL importer** (`importers/ibl.py`, run by the owner once): `reports.yaml` +
     `.env` values → IBL's Firestore settings (language `es`, IBL branding, schedule).
5. **Minimal dashboard:** sign in → connect Google → (IBL: imported settings shown
   read-only, or a template picker for others) → Run now → run history with status and
   links to Drive. Church name from settings; remove the hardcoded footer. English and
   Spanish UI. Polishing comes later.
6. **Deploy to staging** against the Mannabyte test church, then **production**.
7. **Cutover (Sunday night):**
   - IBL's admin signs in on production, connects Google; the owner runs the importer.
   - **Run now** once; compare the PDFs' text with the old job's latest output (a
     script reusing the golden-test text extraction).
   - **Decide with the owner:** new PDFs go to a **fresh Drive folder**. With
     `drive.file`, the app can't see files the old service account created. Tell
     teachers where the new folder is, or move/remove the old files.
   - Pause the `roster-weekly` Cloud Scheduler trigger in IBL's project. **Don't delete it.**
   - Watch the first scheduled run (Monday). If it fails: re-enable the old trigger,
     then fix.

### Milestone 2: fast and synced (week of 11-16 → 11-22)
- Sync store (§3.3–3.5) with the read-budget design; runner renders from the store.
- Re-measure; record the API-requests and run-time before/after in `docs/benchmarks.md`.
- **Live preview** in the wizard from synced data.
- **Google Sheets Sync** module (§4.2).
- Google Picker for folder choice; failure emails (transactional email service).
- Security hardening: two-church route tests for every route, session forgery/expiry
  tests, CSRF protection, `/internal/*` OIDC checks, log scrubbing.
- Privacy and terms pages (now covering stored data).
- After two good Monday runs, the owner may retire IBL's old job (a month later IBL can
  shut down that project).

### Milestone 3: routes and grades (11-23 → 12-06)
- **Bus/Van Route Builder** (§4.3), phone-friendly.
- **Grade Promotion Helper** (§4.4): audit report first, then wizard guidance, then
  opt-in bulk grade correction if the API allows it.
- Full wizard flow with templates and event matching.

### Milestone 4: Rust/Typst spike and Liberty (12-07 → 12-20)
- Rust spike and gate (§5.3); full engine only if the gate passes.
- **Liberty Baptist onboarding:** their admin sets up while the developer watches; note
  every confusion and fix it. English, their ministries only. Guest flow on paper:
  printed rosters include blank guest rows; the office enters guests during the week.

### Milestone 5: public launch (January 2027)
- Setup guide with screenshots, short video; Planning Center community post;
  integrations directory application.
- Follow-up module, then insights.
- Plans and Stripe only once usage justifies it.

The developer leaves IBL around May 2027. By then, nothing should depend on them except
maintaining the product.

---

## 7. Owner setup steps (manual, by Milestone 1 step 6)

1. **Google Cloud:** organization under mannabyte.com; projects `…-staging` and
   `…-prod`; billing account (LLC card); budget alerts (e.g. $5 and $20) on both. Enable:
   Cloud Run, Firestore (Native mode, `us-central1`), Cloud Scheduler, Secret Manager,
   Artifact Registry, Cloud Build, IAM Credentials, Drive API, Sheets API, Picker API,
   (later) Geocoding and Routes APIs. Add Firebase to both projects for Hosting.
   `scripts/setup_mannabyte_gcp.sh` should script everything after org/billing creation.
2. **Planning Center:** free account for Mannabyte Labs; register the OAuth app at
   `api.planningcenteronline.com/oauth/applications` with redirect URIs for
   `http://localhost:8000/auth/pco/callback`, staging and production; seed a fake test
   church (events, locations, households, a linked "bus" event).
3. **Google OAuth client** (web) in each project. Consent screen branded "Advanced
   Reports for Planning Center", support email `support@mannabyte.com`, scope
   `drive.file`. **Gotcha:** while the consent screen is in "Testing" status, refresh
   tokens expire after 7 days, which would break weekly runs. Set it to "In production"
   (non-sensitive scopes like `drive.file` shouldn't need full verification; verify, §8).
   Verify mannabyte.com in Google Search Console.
4. **DNS:** `reports.mannabyte.com` → Firebase Hosting (production).
5. **Email Planning Center developer support:** may a hosted app charge churches; naming;
   official way to reset Check-Ins pre-select (§4.4).

---

## 8. Open questions to verify (don't assume)

- **Planning Center OAuth:** exact scope names (`check_ins`, `people`); access and
  refresh token lifetimes; PKCE support; how to detect an org admin; whether rate limits
  apply per app, user or org under OAuth; whether any org can use the app before
  directory listing.
- **Planning Center terms:** storing synced data in a third-party app; charging churches.
- **People API:** `where[updated_at]` filtering for incremental sync; whether `grade` is
  writable with the OAuth scope.
- **Webhooks:** which Check-Ins and People events are available.
- **Google:** `drive.file` covers Sheets the app creates and folders picked through the
  Picker (subfolders and files inside); consent screen production status for
  non-sensitive scopes.
- **Cloud Run jobs:** per-execution environment overrides when started from the API
  (believed supported via `RunJob` overrides; confirm).
- **Free-tier numbers in §3.4:** check every figure against current pricing pages.
- **Maps:** free usage per SKU after the 2025 pricing change; `optimizeWaypointOrder`
  SKU and waypoint limit; Maps URLs waypoint limit on mobile; caching rules for
  geocoding results.
- Does anyone at IBL use the legacy web UI, or only the weekly job?
- The owner mentioned "lots of inaccuracies" in an earlier planning doc and said "our
  websites were supposed to be deprecated". Neither was fully clarified.

## 9. Blockers to ask the owner about first

1. Do the Google Cloud org, staging/production projects and billing exist yet?
2. Does the Mannabyte Planning Center account exist, with the OAuth app registered?
   (Client ID/secret go into Secret Manager, never into the repo.)
3. Google OAuth client and consent screen: done?
4. Access to IBL's GCP project for the production baseline (§5.2), or will the owner run
   the `gcloud` commands?
5. Cutover Drive folder: fresh folder (recommended) or clean up old files?

---

## 10. Non-goals and constraints

- No check-in creation or editing (the public Check-Ins API doesn't allow it). No
  cookie or CSRF scripts in the product.
- No storing people beyond "relevant people" (§3.3); no fields no report uses.
- No AI or photo intake for now.
- No microservices, no Terraform, no Kubernetes. Simple beats clever.
- The repo owner handles all commits and PRs.
- No copyright notices in the UI. Open source (MIT).
- The existing `Dockerfile` stays backend-only for the legacy job.
- Never change IBL's output without a deliberate golden-test update.
