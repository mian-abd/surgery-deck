"""WS /ws/ingest/{camera_id}: receive JPEG frames from a camera station.

The camera station (a laptop/phone running the /capture page, or a device
streaming an uploaded video file) streams frames here. To keep the viewer feed
smooth *and* low-latency, the three costs are decoupled:

  * **Receive + relay** — every received frame's JPEG is immediately relayed to
    the session's viewer devices (``type: "frame"``). This runs on the event
    loop but does no decoding/inference, so it sustains a high frame rate.
  * **Inference** — a per-connection worker task decodes + runs the perception
    pipeline in a *thread* (``asyncio.to_thread``) so it never blocks the event
    loop, and it only ever processes the **latest** frame (stale frames are
    dropped). This bounds latency regardless of how slow CPU inference is.
  * **Detections** — when inference finishes, boxes/hands are broadcast
    separately (``type: "detections"``) and any new alerts as ``type: "alert"``.

The net effect: viewers see smooth video at the ingest rate, with detection
overlays that update as fast as inference can keep up — and never a growing lag.
"""
from __future__ import annotations

import asyncio
import base64
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..runtime import decode_jpeg, get_pipeline, hub

router = APIRouter()


def _decode_and_process(pipeline, session_id: str, camera_id: str, data: bytes) -> dict | None:
    """Runs in a worker thread: JPEG decode + full perception pipeline."""
    frame = decode_jpeg(data)
    if frame is None:
        return None
    return pipeline.process(session_id, camera_id, frame)


@router.websocket("/ws/ingest/{camera_id}")
async def ingest(ws: WebSocket, camera_id: str) -> None:
    await ws.accept()
    session_id = hub.session_for_camera(camera_id)

    # Latest-frame slot handed from the receive loop to the inference worker.
    latest: dict[str, bytes | None] = {"data": None}
    have_frame = asyncio.Event()
    stop = asyncio.Event()

    async def worker() -> None:
        pipeline = get_pipeline()
        while not stop.is_set():
            await have_frame.wait()
            have_frame.clear()
            data = latest["data"]
            latest["data"] = None
            if data is None:
                continue
            sid = hub.session_for_camera(camera_id) or session_id
            if pipeline is None or not sid:
                continue
            try:
                perception = await asyncio.to_thread(
                    _decode_and_process, pipeline, sid, camera_id, data
                )
            except Exception as exc:  # inference must never kill the socket
                print(f"[ingest:{camera_id}] inference error: {exc}")
                continue
            if not perception:
                continue
            await hub.broadcast(
                sid,
                {
                    "type": "detections",
                    "camera_id": camera_id,
                    "detections": perception.get("detections", []),
                    "hands": perception.get("hands", []),
                },
            )
            for alert in perception.get("alerts", []):
                await hub.broadcast(sid, {"type": "alert", **alert})

    task = asyncio.create_task(worker())

    frames = 0
    fps = 0.0
    t0 = time.time()
    try:
        while True:
            data = await ws.receive_bytes()
            # Cheap header peek for dimensions; full decode happens in the worker.
            frames += 1
            session_id = session_id or hub.session_for_camera(camera_id)

            elapsed = time.time() - t0
            if elapsed >= 1.0:
                fps = round(frames / elapsed, 1)
                frames, t0 = 0, time.time()

            # Relay the raw frame to viewers immediately (smooth, high fps).
            if session_id:
                hub.remember_frame(session_id, data)  # for Gemini zone hints
                await hub.broadcast(
                    session_id,
                    {
                        "type": "frame",
                        "camera_id": camera_id,
                        "image": "data:image/jpeg;base64," + base64.b64encode(data).decode(),
                        "fps": fps,
                    },
                )

            # Hand the newest frame to the worker, dropping any unprocessed one.
            latest["data"] = data
            have_frame.set()

            # Light ACK back to the camera station (no image echo).
            await ws.send_json({"type": "ack", "camera_id": camera_id, "fps": fps})
    except WebSocketDisconnect:
        return
    except Exception as exc:
        print(f"[ingest:{camera_id}] error: {exc}")
        return
    finally:
        stop.set()
        have_frame.set()  # wake the worker so it can observe stop
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            task.cancel()
