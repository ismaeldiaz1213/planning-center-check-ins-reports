# IBL Operational Notes

Church-specific configuration for **Iglesia Bautista Libertad** in Houston, TX.
This file is the single place where all IBL-specific values are documented.

---

## GCP project

| Setting | Value |
|---------|-------|
| Project ID | `ibl-planning-center-check-ins` |
| Region | `us-central1` |
| Artifact Registry | `us-central1-docker.pkg.dev/ibl-planning-center-check-ins/roster-repo/` |

---

## Service account

| Setting | Value |
|---------|-------|
| Display name | `ministry-account-pc` |
| Email | `ministry-account-pc@ibl-planning-center-check-ins.iam.gserviceaccount.com` |
| Key file | `credentials.json` (stored in Secret Manager as `google-service-account-key`) |

---

## Google Drive

The service account has **Editor** access to the parent roster folder.
Sub-folders are created automatically per bus route and Sunday school class.

Drive folder structure (auto-created by the script):

```
📁 Iglesia Bautista Libertad Rosters/          ← GOOGLE_DRIVE_PARENT_FOLDER_ID points here
   📁 Rutas/
      📁 Ruta 1 - Bus/
         Roster.pdf
         Instrucciones.pdf
      📁 Ruta 2 - Bus/
         ...
   📁 Escuela Dominical/
      📁 Nursery/
         Roster.pdf
      📁 Kinder/
         ...
   📁 "C" Escuela Dominical/            ← drive_folder_prefix keeps C's classes
      📁 "C" 7th Boys/                     separate from the A session's
         Roster.pdf
      📁 "C" 7th Girls/
         ...
```

---

## Reports

Configured in `reports.yaml` at the project root. The `pco_event` value must match the
Check-Ins event name in Planning Center exactly (case-sensitive). Full schema:
[docs/reports.md](reports.md).

| Report id | PCO event | Notes |
|-----------|-----------|-------|
| `rutas` | `Rutas` | Bus routes. Two PDFs per route; helpers from Junta de Rutas. |
| `escuela` | `Escuela Dominical` | Sunday school. Ruta column + attendance summary. |
| `escuela-c` | `"C" Escuela Dominical` | Bus-route kids' Sunday school, 7th–12th (formerly "B"). Same features, uploaded under its own Drive folder so class names don't collide with the A session's. |

Either the id or the PCO event name works as the CLI argument:

```bash
python main.py escuela-c
python main.py '"C" Escuela Dominical'
```

---

## Environment variables (`.env`)

```
ALLOWED_GOOGLE_DOMAINS=iblibertad.org,iblibertad.com
RUTAS_SUBTITLE=Ministerio de Autobuses
CHURCH_VERSE_TEXT="Id por todo el mundo y predicad el evangelio a toda criatura"
CHURCH_VERSE_REF=Marcos 16:15 — RV1960
GCP_PROJECT_ID=ibl-planning-center-check-ins
GCP_SA_EMAIL=ministry-account-pc@ibl-planning-center-check-ins.iam.gserviceaccount.com
```

---

## Schedule

One scheduled job, `roster-weekly`, runs every report in `reports.yaml` in a single process
(`python main.py --all`) so Rutas, Junta and parent lookups are fetched once. Each report also
has an unscheduled `roster-<id>` job for one-off runs (`./manage.sh` → 8).

| Job | Cron | Local time |
|-----|------|-----------|
| `roster-weekly` (schedule `run-roster-weekly`) | `0 8 * * 1` | Monday 2:00 AM CST / 3:00 AM CDT |

| Report | History | Volunteers |
|--------|---------|-----------|
| `rutas` | rolling 13 weeks (a quarter) | Junta de Rutas, everyone 16+ |
| `escuela` | since 2026-08-23 (back to school) | check-ins tagged *Volunteer* |
| `escuela-c` | since 2026-09-27 (first C run) | check-ins tagged *Volunteer* |

During summer (CDT, roughly March–November), the 8:00 AM UTC run lands at 3 AM local
rather than 2 AM. Adjust to `0 7 * * 1` in Cloud Scheduler if running at 2 AM is important.

---

## Workers and the Junta de Rutas

Staff now tag teachers and bus workers as **Volunteer** when checking them in, so the rosters
no longer guess who is a worker. Anyone whose latest check-in is tagged *Volunteer* goes in
the roster's **Maestros y ayudantes** table, has no Ruta, and isn't counted with the kids.

The Junta de Rutas meeting isn't tagged, so `Voluntarios.pdf` for Rutas uses everyone 16+
who checked into it, grouped by the route they serve. The sheet lists check-in times as they
are — meetings don't always start on time, so it doesn't mark anyone early or late.

"C" Escuela Dominical had no *Volunteer* check-ins as of October 2026 — its volunteer report
shows an empty state explaining how to tag them until staff start doing so.

---

## Grade promotion (`backend/promote_checkins.py`)

Full walkthrough (setup, step-by-step usage, all flags, limitations) lives in
[docs/grade-promotion.md](grade-promotion.md) — this section only covers what's specific
to IBL.

IBL's classes are split by gender and don't follow a predictable naming pattern, so
always run `make promote-checkin-locations` to get exact names rather than guessing.
Full list as of 2026-08-15:

```
03 Year Olds
Pre-K Niños                    Pre-K Niñas
Kinder Niños                   Kinder Niñas
1st Grade Boys                 1st Grade Girls
2nd Grade Boys                 2nd Grade Girls
3rd Grade Boys                 3rd Grade Girls
4th Grade Boys                 4th Grade Girls
5th Grade Boys                 5th Grade Girls
6th Grade Boys                 6th Grade Girls
7th Grade Boys                 7th Grade Girls
8th Grade Boys                 8th Grade Girls
9th and 10th Grade Boys        9th and 10th Grade Girls
11th and 12th Grade Class
College and Career
Single Adults
Clase de Parejas
Clase de Nuevos Creyentes
Clase de Ancianos (55+)
```

> `03 Year Olds` promotes into **two** destinations (`Pre-K Niños` / `Pre-K Niñas`) split
> by gender — this tool moves everyone from one location to one location, so that class
> needs to be split by hand rather than run as a single `promote-checkin` call (see
> Limitations in the grade-promotion doc).

`backend/groups_to_check_ins.py` (moved from the project root during the `backend/` +
`frontend/` split — still present, not removed) solves a different problem: bulk
check-in from a **static PCO Group's membership**, rather than from check-in history.
Use it for things like checking in a helper roster; use `promote_checkins.py` for
grade promotion.

---

## "C" Escuela Dominical backfill (`backend/backfill_bus_class.py`)

`"C" Escuela Dominical` (formerly "B") is the bus-route kids' Sunday school, 7th–12th
grade, 10:45. Its locations:

```
"C" 7th Boys          "C" 7th Girls
"C" 8th Boys          "C" 8th Girls
"C" 9th &10th Boys    "C" 9th &10th Girls
"C" 11th &12th Coed   Teachers and Helpers
```

A new event has no check-in history, so pre-select has nothing to suggest. The
backfill checks every bus kid into their "C" class for the most recent Sunday:

- **Who:** anyone checked into a `Ruta …` location of `Rutas` in the last 5 weeks,
  under 20, who **also** checked into the regular `Escuela Dominical` in that window.
  Riders with no Sunday school check-in are left out unless you pass
  `--include-non-attendees`. Drivers/captains/helpers check into
  `Chofer, Capitanes, Ayudantes`, so they're never picked up.
- **Which class:** People grade + gender. A kid with no grade falls back to the class
  they've been attending in the regular `Escuela Dominical`. Anyone still unplaced is
  listed as skipped — fix their grade in People and re-run (re-runs are safe; existing
  check-ins come back as duplicates).

```bash
make backfill-bus-class DRY_RUN=1   # preview the per-class lists
make backfill-bus-class             # submit (needs PCO_SESSION_COOKIE, like promote-checkin)
```

---

## Web UI

The web UI is served at the `roster-api` Cloud Run Service URL (retrieve with
`./manage.sh → option 16`). Access is restricted to `@iblibertad.org` and
`@iblibertad.com` Google accounts via the `ALLOWED_GOOGLE_DOMAINS` setting.

The `footer.church` translation key in `frontend/src/i18n/translations.ts` is set to
`"Iglesia Bautista Libertad"` — this is intentionally IBL-specific and is not driven
by an env var. Other churches should update this string to their church name.
