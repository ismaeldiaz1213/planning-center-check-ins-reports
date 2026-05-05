# Cloud Run job image — runs main.py (Rutas or Escuela Dominical pipeline).
# The web API server (api.py) and the React frontend are deployed separately
# and are NOT included in this image.
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/main.py .
COPY backend/planning_center_reports/ planning_center_reports/
COPY backend/ibl_logo.png .
COPY backend/assets/ assets/
COPY credentials.json .

ENTRYPOINT ["python", "main.py"]
