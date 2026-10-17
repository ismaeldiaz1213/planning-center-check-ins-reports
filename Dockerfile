# Cloud Run job image — runs main.py for one configured report.
# The web API server (api.py) and the React frontend are deployed separately
# and are NOT included in this image.
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/main.py .
COPY backend/planning_center_reports/ planning_center_reports/
COPY backend/logo.png .
COPY backend/assets/ assets/

# Report definitions. The glob makes this optional: with no reports.yaml the app
# falls back to its built-in Rutas + Escuela Dominical defaults. It lands in /app,
# which is the "backend/" location the loader checks.
COPY reports.yaml* ./

# credentials.json must be supplied at runtime via a mounted secret or volume.
# Cloud Run: mount via Secret Manager to a path outside /app — a secret volume replaces
#   the entire last directory of its mount path, which would hide the files COPYed above
#   if mounted straight into /app. GOOGLE_APPLICATION_CREDENTIALS tells the app where to
#   find it:  --set-secrets=/secrets/credentials.json=google-service-account-key:latest
#             --set-env-vars=GOOGLE_APPLICATION_CREDENTIALS=/secrets/credentials.json
# Local dev: bind-mount a single file with -v $(pwd)/credentials.json:/app/credentials.json
#   (safe locally — a single-file bind-mount doesn't replace the whole directory).

ENTRYPOINT ["python", "main.py"]
