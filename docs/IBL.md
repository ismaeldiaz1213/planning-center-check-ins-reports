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
         Direcciones-Roster.pdf
      📁 Ruta 2 - Bus/
         ...
   📁 Escuela Dominical/
      📁 Nursery/
         Roster.pdf
      📁 Kinder/
         ...
```

---

## Planning Center event names

These are passed as arguments to `main.py` and must match exactly (case-sensitive):

| Event | Argument |
|-------|---------|
| Bus routes | `Rutas` |
| Sunday school | `Escuela Dominical` |

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

| Job | Cron | Local time |
|-----|------|-----------|
| Rutas | `0 8 * * 1` | Monday 2:00 AM CST / 3:00 AM CDT |
| Escuela Dominical | `0 8 * * 1` | Monday 2:00 AM CST / 3:00 AM CDT |

During summer (CDT, roughly March–November), the 8:00 AM UTC run lands at 3 AM local
rather than 2 AM. Adjust to `0 7 * * 1` in Cloud Scheduler if running at 2 AM is important.

---

## Helpers / Junta de Rutas

Bus workers (helpers) are members 16+ who appear on the Junta de Rutas attendance list.
They are checked into the Escuela Dominical event but belong to a helper group rather than
a Sunday school class. In the generated PDFs:

- They appear on the Sunday school roster with their name and attendance rate
- The **Ruta** column is blank (they are not assigned to a class route)
- They are **not** counted toward route headcount totals in the attendance summary table

The helper detection logic lives in `backend/planning_center_reports/services.py`.

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

## Web UI

The web UI is served at the `roster-api` Cloud Run Service URL (retrieve with
`./manage.sh → option 17`). Access is restricted to `@iblibertad.org` and
`@iblibertad.com` Google accounts via the `ALLOWED_GOOGLE_DOMAINS` setting.

The `footer.church` translation key in `frontend/src/i18n/translations.ts` is set to
`"Iglesia Bautista Libertad"` — this is intentionally IBL-specific and is not driven
by an env var. Other churches should update this string to their church name.
