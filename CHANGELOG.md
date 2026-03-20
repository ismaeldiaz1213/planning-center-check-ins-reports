# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

> Changes staged for the next release go here.

---

## [2.0.0] — 2026-03-19

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
- Service account mismatch — Cloud Run was running as the default compute SA which had no Drive access. Jobs now run as `ministry-account-pc`.
- `get_person_details()` now catches `SSLError`, `ReadTimeout`, `Timeout`, and `ConnectionError` in a single handler with exponential backoff (up to 7 retries).

---

## [1.2.0] — 2026-03-14

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

## [1.1.0] — 2026-03-10

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

## [1.0.0] — 2026-03-07

Initial release.

### Added
- Connects to Planning Center Check-Ins API using Personal Access Token.
- Fetches check-ins for a named event's most recent event period.
- Groups check-ins by location.
- Generates a PDF roster per location (First Name, Last Name, Security Code).
- Uploads PDFs to Google Drive Shared Drive, overwriting previous version.
- Creates location subfolders automatically if they don't exist.
- `.env` support via `python-dotenv`.