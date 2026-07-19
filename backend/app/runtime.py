"""In-memory runtime: live WS fan-out per session + camera→session routing.

Perception is loaded lazily (Phase 2) so the server boots without the heavy ML
wheels. Until a pipeline is available, frame ingestion still round-trips frame
dimensions so the live-feed loop (Phase 1) can be verified.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict

import numpy as np
from fastapi import WebSocket


class SessionHub:
    """Tracks live dashboard clients and camera→session bindings."""

    def __init__(self) -> None:
        self._clients: dict[str, set[WebSocket]] = defaultdict(set)
        self._camera_session: dict[str, str] = {}
        self._lock = asyncio.Lock()

    # --- camera binding ---
    def bind_camera(self, camera_id: str, session_id: str) -> None:
        self._camera_session[camera_id] = session_id

    def session_for_camera(self, camera_id: str) -> str | None:
        return self._camera_session.get(camera_id)

    # --- live dashboard clients ---
    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients[session_id].add(ws)

    async def disconnect(self, session_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._clients[session_id].discard(ws)

    async def broadcast(self, session_id: str, message: dict) -> None:
        """Send a JSON message to every live client of a session."""
        dead: list[WebSocket] = []
        for ws in list(self._clients.get(session_id, ())):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients[session_id].discard(ws)


hub = SessionHub()

# Lazily-created perception pipeline (Phase 2). None until first use / if unavailable.
_pipeline = None
_pipeline_tried = False


def get_pipeline():
    """Return a shared Pipeline instance, or None if ML deps aren't installed."""
    global _pipeline, _pipeline_tried
    if _pipeline is None and not _pipeline_tried:
        _pipeline_tried = True
        try:
            from .perception.pipeline import Pipeline

            _pipeline = Pipeline()
        except Exception as exc:  # ML deps missing or load failure — degrade gracefully
            print(f"[runtime] perception pipeline unavailable: {exc}")
            _pipeline = None
    return _pipeline


def decode_jpeg(data: bytes) -> np.ndarray | None:
    import cv2

    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)
