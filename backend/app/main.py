"""ORGuard FastAPI application entrypoint."""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import reviews, sessions, zones
from .config import settings
from .db import init_db
from .storage import evidence_dir
from .ws import ingest, live

app = FastAPI(title="ORGuard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    os.makedirs(evidence_dir(), exist_ok=True)


@app.get("/health")
def health() -> dict:
    from .runtime import get_pipeline

    return {
        "status": "ok",
        "service": "orguard",
        "perception": get_pipeline() is not None,
        "storage": settings.storage_backend,
    }


# REST
app.include_router(sessions.router, prefix="/api", tags=["sessions"])
app.include_router(zones.router, prefix="/api", tags=["zones"])
app.include_router(reviews.router, prefix="/api", tags=["reviews"])

# WebSockets
app.include_router(ingest.router)
app.include_router(live.router)

# Evidence frames served statically (local backend)
app.mount("/evidence", StaticFiles(directory=evidence_dir()), name="evidence")
