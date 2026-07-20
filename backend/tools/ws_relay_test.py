"""Headless end-to-end check of the camera->backend->viewer relay.

Simulates a camera station streaming a synthetic JPEG to /ws/ingest and a
viewer on /ws/session, asserting the viewer receives the relayed frame image.
Run with the backend up on 127.0.0.1:8000.
"""
import asyncio
import base64
import json
import urllib.request

import cv2
import numpy as np
import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000"


def post(path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def make_jpeg() -> bytes:
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.putText(img, "TEST FRAME", (120, 190), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)
    ok, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


async def main() -> None:
    sess = post("/api/sessions", {"procedure_name": "WS Relay Test", "room_name": "Demo OR 1"})
    cam = post("/api/cameras", {"name": "TestCam", "camera_type": "overhead"})
    post(f"/api/sessions/{sess['id']}/bind-camera?camera_id={cam['id']}")

    got = {}

    async def viewer():
        # Frames relay immediately; detections arrive on their own channel once
        # inference (lazy model load on first frame) catches up — allow more time.
        async with websockets.connect(f"{WS}/ws/session/{sess['id']}") as ws:
            await ws.send("hello")
            deadline_ok = False
            while not deadline_ok:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
                t = msg.get("type")
                if t == "frame" and "frame" not in got:
                    got["frame"] = msg
                elif t == "detections" and "detections" not in got:
                    got["detections"] = msg
                deadline_ok = "frame" in got and "detections" in got

    async def camera():
        await asyncio.sleep(0.3)  # let viewer subscribe first
        async with websockets.connect(f"{WS}/ws/ingest/{cam['id']}") as ws:
            # stream long enough for the pipeline to build + emit detections
            for _ in range(40):
                await ws.send(make_jpeg())
                await asyncio.wait_for(ws.recv(), timeout=5)  # ack
                await asyncio.sleep(0.1)

    await asyncio.gather(viewer(), camera())

    frame = got.get("frame")
    assert frame, "viewer never received a frame"
    assert frame.get("image", "").startswith("data:image/jpeg;base64,"), "no relayed image"
    raw = base64.b64decode(frame["image"].split(",", 1)[1])
    assert len(raw) > 100, "relayed image too small"
    dets = got.get("detections")
    assert dets is not None, "viewer never received a detections message (decoupled channel)"
    print(f"OK relay: viewer got frame image bytes={len(raw)}, fps={frame.get('fps')}")
    print(f"   detections channel OK: {len(dets.get('detections', []))} detection(s) in latest msg")


if __name__ == "__main__":
    asyncio.run(main())
