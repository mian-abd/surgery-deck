"""WS /ws/ingest/{camera_id}: receive JPEG frames from a camera station.

The camera station (a laptop/phone running the /capture page) streams frames
here. Each frame is decoded and (when perception is available) run through the
pipeline. The frame image plus detections/alerts are then relayed to the
session's VIEWER clients (the Android app) over /ws/session/{id} so viewer-only
devices can see the live feed with overlays. A light ACK (fps) goes back to the
camera station.
"""
from __future__ import annotations

import base64
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..runtime import decode_jpeg, get_pipeline, hub

router = APIRouter()


@router.websocket("/ws/ingest/{camera_id}")
async def ingest(ws: WebSocket, camera_id: str) -> None:
    await ws.accept()
    session_id = hub.session_for_camera(camera_id)
    frames = 0
    fps = 0.0
    t0 = time.time()
    try:
        while True:
            data = await ws.receive_bytes()
            frame = decode_jpeg(data)
            if frame is None:
                await ws.send_json({"type": "error", "message": "decode failed"})
                continue

            h, w = frame.shape[:2]
            frames += 1
            session_id = session_id or hub.session_for_camera(camera_id)

            perception: dict = {}
            pipeline = get_pipeline()
            if pipeline is not None and session_id:
                perception = pipeline.process(session_id, camera_id, frame)

            elapsed = time.time() - t0
            if elapsed >= 1.0:
                fps = round(frames / elapsed, 1)
                frames, t0 = 0, time.time()

            # Relay the live feed + overlays to viewer devices.
            if session_id:
                viewer_msg = {
                    "type": "frame",
                    "camera_id": camera_id,
                    "w": int(w),
                    "h": int(h),
                    "image": "data:image/jpeg;base64," + base64.b64encode(data).decode(),
                    "detections": perception.get("detections", []),
                    "hands": perception.get("hands", []),
                    "fps": fps,
                }
                await hub.broadcast(session_id, viewer_msg)
                for alert in perception.get("alerts", []):
                    await hub.broadcast(session_id, {"type": "alert", **alert})

            # Light ACK back to the camera station (no image echo).
            await ws.send_json({"type": "ack", "camera_id": camera_id, "fps": fps})
    except WebSocketDisconnect:
        return
    except Exception as exc:
        print(f"[ingest:{camera_id}] error: {exc}")
        return
