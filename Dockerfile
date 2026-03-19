FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY ibl_logo.png .
COPY credentials.json .

ENTRYPOINT ["python", "main.py"]
