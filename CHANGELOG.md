# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

> **Note:** Versions v0.0.1 through v0.0.11 are internal production releases predating the open-source
> launch of this project. They are preserved here for historical context. The public open-source release
> begins with v0.1.0.

---

## [Unreleased]

### Security

- Removed `.env` from git tracking — it was accidentally committed from the first commit. `.env.example`
  with obvious placeholder values now serves as the setup template.
- Removed `COPY credentials.json` from both `Dockerfile` and `Dockerfile.api` — Google service account
  keys are no longer baked into Docker images. Credentials must now be supplied at runtime via a mounted
  secret or Secret Manager (see `SECURITY.md` for Cloud Run instructions).
- Added `SECURITY.md` — documents the vulnerability reporting process, sensitive data policy, and
  credential rotation steps for Planning Center, Google service accounts, and Google OAuth.

---

## [v0.0.11] — 2026-05-21

### Added

**Authentication — Google OAuth**

- Login overlay (`LoginOverlay.tsx`) shown to unauthenticated users — full-screen
  card with a "Sign in with Google" button powered by `@react-oauth/google`.
- `AuthContext.tsx` — React context holding the Google ID token credential;
  provides `login` / `logout` and an `authRequired` flag derived from whether
  `GOOGLE_CLIENT_ID` is configured.
- `App.tsx` fetches `GET /api/auth/config` on startup to retrieve the client ID,
  then conditionally gates the entire dashboard behind the login overlay.
- `api/client.ts` — `setAuthToken()` setter; every `apiFetch` call automatically
  includes `Authorization: Bearer <token>` when a credential is stored.
- `backend/api.py` — `_verify_google_token()` FastAPI dependency that verifies the
  Google ID token and checks the email domain against `ALLOWED_DOMAINS =
  {"iblibertad.org", "iblibertad.com"}`. Returns 401 for missing/invalid tokens,
  403 for disallowed domains.
- `GET /api/auth/config` public endpoint — returns `{"google_client_id": "..."}` so
  the frontend can bootstrap `GoogleOAuthProvider` at runtime.
- All `/api/*` routes except `/api/health` and `/api/auth/config` now require a
  valid Google token via `Depends(_verify_google_token)`.
- Auth is automatically disabled (bypassed) when `GOOGLE_CLIENT_ID` env var is not
  set — local development continues to work without OAuth.
- `manage.sh` option 16 — reads `GOOGLE_CLIENT_ID` from `.env` and passes it to
  `gcloud run deploy` as `--set-env-vars`; prompts the user if the value is missing.

**Tests**

- `TestAuth` (10 backend tests) — covers `/api/auth/config`, auth bypass when client
  ID is unset, 401 for missing/invalid/malformed tokens, 403 for disallowed domains,
  200 for `iblibertad.org` and `iblibertad.com` accounts, and health always public.
- `LoginOverlay.test.tsx` (5 frontend tests) — covers title, subtitle, domain hint,
  Google button render, and `login()` called with the credential on success.
- Backend total: **185 tests**. Frontend total: **74 tests**.

---

## [v0.0.10] - 2026-05-21

## Added

**Cloud deployment — web UI + API service**

- `Dockerfile.api` — Cloud Run Service image: installs `requirements.txt` +
  `requirements-web.txt`, copies the built React SPA (`backend/static/`) and
  `credentials.json`, runs `uvicorn api:app` on port 8080.
- `cloudbuild-api.yaml` — Cloud Build config that builds and pushes
  `roster-api:latest` to Artifact Registry using `Dockerfile.api`.
- `manage.sh` options 16–19 — **API SERVICE** section:
  - `16` Deploy / redeploy API service (builds frontend, submits to Cloud Build, runs `gcloud run deploy`)
  - `17` Print the Cloud Run service URL
  - `18` Stream API service logs
  - `19` Open the web UI in a browser
- `API_IMAGE` and `API_SERVICE_NAME` variables added to `manage.sh`.

**Backend (`api.py`)**

- `_get_allowed_origins()` — reads `ALLOWED_ORIGINS` env var (comma-separated);
  falls back to `localhost:5173` / `localhost:3000` for local dev. Used by
  `CORSMiddleware` instead of a hardcoded list.
- Auth placeholder comment block in `api.py` documenting the Cloud IAP steps
  needed to restrict access to specific Google accounts in the future.
- Auth TODO comment in `Dockerfile.api` pointing to the Secret Manager migration
  once IAP is in place.

**Tests**

- `TestGetAllowedOrigins` (5 tests) — covers env-unset, empty-string, single
  origin, multiple origins, and whitespace-stripping behaviour.
- `TestCORSHeaders` (2 tests) — verifies `access-control-allow-origin` is
  present for allowed origins and absent for disallowed ones.
- Backend total: **175 tests** (up from 168).

**Docs**

- `DEVELOPMENT.md` — "Deploying the API Service" subsection added under
  "Deploying code to Google Cloud", covering first-time deploy, subsequent
  deploys, URL retrieval, logs, and `ALLOWED_ORIGINS` configuration.

---

## [v0.0.9] — 2026-05-19

### Added

**Web UI**

- **Settings modal** — editable form for PCO credentials (`PCO_APP_ID`, `PCO_SECRET`),
  Google Drive folder ID, and per-job defaults (weeks, campaign theme) for both Rutas and
  Escuela Dominical. Changes are persisted to the `.env` file immediately.
- **Logs modal** — displays all in-session jobs newest-first as expandable cards showing
  type, status badge, relative time, duration, and collapsible terminal output. Refresh
  button re-fetches the list.
- **Settings and Logs tiles** activated on the dashboard (previously "Coming Soon").

**Backend API (`api.py`)**

- `GET /api/settings` — returns all editable settings from env / `.env` file.
- `PUT /api/settings` — persists setting changes to `.env` and updates the live process env.
- `GET /api/jobs` — lists all in-session jobs sorted newest-first.
- `POST /api/jobs/rutas/run` and `POST /api/jobs/escuela/run` now pass `--weeks` and
  `--theme` flags to `main.py`, reading defaults from `RUTAS_DEFAULT_WEEKS`,
  `RUTAS_DEFAULT_THEME`, `ESCUELA_DEFAULT_WEEKS`, `ESCUELA_DEFAULT_THEME` env vars
  (all default to sane values when unset).
- `.env` read/write helpers (`_read_dotenv`, `_write_dotenv`) with line-preserving update logic.

**Internationalisation**

- Added translation keys for all five season theme tabs (`preview.theme.*`) and three PDF
  type buttons (`preview.type.*`) in the Preview modal — previously hardcoded English strings.
- Added translation keys for the Settings modal (sections, field labels, save states) and
  Logs modal (title, job type labels, empty/output strings) in both Spanish and English.

**Tests**

- `backend/tests/test_api.py` — 47 new backend tests covering all API endpoints, the
  `.env` helpers, job store behaviour, run-job flag construction, settings read/write, and
  edge cases. Backend total: **168 tests**.
- `frontend/src/components/__tests__/` — full React component test suite using
  **Vitest 4 + Testing Library** (jsdom environment). Tests for Footer, Navbar, StatusBadge,
  TileCard, HomePage, PreviewModal, JobModal, SettingsModal, and LogsModal.
  Frontend total: **69 tests**.
- `frontend/vitest.config.ts` and `frontend/src/test/setup.ts` — test runner configuration.
- Added `npm test` / `npm run test:watch` scripts to `frontend/package.json`.
- Added `httpx` to `backend/requirements-dev.txt` (required by FastAPI's `TestClient`).

### Changed

- **PDF Preview modal** enlarged: max-width `920 px → 1400 px`, max-height `90 vh → 95 vh`,
  overlay padding `16 px → 8 px` so the viewer takes up much more of the screen.
- **Footer** — copyright line (`© year … All rights reserved.`) removed; this is an open
  source project.

---

## [v0.0.8] — 2026-05-05

Codebase split into `backend/` and `frontend/` directories. Experimental web UI
added for testing — the Cloud Run pipeline and `manage.sh` workflow are
unchanged for production use.

### Changed

- All Python source moved to `backend/` (`planning_center_reports/`, `tests/`,
  `assets/`, `previews/`, `main.py`, `preview.py`, and supporting files).
- `Dockerfile` updated to reference `backend/` paths; still builds a Python-only
  Cloud Run job image — no frontend included.
- `backend/requirements.txt` reverted to core deps only (no FastAPI/uvicorn).
- `backend/requirements-web.txt` added for the optional API server.
- `manage.sh` option 6 path check updated for the new layout.
- CI workflow split into separate `backend` and `frontend` jobs.

### Added

- `backend/api.py` — FastAPI server for the web UI (local / future hosting).
  Provides `GET /api/previews`, `POST /api/previews/generate`, job run and poll
  endpoints. Not used by or required for the Cloud Run jobs.
- `frontend/` — React + TypeScript (Vite) web UI for testing. Spanish/English
  toggle, dashboard tile grid, PDF preview viewer, live job output. Work in
  progress; not yet in production.

---

## [v0.0.7] — 2026-05-05

### Added

- **Escuela Dominical roster improvements**
  - New **Ruta column** replaces the Asistencia column — shows only the route number (e.g. `1`, `2`) instead of the full route name. Implemented via `_extract_route_number()` in `models.py`.
  - **Attendance summary tables** printed below the attendee list on each roster: a per-Sunday table (Domingo | Regular | Visitantes | Total) and a per-route headcount table (Ruta | Presentes). Driven by `_draw_escuela_summary()` in `pdf/layout.py` and `escuela_summary_height()` for page-break decisions.
  - `generate_simple_roster_pdf` accepts a new `show_route` flag and optional `sunday_data` list for the summary.
- **`ED_COL_WIDTHS` / `ED_HEADERS`** constants in `config.py` for the wider Escuela Dominical column layout.
- **`MESES_ABREV`** Spanish month abbreviation map in `config.py`.
- **`get_helpers_set()`** in `pco_client.py` — fetches person IDs (age ≥ 16) who checked into *Junta de Rutas Attendance*, used to identify bus workers.
- **`_get_route_mapping()`** in `services.py` — builds a `person_id → route_name` map from Rutas check-ins, used to populate the Ruta column in Escuela Dominical rosters.
- **`_build_sunday_data()`** in `services.py` — counts per-Sunday regular and visitor attendees for one class location. Visitor status is evaluated **per Sunday** using each person's `created_at` and the period's `starts_at`, not against today's date.
- **`_is_visitor_for_period()`** in `models.py` — returns `True` if a person was added to PCO within 7 days before a given event period.
- **`_format_period_date()`** in `pco_client.py` — formats a PCO `starts_at` ISO string into a short Spanish label (e.g. `"Abr 6"`).
- **Rate-limit retry** added to `get_checkins_for_event_periods()` — the paginator now retries up to 7 times with exponential back-off on HTTP 429 and network errors, matching the behaviour of `get_person_details`.
- **`preview.py` Escuela Dominical preview** — `--type escuela` (included in the default `all`) generates `*_Escuela-Roster.pdf` with mock Sunday summary data and a helper attendee to exercise all new code paths.
- **Test suite expanded** — 30 new tests in `tests/test_escuela_dominical.py` covering `_extract_route_number`, `_is_visitor_for_period`, `_format_period_date`, `_build_sunday_data` (including per-period visitor determination), `escuela_summary_height`, and `generate_simple_roster_pdf` with Escuela Dominical flags. Additional tests in `test_helpers_and_routes.py` verify helper route suppression and roster inclusion.

### Changed

- **`get_recent_event_periods()`** now returns a 3-tuple `(period_ids, period_dates, period_starts_at)`. The new third element maps each period ID to its raw ISO `starts_at` string, used for per-Sunday visitor calculations.
- **Bus workers (helpers) remain on the Escuela Dominical roster** — previously they were filtered out; now they appear on the list with a blank Ruta cell. Route assignment is suppressed in `_build_attendees` when a person is in `helpers_set`.
- **`run_escuela_dominical` docstring** updated to reflect current behaviour.

### Fixed

- **Per-Sunday visitor counts** were previously based on today's date (anyone added within the last 7 days from now). For historical Sundays, this misclassified people who were new weeks ago as regulars. Visitor status is now computed relative to each period's actual date.
- **HTTP 429 crash** in `get_checkins_for_event_periods` — the Escuela Dominical job makes three API calls to this function sequentially (helpers, route mapping, class check-ins); the third call could hit PCO's rate limit and raise immediately. The paginator now retries automatically.

---

## [v0.0.6] — 2026-05-02

Major internal restructuring. Behaviour and PDF output are unchanged — this
release is purely about code organisation, testability, and CI.

### Added

- **`planning_center_reports/` package** — `main.py` is now a thin 7-line wrapper.
  All logic is split into focused modules:
  - `config.py` — env vars, layout constants, `THEMES`, `_theme` global, `T()` helper
  - `models.py` — `Attendee` TypedDict + all pure helper functions (address parsing, grade/age logic, date formatting)
  - `pco_client.py` — Planning Center API calls and person cache
  - `drive_client.py` — Google Drive auth, folder creation, file upload
  - `services.py` — `_build_attendees` + `run_rutas` / `run_escuela_dominical` orchestration
  - `cli.py` — `argparse` entrypoint; applies theme then delegates to services
  - `pdf/layout.py` — ReportLab drawing primitives (header, footer, address bar, rows)
  - `pdf/rosters.py` — `generate_address_pdf` and `generate_simple_roster_pdf`
- **`tests/` suite — 68 tests, all passing** — no credentials or network access required:
  - `test_formatting.py` — `_fmt_birthday`, `_fecha_es`
  - `test_address_parsing.py` — `_extract_apt`, `_complex_key`, `_street_only`, `_is_bad_address`, `_parse_apt_number`
  - `test_grade_logic.py` — `_age_from_birthday`, `_is_minor`, `_resolve_grade`
  - `test_attendance.py` — `_build_attendees` deduplication and attendance counting (mocked PCO calls)
- **`.github/workflows/ci.yml`** — GitHub Actions CI runs `ruff check` + `pytest` on every push and pull request. Free for public repositories. Does not deploy automatically.
- **`pyproject.toml`** — configures ruff (line length 110, excludes `previews/` and `assets/`) and pytest (`testpaths = ["tests"]`).
- **`requirements-dev.txt`** — dev-only dependencies: `pytest` and `ruff`.

### Changed

- `preview.py` no longer monkey-patches `sys.modules` to stub out google/requests
  imports. It now imports only `planning_center_reports.config` and
  `planning_center_reports.pdf.rosters`, which have no network dependencies.
- `manage.sh` option 6 label updated from "Deploy updated main.py" to "Deploy
  updated code" and the existence check now also verifies the package directory.
- `setup_gcloud.sh` prerequisites check now includes `planning_center_reports/`.
- `Dockerfile` now copies `planning_center_reports/` into the image.

---

## [v0.0.5] — 2026-03-29

### Added

- **`assets/` folder** — houses per-theme image assets (`SoccerBall.png`, `gold_medal.png`). Baked into the Docker image via a new `COPY assets/ assets/` line in the Dockerfile, guaranteeing availability in Cloud Run.
- **`ASSETS_DIR` constant** — resolves the `assets/` directory relative to the script file so paths work identically in local runs and inside the container.
- **`visitor_icon` theme key** — themes can now specify a PNG filename (within `assets/`) to replace the default gold dot for visitor markers. Set to `"SoccerBall.png"` for `primavera`; `None` (gold dot) for all other themes. Falls back to the gold dot if the file is missing.
- **`campaign_icon` theme key** — themes can now specify a PNG filename to display beside the campaign label in the page header. Set to `"gold_medal.png"` for `primavera`; `None` for all other themes. When set, one icon is drawn symmetrically on each side of the centered campaign name.
- **Primavera visitor icon** — soccer ball PNG replaces the gold dot in both the data rows and the footer legend when the `primavera` theme is active.
- **Primavera campaign icon** — gold medal PNG flanks the "Campaña de Primavera" header label on both sides.

### Changed

- **Campaign label font** changed from `Helvetica-BoldOblique` to `Helvetica-Bold` — removes the italic style from the header campaign name.
- **Campaign label emoji removed when image icons are present** — ReportLab's standard fonts render emoji as coloured boxes. When a `campaign_icon` is set, the emoji string is omitted from the text and the icon image is used instead.

### Fixed

- **`manage.sh` theme args bug** — `change_theme()` was passing `--theme primavera` as a single space-separated token in `--args`, which Cloud Run splits only on commas. argparse received it as one unrecognised argument. Fixed by storing just the theme value and building the args string as `"$event_arg,--theme,$THEME_VALUE"`.

---

## [v0.0.4] — 2026-03-19

Major overhaul. Switched from a single PDF per location to a full themed roster system with visitor detection and attendance tracking.

### Added

- **Campaign themes** — `--theme` argument supports `primavera`, `verano`, `otono`, `invierno`. Each applies a seasonal colour palette to all PDF elements. Default remains IBL navy/blue.
- **`preview.py`** — local preview tool that generates sample PDFs with mock data (Chick-fil-A addresses) without needing PCO or Drive credentials. Supports `--theme`, `--type`, and `--open` flags.
- **Visitor detection** — people added to PCO within the last 7 days receive a gold dot in the first column of every PDF. Visitor count shown in the page header.
- **Attendance rate column** (`Asist.`) — shows how many of the last N weeks each person attended (e.g. `3/5`). Computed from check-in history, no extra API calls.
- **Second PDF per Rutas location** — each bus route now uploads both `Direcciones-Roster.pdf` (address-grouped) and `Roster.pdf` (alphabetical) to Drive.
- **`manage.sh` option 7** — Change campaign theme without rebuilding the Docker image.
- **`--weeks` argument** — control how many recent event periods to include (default: 5).
- **Age-based grade labels** for children under 5: Nursery (0–2), 3 años, 4 años — PCO often leaves this field blank for toddlers.

### Changed

- `generate_pdf()` renamed to `generate_address_pdf()` for clarity.
- `generate_escuela_pdf()` replaced by shared `generate_simple_roster_pdf()` used by both Rutas and Escuela Dominical.
- Visitor legend moved from inline (between data rows) to the page footer.
- Campaign name in header is now centered and larger (size 11 bold italic).
- Header rule simplified to a single clean 1.5pt line (removed double/triple rule).
- `upload_and_replace()` now accepts a `drive_name` parameter so local and Drive filenames can differ.
- `_build_attendees()` now accepts `total_weeks` to correctly compute attendance denominators.
- Removed old `NAVY`, `BLUE_MID`, `BLUE_LIGHT` etc. constants — replaced by the `THEMES` dict and `T()` helper.
- `manage.sh` option numbers shifted (7 = theme, 8–9 = test jobs, etc.).

### Fixed

- Cloud Run task timeout was 600s (10 min) — increased to 3600s (1 hour). This was causing silent failures for large check-in databases.
- `credentials.json` excluded from Docker builds by gcloud reading `.gitignore`. Fixed by creating `.gcloudignore` that only excludes `.env`.
- `entrypoint.sh` caused container startup failures due to Windows line endings — removed in favour of calling Python directly from the Dockerfile.
- Service account mismatch — Cloud Run was running as the default compute SA which had no Drive access. Jobs now run as the correct ministry service account.
- `get_person_details()` now catches `SSLError`, `ReadTimeout`, `Timeout`, and `ConnectionError` in a single handler with exponential backoff (up to 7 retries).

---

## [v0.0.3] — 2026-03-14

### Added

- **Grade column** — pulled from PCO People API (`grade` integer field), mapped to display strings (Pre-K, Kinder, 1°–12°).
- **Apartment number column** — extracted from address using regex, handles `#10B`, `APT 13A`, `Apto#20A`, bare comma-numbers like `, 506,`.
- **Address grouping by complex** — people at the same building are grouped regardless of unit number; sorted within group by unit number.
- **`street_line_1` / `street_line_2`** fields now used for address (previously used non-existent `street` field — addresses showed city only).
- **Birthday format** changed from `YYYY-MM-DD` to `MM/DD/YYYY`.
- **Generated date** fully in Spanish with time: *Generado el 14 de marzo de 2026 a las 10:32*.
- **IBL Libertad logo** in page header.
- **Marcos 16:15 verse** in page footer.
- **"Ministerio de Autobuses"** as header subtitle for Rutas PDFs.
- **`--theme` argument** groundwork (THEMES dict, `T()` helper, `_theme` global).

### Changed

- Layout switched to **landscape** orientation.
- Column headers now in **Spanish** (Nombre, Apellido, Cumpleaños, Teléfono, Dirección).
- Address bar label changed to **"Grupo de Dirección"**.
- `PCO_EVENT_NAME` removed from `.env` — event name is now a **CLI argument**.
- Alternating row tint uses theme-aware `T("row_alt")`.

### Fixed

- Pagination loop could hang indefinitely if the API returned the same `next` URL repeatedly — added same-URL guard.
- `where[event_period_id]` filter on the PCO check-ins API was silently ignored — switched to client-side filtering by `event_period.id` relationship.
- Duplicate attendees across multiple event periods — deduplication now uses a `seen` set per location that spans all periods.

---

## [v0.0.2] — 2026-03-10

### Added

- **Person details** fetched from PCO People API: birthday, phone, address.
- **Per-person caching** — `_person_cache` dict prevents redundant API calls for people checked in across multiple weeks.
- **Rate limit handling** — 429 responses trigger exponential backoff with a visible countdown.
- **`--weeks` argument** — fetch last N event periods instead of always the most recent one.
- **Pagination** for both check-ins and person detail fetches.
- **Yellow highlight** for missing/bad data cells (phone, birthday, address).
- **Google Cloud deployment** — `setup_gcloud.sh` and `manage.sh` scripts.
- **`Dockerfile`** and **`entrypoint.sh`** for Cloud Run.

### Changed

- `get_checkins_for_event_period()` now filters client-side since `where[event_period_id]` is unreliable.
- Sleep between API calls increased to 0.5s to reduce connection drops.

### Fixed

- `where[event_period_id]` API filter returning all check-ins regardless of period — now filtered in Python after fetching.

---

## [v0.0.1] — 2026-03-07

Initial working version.

### Added

- Connects to Planning Center Check-Ins API using Personal Access Token.
- Fetches check-ins for a named event's most recent event period.
- Groups check-ins by location.
- Generates a PDF roster per location (First Name, Last Name, Security Code).
- Uploads PDFs to Google Drive Shared Drive, overwriting previous version.
- Creates location subfolders automatically if they don't exist.
- `.env` support via `python-dotenv`.
