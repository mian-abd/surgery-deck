"""End-to-end: start the demo, watch for a safety alert, then confirm Gemini
enrichment arrives over the SAME session WebSocket as an `event_update`.

This is the test that proves the whole loop a judge will watch on screen:
rule engine fires -> event persisted -> Gemini analyses the evidence frame ->
dashboard is patched live.
"""
import asyncio
import json
import urllib.request

import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000"


def req(path, body=None, method="POST"):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}, method=method
    )
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read())


async def main() -> int:
    sess = req("/api/sessions", {"procedure_name": "Gemini E2E", "room_name": "Demo OR 1"})
    sid = sess["id"]
    print(f"session {sid}")

    alerts, updates = [], []

    async def viewer():
        async with websockets.connect(f"{WS}/ws/session/{sid}", max_size=None) as ws:
            await ws.send("hello")
            # demo fires its first persisted alert ~10s in; Gemini needs a few
            # seconds more, so give the loop room.
            deadline = asyncio.get_event_loop().time() + 90
            while asyncio.get_event_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                except asyncio.TimeoutError:
                    continue
                m = json.loads(raw)
                if m.get("type") == "alert":
                    alerts.append(m)
                    print(f"  ALERT  {m['severity']:<11} {m['title'][:60]}")
                elif m.get("type") == "event_update":
                    updates.append(m)
                    g = m.get("gemini", {})
                    print(f"  GEMINI  agrees={g.get('agrees')} conf={g.get('visual_confidence')}")
                    print(f"     explanation: {str(g.get('explanation'))[:110]}")
                    print(f"     action:      {str(g.get('recommended_action'))[:110]}")
                    return  # one enriched event is enough to prove the loop

    req(f"/api/sessions/{sid}/demo/start")
    print("demo started; waiting for an alert + its Gemini enrichment...")
    try:
        await viewer()
    finally:
        try:
            req(f"/api/sessions/{sid}/demo/stop")
        except Exception:
            pass

    print(f"\nalerts={len(alerts)} gemini_updates={len(updates)}")
    if not alerts:
        print("FAIL: no alerts fired")
        return 1
    if not updates:
        print("FAIL: alerts fired but no Gemini enrichment arrived")
        return 1

    # report summary
    rep = req(f"/api/sessions/{sid}/report", method="GET")
    summary = rep.get("gemini_summary")
    print(f"\nreport gemini_summary: {str(summary)[:200]}")
    if not summary:
        print("FAIL: report has no Gemini summary")
        return 1

    print("\nE2E OK — alert -> Gemini enrichment -> live push -> report summary")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
