# EmotionRecognitionGateway
# FastAPI: JWT auth, CORS, rate limiting, proxy to orchestrator/storage
# Talks to: Redis, PostgreSQL (gateway_db), Orchestrator (HTTP), Storage (HTTP)
# Port: 8000

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
