"""Stream a real image repeatedly into a specific existing session/camera so a
browser Monitor tab watching that session can be observed updating live.
"""
import asyncio
import json
import sys
import urllib.request

import websockets

SESSION_ID = sys.argv[1]
BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000"


def post(path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


async def main():
    with open("bus.jpg", "rb") as f:
        jpg = f.read()

    cam = post("/api/cameras", {"name": "LiveDemoCam", "camera_type": "overhead"})
    post(f"/api/sessions/{SESSION_ID}/bind-camera?camera_id={cam['id']}")
    print(f"bound camera {cam['id']} to session {SESSION_ID}")

    async with websockets.connect(f"{WS}/ws/ingest/{cam['id']}") as ws:
        for i in range(40):
            await ws.send(jpg)
            ack = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if i % 10 == 0:
                print(f"frame {i}: ack fps={ack.get('fps')}")
            await asyncio.sleep(0.2)
    print("done streaming")


if __name__ == "__main__":
    asyncio.run(main())
