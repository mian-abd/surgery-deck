# ORGuard backend — FastAPI + perception. CPU inference.
#
# NOTE: this is a large image (~3-5 GB). torch + torchvision + ultralytics +
# mediapipe + opencv-contrib are heavy. The build below installs the CPU-only
# torch wheels from the PyTorch CPU index to avoid pulling ~2 GB of CUDA libs
# that Cloud Run cannot use anyway. If the pinned versions are not published on
# the CPU index, override _TORCH_INDEX_URL with the default PyPI index
# (--build-arg TORCH_INDEX_URL=https://pypi.org/simple) — the image just gets
# bigger.
FROM python:3.10-slim

# System libs required by opencv-contrib + mediapipe
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Keep pip quiet/lean and avoid caching wheels into the image layer.
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .

# 1) Install CPU-only torch/torchvision first, pinned to the versions in
#    requirements.txt, from the PyTorch CPU wheel index. Pre-installing the
#    exact pins means the requirements install below sees them as satisfied and
#    does NOT pull the default (CUDA) wheels.
# 2) Install the rest of the pinned dependencies from PyPI.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
# Use --extra-index-url (NOT --index-url): torch/torchvision resolve to the
# CPU-only wheels from the PyTorch index (the local "+cpu" version sorts higher
# than PyPI's CUDA build so it wins for ==2.13.0), while torch's own deps
# (typing-extensions, sympy, networkx, ...) still resolve from PyPI.
RUN pip install --extra-index-url ${TORCH_INDEX_URL} \
        torch==2.13.0 torchvision==0.28.0 \
 && pip install -r requirements.txt

COPY app ./app

ENV MODELS_DIR=/app/models \
    EVIDENCE_DIR=/app/evidence \
    PORT=8080
RUN mkdir -p /app/models /app/evidence

EXPOSE 8080

# Cloud Run provides $PORT (default 8080). uvicorn[standard] ships the
# `websockets` impl so /ws/ingest and /ws/session work out of the box.
# IMPORTANT: keep --workers 1. The SessionHub (camera->session bindings and
# live WS clients) is in-process state; multiple workers would each hold a
# separate, inconsistent copy. Horizontal scaling requires shared state, which
# this MVP does not have — see deploy/README.md "WebSockets on Cloud Run".
# --proxy-headers / --forwarded-allow-ips let uvicorn trust the Cloud Run (and
# nginx) X-Forwarded-* headers so request scheme/host are correct.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
