# Planning Center Check-Ins — Roster System

Automatically generates PDF rosters from [Planning Center](https://www.planningcenter.com/) check-ins and uploads them to Google Drive on a weekly schedule. Originally built for a church bus ministry; configurable for any church using Planning Center Check-Ins.

---

## Live Demo

**Not sure if this fits your church's workflow? Try it before setting anything up.**

> **[→ Open the live demo](https://roster-api-demo-k3lvrupgua-uc.a.run.app/)** — no login, no credentials, no download required.

The demo runs the full web UI against mock data: trigger a Rutas or Escuela Dominical job, watch the log output stream in real time, and preview the generated PDFs. It's the real application — just with fake attendees instead of your church data.


---

## Quickstart

```bash
# 1. Clone
git clone https://github.com/ismaeldiaz1213/planning-center-check-ins-reports.git
cd planning-center-check-ins-reports

# 2. Create your environment file
cp .env.example .env
# Open .env and fill in PCO_APP_ID, PCO_SECRET, GOOGLE_DRIVE_PARENT_FOLDER_ID

# 3. Install backend dependencies
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-web.txt -r requirements-dev.txt

# 4. Run tests (no credentials needed)
pytest && ruff check .

# 5. Generate sample PDFs (no credentials needed)
python preview.py --open

# 6. Run against your Planning Center account
python main.py "Your Event Name"
```

See [docs/getting-started.md](docs/getting-started.md) for the full walkthrough.

---

## Features

- **Two roster types per bus route** — address-grouped PDF for secretaries, clean alphabetical list for drivers
- **Sunday school rosters** — one per class with grade, attendance rate, and bus route column
- **Attendance summary tables** — per-Sunday regular/visitor counts and per-route headcount
- **Yellow highlights** for missing data (phone, birthday, address, grade)
- **Visitor dot** — gold circle marks people added to PCO within the last 7 days
- **Attendance rate** — shows how many of the last N weeks each person attended (e.g. `3/5`)
- **Campaign themes** — seasonal colour schemes for special events
- **Web UI** — dashboard for triggering jobs, previewing PDFs, editing settings, and viewing logs
- **Demo mode** — deploy a public `DEMO_MODE=true` instance so developers can evaluate the app without credentials
- **Google OAuth login** — restrict access to your church's Google Workspace domain
- **Fully automated** via Google Cloud Run + Cloud Scheduler

---

## PDF Output

### Bus Routes (Rutas)

Each bus route folder in Google Drive receives two PDFs every week:

| File | Description |
|------|-------------|
| `Direcciones-Roster.pdf` | People grouped by apartment complex, sorted by unit number. Includes empty writable rows for walk-ins. |
| `Roster.pdf` | Clean alphabetical list sorted by last name. Good for drivers. |

### Sunday School (Escuela Dominical)

Each class location receives:

| File | Description |
|------|-------------|
| `Roster.pdf` | Alphabetical roster with grade, bus route number, attendance rate, and visitor indicators. Includes attendance summary tables at the bottom. |

### Column Reference

| Column | Notes |
|--------|-------|
| ● / ⚽ | Visitor marker — gold dot by default; soccer ball PNG for the `primavera` theme |
| Nombre / Apellido | First and last name |
| Cumpleaños | Birthday in MM/DD/YYYY format |
| Teléfono | Primary phone number |
| Grado | PCO grade field; auto-filled as Nursery / 3 años / 4 años for children under 5 |
| Apto. | Apartment number extracted from address |
| Ruta | Bus route number — Sunday school rosters only; blank for helpers |
| Asist. | Attendance rate over the selected window (e.g. `4/5`) |
| Dirección | Street address without apartment number |

**Yellow highlighting** means the cell is missing or incomplete — phone, birthday, grade (for minors), and bad/city-only addresses all trigger this.

---

## Campaign Themes

Pass `--theme` to apply a seasonal colour scheme:

```bash
python main.py "Rutas" --theme primavera
python main.py "Rutas" --theme verano
python main.py "Rutas" --theme otono
python main.py "Rutas" --theme invierno
```

| Theme | Colours | Label | Visitor marker |
|-------|---------|-------|----------------|
| *(none)* | Navy/blue | — | Gold dot |
| `primavera` | Greens | Campaña de Primavera | Soccer ball PNG |
| `verano` | Orange/red | Campaña de Verano | Gold dot |
| `otono` | Brown/tan | Campaña de Otoño | Gold dot |
| `invierno` | Deep indigo/blue | Campaña de Invierno | Gold dot |

---

## Documentation

- [Getting Started](docs/getting-started.md) — clone, configure, run tests, generate PDFs
- [Configuration Reference](docs/configuration.md) — all environment variables, PCO permissions, Drive setup, logo
- [Deploying to Google Cloud](docs/deployment-gcp.md) — Cloud Run jobs, manage.sh, web UI deploy
- [Sample Data & Previews](docs/sample-data.md) — preview.py flags and mock data editing

For development workflow (running the test suite, Vite dev server, full-stack local setup),
see [DEVELOPMENT.md](DEVELOPMENT.md).

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `429 Too Many Requests` | Script auto-retries with exponential backoff. Wait for it. |
| `SSL EOF / ReadTimeout` | Auto-retries up to 7 times. If persistent, try again later. |
| `Event 'X' not found` | Event name is case-sensitive — check exact name in PCO Check-Ins. |
| `No such file: main.py` in Cloud | Job is using a stale image. Run `manage.sh → option 6`. |
| PDFs not appearing in Drive | Confirm service account has Editor access to the Drive folder. |
| Job timed out | Both jobs have a 3600s (1 hour) limit. Should be sufficient for any church size. |
| Theme not applying | Run both build + job update, or use `manage.sh → option 6` which does both. |
| `unrecognized arguments: --theme primavera` | `--args` requires comma-separated tokens, not spaces: `--theme,primavera`. |

---

## Schedule

| Job | Cron | Default time |
|-----|------|-------------|
| Bus routes | `0 8 * * 1` | Monday 8:00 AM UTC (2:00 AM CST) |
| Sunday school | `0 8 * * 1` | Monday 8:00 AM UTC (2:00 AM CST) |

---

## Security

- **Never commit** `.env` or `credentials.json` — both are in `.gitignore`
- `credentials.json` is supplied at runtime via Secret Manager — not baked into any Docker image
- PCO credentials live in Google Secret Manager — never in the image
- Rotate your PCO token at **https://api.planningcenteronline.com/oauth/applications** if exposed
- Rotate your service account key in Cloud Console → IAM → Service Accounts if exposed
- See [SECURITY.md](SECURITY.md) for the full security policy and vulnerability reporting
