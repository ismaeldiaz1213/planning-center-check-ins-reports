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
| Key file | `credentials.json` (stored in Secret Manager as `google-credentials`) |

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

## Auto check-in (`auto_checkin.py`)

Used to bulk check in members of a PCO Group (e.g. "11th and 12th Grade") when they are
known to be present but have not been individually checked in through the app.

Configure at the top of the file:

```python
EVENT_NAME    = "Escuela Dominical"
GROUP_NAME    = "11th and 12th Grade"
LOCATION_NAME = "11th and 12th Grade"
BATCH_SIZE    = 25
```

**Getting the session cookie:**

1. Open **https://check-ins.planningcenteronline.com** while logged in
2. DevTools (`F12`) → **Application** → **Cookies** → copy `planning_center_session`
3. In DevTools Console run: `document.querySelector('meta[name=csrf-token]').content`

Add to `.env`:
```
PCO_SESSION_COOKIE=your_value
PCO_CSRF_TOKEN=your_value
```

```bash
python auto_checkin.py
```

> Session cookies expire on browser logout. Grab a fresh one if the script returns 401.

---

## Web UI

The web UI is served at the `roster-api` Cloud Run Service URL (retrieve with
`./manage.sh → option 17`). Access is restricted to `@iblibertad.org` and
`@iblibertad.com` Google accounts via the `ALLOWED_GOOGLE_DOMAINS` setting.

The `footer.church` translation key in `frontend/src/i18n/translations.ts` is set to
`"Iglesia Bautista Libertad"` — this is intentionally IBL-specific and is not driven
by an env var. Other churches should update this string to their church name.
