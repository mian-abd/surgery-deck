"""Perception + engine orchestration.

Holds a shared detector/hand model, a ByteTrack per camera, and a SessionWorld
per session. ``process`` runs a single frame end to end and returns overlay data
+ any new safety alerts (which are also persisted with an evidence frame).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from .. import gemini
from ..config import settings
from ..db import SessionLocal
from ..engine.events import evaluate_hygiene, evaluate_instruments
from ..engine.state import NON_INSTRUMENT, SessionWorld
from ..engine.zones import ZoneDef
from ..models import InstrumentSnapshot, SafetyEvent
from ..storage import save_evidence
from .detector import build_detector
from .hands import HandDetector
from .tracker import ByteTracker


class Pipeline:
    def __init__(self) -> None:
        self.detector = build_detector()
        try:
            self.hand_detector: HandDetector | None = HandDetector()
        except Exception as exc:
            print(f"[pipeline] hands unavailable: {exc}")
            self.hand_detector = None

        self.trackers: dict[str, ByteTracker] = {}
        self.worlds: dict[str, SessionWorld] = {}
        self._frame_idx: dict[str, int] = {}
        self._cached_dets: dict[str, list] = {}

    # --- world / zones ---
    def world(self, session_id: str) -> SessionWorld:
        w = self.worlds.get(session_id)
        if w is None:
            w = SessionWorld(settings.hygiene_min_dwell_sec, settings.hygiene_window_sec)
            self.worlds[session_id] = w
        return w

    def set_zones(self, session_id: str, camera_id: str, zones: list[dict]) -> None:
        defs = [ZoneDef(z["name"], z["zone_type"], z["polygon"]) for z in zones]
        self.world(session_id).set_zones(camera_id, defs)

    def _tracker(self, camera_id: str) -> ByteTracker:
        t = self.trackers.get(camera_id)
        if t is None:
            t = ByteTracker()
            self.trackers[camera_id] = t
        return t

    # --- main per-frame entry ---
    def process(self, session_id: str, camera_id: str, frame) -> dict:
        world = self.world(session_id)
        world.last_frame_by_camera[camera_id] = frame
        H, W = frame.shape[:2]

        # detector every Nth frame; tracker still runs every frame
        idx = self._frame_idx.get(camera_id, 0) + 1
        self._frame_idx[camera_id] = idx
        every = max(1, settings.detect_every_n)
        if idx % every == 0 or camera_id not in self._cached_dets:
            raw = self.detector.detect(frame)
            self._cached_dets[camera_id] = raw
        else:
            raw = self._cached_dets[camera_id]

        tracked = self._tracker(camera_id).update(raw, (H, W))

        # split into instruments vs persons, with normalized centers
        instruments, persons = [], []
        for d in tracked:
            cx, cy = d.center
            n = {"track_id": d.track_id, "label": d.label, "cx": cx / W, "cy": cy / H}
            if d.label == "person":
                persons.append(n)
            elif d.label not in NON_INSTRUMENT:
                instruments.append(n)

        hands_raw: list[list[dict]] = []
        hand_centers: list[dict] = []
        if self.hand_detector is not None:
            hands_raw = self.hand_detector.detect(frame)
            hand_centers = HandDetector.centers(hands_raw)

        # run safety rules (mutates world + tags instrument state)
        descriptors = evaluate_instruments(world, camera_id, instruments)
        descriptors += evaluate_hygiene(world, camera_id, persons, hand_centers)

        alerts = self._persist(session_id, camera_id, frame, descriptors)

        # overlay payload for the viewer
        state_by_tid = {t.track_id: t.state for t in world.tracks.values()}
        zones = world.zones(camera_id)
        detections = []
        for d in tracked:
            cx, cy = d.center
            zone = zones.locate(cx / W, cy / H)
            detections.append(
                {
                    "bbox": [round(v, 1) for v in d.bbox],
                    "label": d.label,
                    "track_id": d.track_id,
                    "conf": round(d.conf, 2),
                    "zone": zone.zone_type if zone else None,
                    "state": state_by_tid.get(d.track_id) if d.label not in NON_INSTRUMENT else None,
                }
            )

        return {"detections": detections, "hands": hands_raw, "alerts": alerts}

    # --- snapshots / counts ---
    def snapshot_counts(self, session_id: str) -> tuple[dict, str | None]:
        world = self.world(session_id)
        counts = world.current_counts()
        image_path = None
        if world.last_frame_by_camera:
            frame = next(iter(world.last_frame_by_camera.values()))
            image_path = save_evidence(frame, prefix="snapshot")
        return counts, image_path

    def check_count_mismatch(self, db, session_id: str) -> list[dict]:
        def latest(kind: str):
            return db.scalars(
                select(InstrumentSnapshot)
                .where(
                    InstrumentSnapshot.session_id == session_id,
                    InstrumentSnapshot.snapshot_type == kind,
                )
                .order_by(InstrumentSnapshot.captured_at.desc())
            ).first()

        initial, final = latest("initial"), latest("final")
        if not initial or not final:
            return []
        ini, fin = initial.counts or {}, final.counts or {}
        missing = {
            k: ini.get(k, 0) - fin.get(k, 0)
            for k in set(ini) | set(fin)
            if ini.get(k, 0) - fin.get(k, 0) > 0
        }
        if not missing:
            return []
        desc = ", ".join(f"{v} {k}" for k, v in missing.items())
        event = SafetyEvent(
            session_id=session_id,
            event_type="count_mismatch",
            severity="critical",
            title="Instrument count mismatch",
            description=f"Possible missing item(s): {desc}. Requires review — not proof of a "
            f"retained instrument.",
            confidence=0.9,
            evidence_path=final.image_path,
            meta={"initial": ini, "final": fin, "missing": missing},
        )
        db.add(event)
        db.commit()
        return [_alert_dict(event)]

    # --- persistence ---
    def _persist(self, session_id: str, camera_id: str, frame, descriptors: list[dict]) -> list[dict]:
        if not descriptors:
            return []
        alerts: list[dict] = []
        db = SessionLocal()
        try:
            for d in descriptors:
                evidence = None
                try:
                    evidence = save_evidence(frame, prefix=d["event_type"])
                except Exception as exc:
                    print(f"[pipeline] evidence save failed: {exc}")
                event = SafetyEvent(
                    session_id=session_id,
                    camera_id=camera_id,
                    event_type=d["event_type"],
                    severity=d["severity"],
                    title=d["title"],
                    description=d.get("description", ""),
                    confidence=d.get("confidence", 0.0),
                    evidence_path=evidence,
                    meta=d.get("meta", {}),
                )
                db.add(event)
                db.commit()
                alerts.append(_alert_dict(event))

                # Gemini narration + visual second opinion, in the background so
                # the realtime loop is never blocked. No-op without an API key.
                gemini.enrich_event_bg(
                    event.id,
                    session_id,
                    {
                        "event_type": event.event_type,
                        "severity": event.severity,
                        "title": event.title,
                        "rule_description": event.description,
                        "rule_confidence": event.confidence,
                        "camera_id": camera_id,
                        "detail": d.get("meta", {}),
                    },
                    _jpeg_of(frame),
                )
        finally:
            db.close()
        return alerts


def _jpeg_of(frame) -> bytes | None:
    """Encode a BGR frame to JPEG bytes for Gemini. None on failure."""
    try:
        import cv2

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return buf.tobytes() if ok else None
    except Exception:
        return None


def _alert_dict(event: SafetyEvent) -> dict:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "severity": event.severity,
        "title": event.title,
        "description": event.description,
        "confidence": event.confidence,
        "evidence_path": event.evidence_path,
        "occurred_at": (event.occurred_at or datetime.now(timezone.utc)).isoformat(),
    }
