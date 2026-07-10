# Getting Started

This guide walks through setting up the roster system for your church from scratch.

---

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.10+ | `python3 --version` |
| Node.js | 18+ | `node --version` (only needed if running the web UI) |
| Google Cloud CLI | any | `gcloud --version` (only needed for Cloud Run deployment) |

---

## 1. Clone the repo

```bash
git clone https://github.com/ismaeldiaz1213/planning-center-check-ins-reports.git
cd planning-center-check-ins-reports
```

---

## 2. Create your environment file

```bash
cp .env.example .env
```

Open `.env` and fill in at minimum:

```
PCO_APP_ID=your_planning_center_app_id
PCO_SECRET=your_planning_center_secret
GOOGLE_DRIVE_PARENT_FOLDER_ID=your_drive_folder_id
```

See [configuration.md](configuration.md) for the full list of variables and where to get each one.

---

## 3. Install backend dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-web.txt -r requirements-dev.txt
```

---

## 4. Run the tests

```bash
pytest          # 185 backend tests, no credentials required
ruff check .    # linter
```

All tests use mock data — no Planning Center or Google Drive connection needed.

---

## 5. Generate sample PDFs without real church data

```bash
python preview.py
```

This writes PDFs to `backend/previews/` using mock attendees. No credentials needed.
See [sample-data.md](sample-data.md) for full usage (themes, types, `--open` flag).

---

## 6. Run against your Planning Center account

Before uploading anything to Drive, do a **dry run** from the project root to verify
everything looks right. The easiest way is through `manage.sh`:

```bash
./manage.sh → option 20   # build local Docker image (one-time)
./manage.sh → option 21   # dry-run Rutas — all routes, no Drive upload
./manage.sh → option 22   # dry-run Rutas — single route (prompts for name)
./manage.sh → option 23   # dry-run Escuela Dominical — all classes
./manage.sh → option 24   # dry-run Escuela Dominical — single class
```

PDFs are saved to `./out/` and the folder opens automatically when done.
Nothing is uploaded to Google Drive.

When you're happy with the output, run the real job:

```bash
./manage.sh → option 8    # run Rutas (uploads to Drive)
./manage.sh → option 9    # run Escuela Dominical (uploads to Drive)
```

| Path | Data | Drive upload | Output |
|------|------|-------------|--------|
| `python preview.py` | Fake (mock names) | No | `backend/previews/` |
| `manage.sh → 21-24` | Real Planning Center | No | `./out/` |
| `manage.sh → 8-9` | Real Planning Center | Yes | Google Drive |

---

## Next steps

- **Deploy to Google Cloud** → [deployment-gcp.md](deployment-gcp.md)
- **Configure all options** → [configuration.md](configuration.md)
- **Run the web UI locally** → see [DEVELOPMENT.md](../DEVELOPMENT.md)
