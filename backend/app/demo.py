"""Self-contained live-demo simulator.

Drives the *real* dashboard with a scripted operating-room scene so the product
can be shown on a single laptop with no camera, no props, and no second device.
It renders synthetic frames with OpenCV and broadcasts the exact same
``frame`` / ``detections`` / ``alert`` WebSocket messages a real camera pipeline
would (see ``ws/ingest.py``), so the Monitor page lights up unchanged. Safety
events + instrument snapshots are persisted to the DB, so Review and Report
populate with real rows — nothing about the dashboard is mocked, only the feed.

Timeline (≈50 s, then loops; DB rows written once):
  t≈4   initial count captured (6 instruments)
  t≈10  hand hygiene observed (Staff-01 dwells at the sink)
  t≈18  hand-hygiene noncompliance (Staff-02 enters sterile directly)  [warning]
  t≈26  sterile breach: a clamp is moved onto the nonsterile table      [warning]
  t≈34  contamination: that clamp is returned to the sterile field      [critical]
  t≈44  final count (5) → count mismatch: 1 forceps unaccounted for     [critical]
"""
from __future__ import annotations

import asyncio
import base64
import random
import time
from datetime import datetime, timezone

import cv2
import numpy as np

from . import gemini
from .db import SessionLocal
from .models import Camera, InstrumentSnapshot, ProcedureSession, SafetyEvent, Zone
from .runtime import hub
from .storage import save_evidence

# --- frame + scene geometry -------------------------------------------------
W, H = 960, 540
CYCLE = 50.0
FPS = 10

# Zones as normalized rects (x0, y0, x1, y1). Kept non-overlapping so a point
# maps to exactly one zone. Rendered as OR "furniture" and seeded into the DB
# so the overlay draws matching outlines on top.
ZONES = [
    ("sink", "Sink", 0.03, 0.06, 0.24, 0.30),
    ("tray", "Instrument tray", 0.29, 0.48, 0.56, 0.90),
    ("sterile", "Sterile field", 0.60, 0.16, 0.97, 0.92),
    ("nonsterile", "Non-sterile table", 0.03, 0.55, 0.26, 0.95),
]
_ZONE_FILL = {  # BGR furniture colors
    "sink": (95, 92, 88),
    "tray": (125, 125, 128),
    "sterile": (150, 112, 74),
    "nonsterile": (78, 92, 108),
}

# Six instruments, home positions on the tray (normalized).
INSTRUMENTS = [
    (1, "forceps", 0.34, 0.58),
    (2, "forceps", 0.34, 0.78),
    (3, "scissors", 0.42, 0.58),
    (4, "scissors", 0.42, 0.78),
    (5, "clamp", 0.50, 0.58),
    (6, "scalpel", 0.50, 0.78),
]
INITIAL_COUNTS = {"forceps": 2, "scissors": 2, "clamp": 1, "scalpel": 1}
FINAL_COUNTS = {"forceps": 1, "scissors": 2, "clamp": 1, "scalpel": 1}

_tasks: dict[str, asyncio.Task] = {}
_cameras: dict[str, str] = {}


# --- geometry helpers -------------------------------------------------------
def _lerp(a: float, b: float, f: float) -> float:
    f = max(0.0, min(1.0, f))
    return a + (b - a) * f


def _zone_of(cx: float, cy: float) -> str | None:
    for ztype, _name, x0, y0, x1, y1 in ZONES:
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            return ztype
    return None


def _px(cx: float, cy: float) -> tuple[int, int]:
    return int(cx * W), int(cy * H)


# --- scene at time t --------------------------------------------------------
def _scene_at(t: float) -> dict:
    """Return the objects, detections, and hands for the frame at time ``t``."""
    objs: list[dict] = []          # for rendering
    hands: list[list[dict]] = []

    forceps2_gone = t >= 38.0

    # clamp #5 trajectory: tray -> nonsterile table -> back into sterile field
    if t < 22:
        clamp = (0.50, 0.58)
    elif t < 30:
        clamp = (_lerp(0.50, 0.14, (t - 22) / 8), _lerp(0.58, 0.75, (t - 22) / 8))
    elif t < 36:
        clamp = (_lerp(0.14, 0.70, (t - 30) / 6), _lerp(0.75, 0.60, (t - 30) / 6))
    else:
        clamp = (0.70, 0.60)
    clamp_contaminated = t >= 26.0  # touched nonsterile at ~t=26

    for tid, label, hx, hy in INSTRUMENTS:
        if tid == 2 and forceps2_gone:
            continue
        if tid == 5:
            cx, cy = clamp
            state = "potentially_contaminated" if clamp_contaminated else "sterile"
        else:
            # gentle idle jitter so the feed reads as live
            cx = hx + random.uniform(-0.004, 0.004)
            cy = hy + random.uniform(-0.004, 0.004)
            state = "sterile"
        objs.append({"kind": "instrument", "label": label, "track_id": tid,
                     "cx": cx, "cy": cy, "state": state})

    # Staff-01: dwells at the sink (hygiene), then walks toward the field.
    if 5 <= t < 12:
        objs.append({"kind": "person", "label": "Staff-01", "cx": 0.13, "cy": 0.24})
        hands = [[{"x": 0.09 + random.uniform(-0.02, 0.02) + 0.03 * (i % 3),
                   "y": 0.16 + random.uniform(-0.02, 0.02) + 0.02 * (i // 3)}
                  for i in range(8)]]
    elif 12 <= t < 16:
        f = (t - 12) / 4
        objs.append({"kind": "person", "label": "Staff-01",
                     "cx": _lerp(0.13, 0.62, f), "cy": _lerp(0.24, 0.46, f)})

    # Staff-02: enters the sterile field directly (no sink dwell) -> violation.
    if 16 <= t < 26:
        f = (t - 16) / 8
        objs.append({"kind": "person", "label": "Staff-02",
                     "cx": _lerp(0.66, 0.80, f), "cy": _lerp(0.95, 0.44, f)})

    detections = []
    for o in objs:
        cx, cy = o["cx"], o["cy"]
        x, y = _px(cx, cy)
        if o["kind"] == "instrument":
            hw, hh = 44, 13
        else:
            hw, hh = 46, 82
        detections.append({
            "bbox": [x - hw, y - hh, x + hw, y + hh],
            "label": o["label"] if o["kind"] == "instrument" else "person",
            "track_id": o["track_id"] if o["kind"] == "instrument" else None,
            "conf": round(random.uniform(0.82, 0.96), 2),
            "zone": _zone_of(cx, cy),
            "state": o.get("state"),
        })

    return {"objects": objs, "detections": detections, "hands": hands}


# --- rendering --------------------------------------------------------------
def _render(scene: dict, t: float) -> np.ndarray:
    img = np.full((H, W, 3), (52, 50, 56), dtype=np.uint8)

    # OR furniture (aligned to the zones so overlay outlines frame them).
    for ztype, _name, x0, y0, x1, y1 in ZONES:
        p0, p1 = _px(x0, y0), _px(x1, y1)
        cv2.rectangle(img, p0, p1, _ZONE_FILL[ztype], -1)
        cv2.rectangle(img, p0, p1, (28, 28, 32), 2)
    # a faucet hint over the sink
    sx, sy = _px(0.135, 0.06)
    cv2.rectangle(img, (sx - 3, sy), (sx + 3, sy + 26), (60, 60, 66), -1)

    for o in scene["objects"]:
        x, y = _px(o["cx"], o["cy"])
        if o["kind"] == "instrument":
            steel = (205, 205, 210)
            cv2.rectangle(img, (x - 42, y - 8), (x + 42, y + 8), steel, -1)
            cv2.rectangle(img, (x - 42, y - 8), (x + 42, y + 8), (120, 120, 125), 1)
            cv2.line(img, (x - 30, y), (x + 30, y), (150, 150, 155), 1)
        else:  # person in scrubs
            cv2.circle(img, (x, y - 60), 20, (120, 150, 110), -1)   # head
            cv2.rectangle(img, (x - 34, y - 40), (x + 34, y + 78), (110, 140, 95), -1)  # body
            cv2.putText(img, o["label"], (x - 34, y - 78),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 230, 235), 1, cv2.LINE_AA)

    for hand in scene["hands"]:
        for p in hand:
            cv2.circle(img, _px(p["x"], p["y"]), 4, (200, 120, 240), -1)

    # subtle timecode so it reads as a live feed
    cv2.putText(img, datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
                (12, H - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 185), 1, cv2.LINE_AA)
    return img


def _encode(img: np.ndarray) -> str:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 72])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


# --- persistence beats ------------------------------------------------------
def _persist_event(session_id, camera_id, event_type, severity, title, desc,
                   conf, frame) -> dict:
    """Write a SafetyEvent (+evidence frame) and return its alert dict."""
    evidence = None
    try:
        evidence = save_evidence(frame, prefix=event_type)
    except Exception as exc:  # evidence is best-effort; never break the demo
        print(f"[demo] evidence save failed: {exc}")
    db = SessionLocal()
    try:
        ev = SafetyEvent(
            session_id=session_id, camera_id=camera_id, event_type=event_type,
            severity=severity, title=title, description=desc, confidence=conf,
            evidence_path=evidence, occurred_at=datetime.now(timezone.utc),
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)
        alert = {"id": ev.id, "event_type": event_type, "severity": severity,
                 "title": title, "description": desc, "confidence": conf,
                 "evidence_path": evidence,
                 "occurred_at": ev.occurred_at.isoformat()}
    finally:
        db.close()

    # Gemini narration + visual second opinion, in the background. The demo
    # feed is synthetic but the event rows are real, so the enrichment is too.
    gemini.enrich_event_bg(
        alert["id"], session_id,
        {"event_type": event_type, "severity": severity, "title": title,
         "rule_description": desc, "rule_confidence": conf,
         "camera_id": camera_id, "scene": "simulated operating-room demo feed"},
        _jpeg_bytes(frame),
    )
    return alert


def _jpeg_bytes(img: np.ndarray) -> bytes | None:
    try:
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return buf.tobytes() if ok else None
    except Exception:
        return None


def _persist_snapshot(session_id, snapshot_type, counts, frame) -> None:
    image_path = None
    try:
        image_path = save_evidence(frame, prefix=f"snapshot_{snapshot_type}")
    except Exception:
        pass
    db = SessionLocal()
    try:
        db.add(InstrumentSnapshot(
            session_id=session_id, snapshot_type=snapshot_type,
            total_count=sum(counts.values()), counts=dict(counts),
            image_path=image_path))
        db.commit()
    finally:
        db.close()


async def _fire(session_id, camera_id, frame, name, persist) -> None:
    """Emit one scripted beat: broadcast an alert (and persist on first cycle)."""
    if name == "initial_count":
        if persist:
            _persist_snapshot(session_id, "initial", INITIAL_COUNTS, frame)
        alert = {"event_type": "info", "severity": "information",
                 "title": "Initial instrument count captured: 6 instruments",
                 "description": "2 forceps, 2 scissors, 1 clamp, 1 scalpel on the tray.",
                 "confidence": 1.0}
    elif name == "hygiene_ok":
        alert = (_persist_event(session_id, camera_id, "hygiene_ok", "information",
                                "Hand hygiene observed — Staff-01",
                                "Hands dwelled in the sink zone with rubbing motion before entry.",
                                0.8, frame) if persist
                 else {"event_type": "hygiene_ok", "severity": "information",
                       "title": "Hand hygiene observed — Staff-01",
                       "description": "Hands dwelled in the sink zone with rubbing motion before entry.",
                       "confidence": 0.8})
    elif name == "hygiene_missing":
        alert = (_persist_event(session_id, camera_id, "hygiene_missing", "warning",
                                "Possible hand-hygiene noncompliance — Staff-02",
                                "A participant entered the sterile field with no hand-hygiene event detected. Review video.",
                                0.82, frame) if persist
                 else {"event_type": "hygiene_missing", "severity": "warning",
                       "title": "Possible hand-hygiene noncompliance — Staff-02",
                       "description": "A participant entered the sterile field with no hand-hygiene event detected. Review video.",
                       "confidence": 0.82})
    elif name == "breach_warning":
        alert = (_persist_event(session_id, camera_id, "sterile_breach", "warning",
                                "clamp #5 touched a nonsterile surface",
                                "Instrument entered a designated nonsterile zone and is now potentially contaminated.",
                                0.85, frame) if persist
                 else {"event_type": "sterile_breach", "severity": "warning",
                       "title": "clamp #5 touched a nonsterile surface",
                       "description": "Instrument entered a designated nonsterile zone and is now potentially contaminated.",
                       "confidence": 0.85})
    elif name == "breach_critical":
        alert = (_persist_event(session_id, camera_id, "sterile_breach", "critical",
                                "Possible sterile-field contamination: clamp #5",
                                "A potentially contaminated instrument re-entered the sterile field. Requires immediate review.",
                                0.9, frame) if persist
                 else {"event_type": "sterile_breach", "severity": "critical",
                       "title": "Possible sterile-field contamination: clamp #5",
                       "description": "A potentially contaminated instrument re-entered the sterile field. Requires immediate review.",
                       "confidence": 0.9})
    elif name == "count_mismatch":
        if persist:
            _persist_snapshot(session_id, "final", FINAL_COUNTS, frame)
        alert = (_persist_event(session_id, camera_id, "count_mismatch", "critical",
                                "Count mismatch: 1 forceps unaccounted for",
                                "Final count (5) is one below the initial count (6). Locate the missing forceps before closing.",
                                0.88, frame) if persist
                 else {"event_type": "count_mismatch", "severity": "critical",
                       "title": "Count mismatch: 1 forceps unaccounted for",
                       "description": "Final count (5) is one below the initial count (6). Locate the missing forceps before closing.",
                       "confidence": 0.88})
    else:
        return
    await hub.broadcast(session_id, {"type": "alert", **alert})


# (trigger time, beat name) — fired once per cycle in order.
BEATS = [
    (4.0, "initial_count"),
    (10.0, "hygiene_ok"),
    (18.0, "hygiene_missing"),
    (26.0, "breach_warning"),
    (34.0, "breach_critical"),
    (44.0, "count_mismatch"),
]


async def _run(session_id: str, camera_id: str) -> None:
    persisted = False
    interval = 1.0 / FPS
    try:
        while True:
            cycle_start = time.monotonic()
            fired: set[int] = set()
            while True:
                t = time.monotonic() - cycle_start
                if t >= CYCLE:
                    break
                scene = _scene_at(t)
                frame = _render(scene, t)
                jpeg = _jpeg_bytes(frame)
                if jpeg:
                    hub.remember_frame(session_id, jpeg)  # for Gemini zone hints
                await hub.broadcast(session_id, {
                    "type": "frame", "camera_id": camera_id,
                    "image": _encode(frame), "fps": FPS})
                await hub.broadcast(session_id, {
                    "type": "detections", "camera_id": camera_id,
                    "detections": scene["detections"], "hands": scene["hands"]})
                for i, (bt, name) in enumerate(BEATS):
                    if t >= bt and i not in fired:
                        fired.add(i)
                        await _fire(session_id, camera_id, frame, name,
                                    persist=not persisted)
                await asyncio.sleep(interval)
            persisted = True  # DB rows written once; feed keeps looping live
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # a demo crash must not take down the server
        print(f"[demo:{session_id}] error: {exc}")


def _seed_camera_and_zones(session_id: str) -> str:
    """Create the demo camera, bind it, seed zones, mark the session active."""
    db = SessionLocal()
    try:
        cam = Camera(name="Demo Camera", camera_type="overhead")
        db.add(cam)
        db.commit()
        db.refresh(cam)
        camera_id = cam.id

        # replace any existing zones for this camera, then seed the demo set
        db.query(Zone).filter(Zone.session_id == session_id,
                              Zone.camera_id == camera_id).delete()
        for ztype, name, x0, y0, x1, y1 in ZONES:
            db.add(Zone(session_id=session_id, camera_id=camera_id, name=name,
                        zone_type=ztype,
                        polygon=[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]))

        sess = db.get(ProcedureSession, session_id)
        if sess and sess.status == "setup":
            sess.status = "active"
        if sess and not sess.started_at:
            sess.started_at = datetime.now(timezone.utc)
        db.commit()
        return camera_id
    finally:
        db.close()


async def start(session_id: str) -> str:
    """Start (or return the already-running) demo for a session."""
    if session_id in _tasks and not _tasks[session_id].done():
        return _cameras.get(session_id, "")
    camera_id = _seed_camera_and_zones(session_id)
    hub.bind_camera(camera_id, session_id)
    _cameras[session_id] = camera_id
    _tasks[session_id] = asyncio.create_task(_run(session_id, camera_id))
    return camera_id


async def stop(session_id: str) -> None:
    task = _tasks.pop(session_id, None)
    _cameras.pop(session_id, None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
