FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY planning_center_reports/ planning_center_reports/
COPY ibl_logo.png .
COPY assets/ assets/
COPY credentials.json .

ENTRYPOINT ["python", "main.py"]
