# Report Configuration Reference

A **report** is one Planning Center Check-Ins event plus the roster PDFs generated from it.
Reports are defined in `reports.yaml` at the project root.

Every optional feature is **off by default**. A church with no bus ministry never sees a
`Ruta` column, and the job never contacts a bus-route or helpers event that doesn't exist.

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

That produces one alphabetical `Roster.pdf` per location, uploaded to a Drive folder named
after the location — no route column, no helper lookup, no attendance tables, and no calls to
any Planning Center event other than `Clases de Niños`.

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
| `outputs` | `[simple]` | Which PDFs to generate. `simple` → `Roster.pdf` (alphabetical). `address` → `Direcciones-Roster.pdf` (grouped by apartment complex, with blank write-in rows). List both to get both. |

### Optional features

All default to off. Each one that stays off is a Planning Center event that is never fetched.

| Field | Default | Description |
|-------|---------|-------------|
| `route_source_event` | *(none)* | Check-Ins event to derive each person's bus route from. Leave unset if you have no bus ministry. |
| `show_route` | `false` | Render the `Ruta` column. Requires `route_source_event` — the config is rejected otherwise, since the column would always be blank. |
| `helpers_event` | *(none)* | Check-Ins event identifying workers/helpers. People in it who are at least `helper_min_age` are marked as helpers: their route column stays blank and they are excluded from the attendance-summary counts. Leave unset if you have no such event. |
| `helper_min_age` | `16` | Age threshold for the above. |
| `attendance_summary` | `false` | Draw the per-Sunday regular/visitor table and the per-route headcount table below the roster. |

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
| `default_weeks` | `5` | How many recent weeks of check-ins to include (1–52). |
| `default_theme` | *(none)* | `primavera`, `verano`, `otono`, or `invierno`. |
| `demo_locations` | *(none)* | Location names `demo_run.py` invents when `DEMO_MODE=true`. |

Precedence for weeks and theme: **CLI flag → environment variable → `reports.yaml`**.

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

No `route_source_event`, no `helpers_event` — the `Rutas` and `Junta de Rutas Attendance`
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

### Bus routes with both roster styles

```yaml
reports:
  - id: rutas
    label: Rutas
    pco_event: Rutas
    subtitle: Ministerio de Autobuses
    outputs: [address, simple]
    helpers_event: Junta de Rutas Attendance
```

---

## Adding a report end to end

1. Create the event in Planning Center Check-Ins and note its exact name.
2. Add a block to `reports.yaml`.
3. Verify it parses: `cd backend && python main.py --list-reports`
4. Preview the PDF shape with mock data: `python preview.py --report <id> --open`
5. Test against live data without uploading:
   `python main.py <id> --dry-run --output-dir /tmp/<id>-out`
6. Deploy: `./manage.sh → option 6` rebuilds the image and updates every report's job,
   creating the Cloud Run job and Monday schedule for any report that doesn't have one yet.
7. If you **renamed or removed** a report id, run `./manage.sh → option 10` (Sync Cloud Run
   jobs). It finds `roster-*` jobs that no longer match a configured report and offers to
   delete them with their schedules — a stale job keeps firing weekly and would generate a
   duplicate set of rosters.

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
| `unknown output ['excel']` | `outputs` accepts only `simple` and `address`. |
| `show_route is true but route_source_event is not set` | The `Ruta` column would render blank for every row. |
| `unknown theme 'otoño'` | Use `otono` — the theme keys are ASCII. |
| `default_weeks must be between 1 and 52` | Out of range. |
