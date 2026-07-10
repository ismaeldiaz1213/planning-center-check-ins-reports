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

Replace `"Rutas"` and `"Escuela Dominical"` with the exact event names from your
Planning Center Check-Ins account (they are case-sensitive):

```bash
python main.py "Rutas"
python main.py "Escuela Dominical"
```

PDFs will be generated and uploaded to your Google Drive folder.

---

## Next steps

- **Deploy to Google Cloud** → [deployment-gcp.md](deployment-gcp.md)
- **Configure all options** → [configuration.md](configuration.md)
- **Run the web UI locally** → see [DEVELOPMENT.md](../DEVELOPMENT.md)
