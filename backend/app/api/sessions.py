"""Session lifecycle, cameras, snapshots, and the end-of-session report."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..engine.report import build_report
from ..models import Camera, ProcedureSession, SafetyEvent, InstrumentSnapshot
from ..runtime import hub, get_pipeline
from ..schemas import (
    CameraCreate,
    CameraOut,
    EventOut,
    ReportOut,
    SessionCreate,
    SessionOut,
    SnapshotOut,
)

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Cameras ---
@router.post("/cameras", response_model=CameraOut)
def create_camera(body: CameraCreate, db: Session = Depends(get_db)) -> Camera:
    cam = Camera(name=body.name, camera_type=body.camera_type)
    db.add(cam)
    db.commit()
    return cam


@router.get("/cameras", response_model=list[CameraOut])
def list_cameras(db: Session = Depends(get_db)) -> list[Camera]:
    return list(db.scalars(select(Camera)))


# --- Sessions ---
@router.post("/sessions", response_model=SessionOut)
def create_session(body: SessionCreate, db: Session = Depends(get_db)) -> ProcedureSession:
    sess = ProcedureSession(
        procedure_name=body.procedure_name,
        room_name=body.room_name,
        status="active",
        started_at=_now(),
    )
    db.add(sess)
    db.commit()
    return sess


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db)) -> list[ProcedureSession]:
    return list(db.scalars(select(ProcedureSession).order_by(ProcedureSession.created_at.desc())))


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: str, db: Session = Depends(get_db)) -> ProcedureSession:
    sess = db.get(ProcedureSession, session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    return sess


@router.post("/sessions/{session_id}/bind-camera")
def bind_camera(session_id: str, camera_id: str, db: Session = Depends(get_db)) -> dict:
    if not db.get(ProcedureSession, session_id):
        raise HTTPException(404, "Session not found")
    hub.bind_camera(camera_id, session_id)
    return {"ok": True, "camera_id": camera_id, "session_id": session_id}


@router.post("/sessions/{session_id}/end", response_model=SessionOut)
def end_session(session_id: str, db: Session = Depends(get_db)) -> ProcedureSession:
    sess = db.get(ProcedureSession, session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    sess.status = "review"
    sess.ended_at = _now()
    db.commit()
    return sess


# --- Events (read) ---
@router.get("/sessions/{session_id}/events", response_model=list[EventOut])
def list_events(session_id: str, db: Session = Depends(get_db)) -> list[SafetyEvent]:
    return list(
        db.scalars(
            select(SafetyEvent)
            .where(SafetyEvent.session_id == session_id)
            .order_by(SafetyEvent.occurred_at.desc())
        )
    )


# --- Snapshots ---
@router.post("/sessions/{session_id}/snapshot", response_model=SnapshotOut)
async def capture_snapshot(
    session_id: str, snapshot_type: str = "initial", db: Session = Depends(get_db)
) -> InstrumentSnapshot:
    """Capture current instrument counts from the live world model.

    Counts come from the perception pipeline's per-session state when available;
    otherwise an empty snapshot is recorded (still lets the demo flow proceed).
    On a ``final`` snapshot the count-mismatch rule runs against the initial one.
    """
    if not db.get(ProcedureSession, session_id):
        raise HTTPException(404, "Session not found")

    counts: dict[str, int] = {}
    image_path = None
    pipeline = get_pipeline()
    if pipeline is not None:
        counts, image_path = pipeline.snapshot_counts(session_id)

    snap = InstrumentSnapshot(
        session_id=session_id,
        snapshot_type=snapshot_type,
        total_count=sum(counts.values()),
        counts=counts,
        image_path=image_path,
    )
    db.add(snap)
    db.commit()

    if snapshot_type == "final" and pipeline is not None:
        for alert in pipeline.check_count_mismatch(db, session_id):
            await hub.broadcast(session_id, {"type": "alert", **alert})
    return snap


@router.get("/sessions/{session_id}/snapshots", response_model=list[SnapshotOut])
def list_snapshots(session_id: str, db: Session = Depends(get_db)) -> list[InstrumentSnapshot]:
    return list(
        db.scalars(
            select(InstrumentSnapshot)
            .where(InstrumentSnapshot.session_id == session_id)
            .order_by(InstrumentSnapshot.captured_at)
        )
    )


# --- Report ---
@router.get("/sessions/{session_id}/report", response_model=ReportOut)
def get_report(session_id: str, db: Session = Depends(get_db)) -> ReportOut:
    sess = db.get(ProcedureSession, session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    return build_report(db, sess)
