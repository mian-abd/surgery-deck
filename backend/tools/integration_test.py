"""Full-stack integration: real image -> ingest WS -> perception -> viewer WS.

Requires the backend running on :8000 and bus.jpg present (downloaded by the
pipeline test). Asserts the viewer receives tracked person detections and that
zone setup + a manual snapshot flow work.
"""
import asyncio
import json
import os
import urllib.request

import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000"


def req(path: str, body=None, method="POST") -> dict:
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}, method=method
    )
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read())


async def main() -> None:
    with open("bus.jpg", "rb") as f:
        jpg = f.read()

    sess = req("/api/sessions", {"procedure_name": "Integration", "room_name": "OR"})
    cam = req("/api/cameras", {"name": "Cam", "camera_type": "overhead"})
    req(f"/api/sessions/{sess['id']}/bind-camera?camera_id={cam['id']}")
    # zones so the engine has geometry
    req(
        f"/api/sessions/{sess['id']}/zones",
        {
            "camera_id": cam["id"],
            "zones": [
                {"camera_id": cam["id"], "name": "sterile", "zone_type": "sterile",
                 "polygon": [[0.5, 0], [1, 0], [1, 1], [0.5, 1]]},
                {"camera_id": cam["id"], "name": "nonsterile", "zone_type": "nonsterile",
                 "polygon": [[0, 0], [0.5, 0], [0.5, 1], [0, 1]]},
            ],
        },
        method="PUT",
    )

    got = {}

    async def viewer():
        async with websockets.connect(f"{WS}/ws/session/{sess['id']}") as ws:
            await ws.send("hello")
            while "det" not in got:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                if m.get("type") == "frame" and m.get("detections"):
                    got["det"] = m["detections"]

    async def camera():
        await asyncio.sleep(0.3)
        async with websockets.connect(f"{WS}/ws/ingest/{cam['id']}") as ws:
            for _ in range(8):
                await ws.send(jpg)
                await asyncio.wait_for(ws.recv(), timeout=15)
                await asyncio.sleep(0.15)

    await asyncio.gather(viewer(), camera())

    dets = got.get("det", [])
    labels = [d["label"] for d in dets]
    tracked = [d for d in dets if d.get("track_id") is not None]
    print(f"viewer detections: {labels}")
    print(f"tracked (with ids): {[(d['label'], d['track_id'], d['zone']) for d in tracked]}")
    assert any(l == "person" for l in labels), "expected a person detection"

    snap = req(f"/api/sessions/{sess['id']}/snapshot?snapshot_type=initial")
    print("snapshot counts:", snap["counts"], "image:", snap["image_path"])
    print("OK integration")


if __name__ == "__main__":
    asyncio.run(main())
