# ORGuard backend — FastAPI + perception. CPU inference.
FROM python:3.10-slim

# System libs required by opencv-contrib + mediapipe
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV MODELS_DIR=/app/models \
    EVIDENCE_DIR=/app/evidence \
    PORT=8080
RUN mkdir -p /app/models /app/evidence

# Cloud Run provides $PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
