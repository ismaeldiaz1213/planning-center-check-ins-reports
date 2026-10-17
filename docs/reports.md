# Report Configuration Reference

A **report** is one Planning Center Check-Ins event plus the roster PDFs generated from it.
Reports are defined in `reports.yaml` at the project root.

Every optional feature is **off by default**. A church with no bus ministry never sees a
`Ruta` column, and the job never contacts a bus-route or workers' event that doesn't exist.

## What each report produces

| File | Where | What's in it |
|------|-------|--------------|
| `Roster.pdf` | one per class/route folder | **Lista** (everyone seen in the active window, with attendance dots, *date added* and a parent line under each kid); **Maestros y ayudantes** (check-ins Planning Center tags as *Volunteer*); **Hace tiempo que no viene** (seen since the history start but not lately — a follow-up call list); **Resumen** (average per Sunday, recently added, attendance per Sunday, kids per route); a feedback-form box. |
| `Instrucciones.pdf` | next to every roster (`instructions: true`) | A bilingual cover (3 steps, QR to the video, quick reference, feedback QR) followed by the full Spanish and English check-in guides from `backend/assets/guides/`. Re-uploaded only when its content changes. |
| `Voluntarios.pdf` | `Voluntarios/<label>/` (`volunteer_report: true`) | Who served each of the last `volunteer_weeks` Sundays and their check-in time, grouped by class/route, with per-Sunday totals. Times are shown as-is — no early/late labels. |

### How a roster is built

- A person belongs to the location of their **most recent** check-in, so a kid who changed
  classes appears once, in the new class.
- **Active** = seen in the last `default_weeks` Sundays. Everyone else seen since the history
  start goes to **Hace tiempo**, most recently lapsed first.
- **Date added** = their first Sunday in this class since the history start. Blank when that was
  the very first Sunday — they were already a regular. Dates inside the active window are
  highlighted in green.
- **★ New** = their first check-in for the whole event was the latest Sunday.
- **Parents** come from the kid's PCO household primary contact, looked up in two batched People
  API calls. Only adults are shown: when PCO makes an older sibling the head of household, no
  parent line is printed.
- Contact details come from the check-ins themselves (PCO sideloads the person), so a run makes
  no per-person API calls — all three IBL reports together take ~130 requests and under a minute.

---

## Getting started

```bash
cp reports.yaml.example reports.yaml
# edit reports.yaml, then:
cd backend && python main.py --list-reports
```

If `reports.yaml` does not exist, the built-in defaults are used — `Rutas` and
`Escuela Dominical`, configured exactly as they behaved before this file existed. An existing
install needs no changes.

Load order:

1. `$REPORTS_CONFIG` — an explicit path (errors if the file is missing)
2. `reports.yaml` at the project root
3. `backend/reports.yaml`
4. the built-in defaults

---

## The minimal report

Three fields. Nothing else is required.

```yaml
reports:
  - id: ninos
    label: Clases de Niños
    pco_event: Clases de Niños
```

That produces one `Roster.pdf` per location covering a rolling 26 weeks, uploaded to a Drive
folder named after the location — no route column, no volunteer report, and no calls to any
Planning Center event other than `Clases de Niños` (plus the batched parent lookup).

---

## Schema

### Required

| Field | Description |
|-------|-------------|
| `id` | Slug used as the CLI argument, the API path segment (`/api/jobs/<id>/run`), the Cloud Run job suffix (`roster-<id>`), and the dashboard tile key. Lowercase with hyphens. |
| `label` | Human-readable name shown in the web UI and used as the PDF subtitle unless `subtitle` is set. |
| `pco_event` | The Check-Ins event name in Planning Center, **matched exactly** (case-sensitive). Quote it in YAML if it contains quotes or special characters. |

### Presentation

| Field | Default | Description |
|-------|---------|-------------|
| `subtitle` | `label` | Subtitle drawn under the title in the PDF header. |
| `icon` | `📋` | Emoji shown on the dashboard tile. |
| `enabled` | `true` | Set to `false` to hide a report from the UI, CLI, and deploy scripts without deleting it. |

### Outputs

| Field | Default | Description |
|-------|---------|-------------|
| `outputs` | `[simple]` | `simple` → `Roster.pdf`. (The address-grouped `Direcciones-Roster.pdf` was retired; `address` is now rejected.) |
| `instructions` | `false` | Put `Instrucciones.pdf` in every location folder. |

### History

| Field | Default | Description |
|-------|---------|-------------|
| `start_date` | *(none)* | Fixed first Sunday (`YYYY-MM-DD`), e.g. back-to-school. Use for classes that reset each school year. |
| `history_weeks` | `26` | Rolling window used when `start_date` is unset — e.g. `13` (a quarter) for bus routes that run all year. |
| `default_weeks` | `6` | The **active** window: people seen in the last N Sundays are on the list; older ones move to *Hace tiempo*. |
| `max_history_weeks` | `52` | Safety cap on how many Sundays are fetched. |

### Optional features

All default to off. Each one that stays off is a Planning Center event that is never fetched.

| Field | Default | Description |
|-------|---------|-------------|
| `route_source_event` | *(none)* | Check-Ins event to derive each person's bus route from. Leave unset if you have no bus ministry. |
| `show_route` | `false` | Render the `Ruta` column. Requires `route_source_event` — the config is rejected otherwise, since the column would always be blank. |
| `attendance_summary` | `false` | Draw the per-route headcount table (with `show_route`). |
| `volunteer_report` | `false` | Generate `Voluntarios.pdf`. |
| `volunteer_event` | *(none)* | Take volunteer attendance from this event instead, counting everyone `volunteer_min_age`+ (for a workers-only meeting where nobody is tagged *Volunteer*). Unset ⇒ this report's own check-ins tagged *Volunteer*. |
| `volunteer_min_age` | `16` | Age threshold when `volunteer_event` is set. |
| `volunteer_weeks` | `4` | Sundays covered by `Voluntarios.pdf`. |

Workers are whoever Planning Center tags as **Volunteer** on their latest check-in — the old
`helpers_event` / `helper_min_age` age heuristic is gone, and those keys are now rejected.

### Destination

| Field | Default | Description |
|-------|---------|-------------|
| `drive_folder_prefix` | *(none)* | Nest this report's location folders one level deeper in Google Drive. Use it when two reports have overlapping location names — without it they would overwrite each other's `Roster.pdf`. With no prefix, location folders sit directly under `GOOGLE_DRIVE_PARENT_FOLDER_ID`, which is the original layout. |

```
GOOGLE_DRIVE_PARENT_FOLDER_ID/          # no prefix
  Clase Primaria/Roster.pdf

GOOGLE_DRIVE_PARENT_FOLDER_ID/          # drive_folder_prefix: '"B" Escuela Dominical'
  "B" Escuela Dominical/
    Clase Primaria/Roster.pdf
```

`--dry-run` mirrors the same nesting under `--output-dir`.

### Run defaults

| Field | Default | Description |
|-------|---------|-------------|
| `default_theme` | *(none)* | `primavera`, `verano`, `otono`, or `invierno`. |
| `demo_locations` | *(none)* | Location names `demo_run.py` invents when `DEMO_MODE=true`. |

Precedence for the active window (`default_weeks`) and theme: **CLI flag → environment variable →
`reports.yaml`**. With `--all`, each report uses its own `default_weeks`; `--theme` applies to all.

The environment variable name is derived from the id, uppercased with hyphens turned into
underscores:

| Report id | Weeks | Theme |
|-----------|-------|-------|
| `rutas` | `RUTAS_DEFAULT_WEEKS` | `RUTAS_DEFAULT_THEME` |
| `escuela` | `ESCUELA_DEFAULT_WEEKS` | `ESCUELA_DEFAULT_THEME` |
| `escuela-b` | `ESCUELA_B_DEFAULT_WEEKS` | `ESCUELA_B_DEFAULT_THEME` |

The web UI's Settings panel writes these variables to `.env`, one section per report.

---

## Examples

### A church with no bus ministry

```yaml
reports:
  - id: escuela
    label: Escuela Dominical
    pco_event: Escuela Dominical
    icon: "📚"
    attendance_summary: true
```

No `route_source_event`, no `volunteer_event` — the `Rutas` and `Junta de Rutas Attendance`
events are never requested, and the roster has no `Ruta` column.

### Two Sunday school sessions sharing class names

```yaml
reports:
  - id: escuela
    label: Escuela Dominical
    pco_event: Escuela Dominical
    route_source_event: Rutas
    show_route: true
    attendance_summary: true

  - id: escuela-b
    label: '"B" Escuela Dominical'
    pco_event: '"B" Escuela Dominical'
    route_source_event: Rutas
    show_route: true
    attendance_summary: true
    drive_folder_prefix: '"B" Escuela Dominical'
```

### Bus routes on a rolling quarter, with workers' attendance

```yaml
reports:
  - id: rutas
    label: Rutas
    pco_event: Rutas
    subtitle: Ministerio de Autobuses
    history_weeks: 13
    instructions: true
    volunteer_report: true
    volunteer_event: Junta de Rutas Attendance
    volunteer_min_age: 16
```

---

## Adding a report end to end

1. Create the event in Planning Center Check-Ins and note its exact name.
2. Add a block to `reports.yaml`.
3. Verify it parses: `cd backend && python main.py --list-reports`
4. Preview the PDF shape with mock data: `python preview.py --report <id> --open`
5. Test against live data without uploading:
   `python main.py <id> --dry-run --output-dir /tmp/<id>-out`
6. Deploy: `./manage.sh → option 6` rebuilds the image and updates the jobs. One scheduled job,
   `roster-weekly`, runs **every** enabled report in one process (`python main.py --all`), so a
   new report is picked up automatically. Each report also gets an unscheduled `roster-<id>`
   job for one-off runs (option 8).
7. If you **renamed or removed** a report id, run `./manage.sh → option 10` (Sync Cloud Run
   jobs). It finds `roster-*` jobs that no longer match a configured report, and leftover
   per-report schedules from before `roster-weekly`, and offers to delete them — a stale
   schedule keeps firing weekly and would generate a duplicate set of rosters.

The dashboard tile, the `/api/jobs/<id>/run` endpoint, and the Settings section appear
automatically — no frontend change is needed.

### Optional: translated tile text

A new report's tile uses its `label` and `icon`. To give it dedicated Spanish/English strings,
add `tile.<id>.title`, `tile.<id>.desc`, `job.<id>.title`, `job.<id>.desc`, and
`logs.type.<id>` to `frontend/src/i18n/translations.ts`.

---

## Configuring an event that doesn't exist yet

A report can be added before its Check-Ins event is created, or before anyone has checked into
it. The job logs a warning and exits cleanly rather than failing:

```
⚠ Event '"B" Escuela Dominical' not found in Planning Center: ...
Skipping report 'escuela-b' — nothing to generate.
```

```
  ⚠ No Check-Ins event named '"B" Escuela Dominical' exists in Planning Center yet. (404)
  Nothing to generate for report 'escuela-b' — this is not an error.
  Rosters will be produced automatically once check-ins start arriving for this event.
```

The job **exits 0**, so Cloud Run and Cloud Scheduler both record it as a success and no
alerting fires. The same applies to an event that exists but has no check-ins in the window.
Once check-ins start arriving, the same job produces rosters with no further changes.

---

## Validation errors

`reports.yaml` is validated on load, and a bad file fails immediately with the offending
report named:

| Message | Cause |
|---------|-------|
| `has unknown key(s) [...]` | A misspelled field name. |
| `duplicate report id 'x'` | Two reports share an `id`. |
| `unknown output ['excel']` | `outputs` accepts only `simple`. |
| `show_route is true but route_source_event is not set` | The `Ruta` column would render blank for every row. |
| `unknown theme 'otoño'` | Use `otono` — the theme keys are ASCII. |
| `default_weeks must be between 1 and 52` | Out of range. |
| `start_date must be YYYY-MM-DD` | e.g. `start_date: 2026-08-23`. |
