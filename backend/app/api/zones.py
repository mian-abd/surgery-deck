"""Zone polygon persistence, scoped per session + camera."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import gemini
from ..db import get_db
from ..models import ProcedureSession, Zone
from ..runtime import hub, get_pipeline
from ..schemas import ZoneBulkIn, ZoneOut

router = APIRouter()


@router.post("/sessions/{session_id}/suggest-zones")
async def suggest_zones(session_id: str, db: Session = Depends(get_db)) -> dict:
    """Ask Gemini to propose zone polygons from the session's latest frame.

    Suggestions are returned for the operator to accept or edit — nothing is
    persisted here. Returns an empty list (never an error) when Gemini is
    unavailable or no frame has arrived yet, so the UI can degrade quietly.
    """
    if not db.get(ProcedureSession, session_id):
        raise HTTPException(404, "Session not found")

    if not gemini.available():
        return {"zones": [], "reason": "Gemini not configured"}

    frame = hub.last_frame(session_id)
    if not frame:
        return {"zones": [], "reason": "No camera frame received yet"}

    zones = await gemini.suggest_zones(frame)
    if zones is None:
        return {"zones": [], "reason": "Gemini could not analyze the frame"}
    return {"zones": zones, "reason": ""}


@router.get("/sessions/{session_id}/zones", response_model=list[ZoneOut])
def list_zones(session_id: str, db: Session = Depends(get_db)) -> list[Zone]:
    return list(db.scalars(select(Zone).where(Zone.session_id == session_id)))


@router.put("/sessions/{session_id}/zones", response_model=list[ZoneOut])
def save_zones(session_id: str, body: ZoneBulkIn, db: Session = Depends(get_db)) -> list[Zone]:
    """Replace all zones for a given (session, camera)."""
    if not db.get(ProcedureSession, session_id):
        raise HTTPException(404, "Session not found")

    db.execute(
        delete(Zone).where(Zone.session_id == session_id, Zone.camera_id == body.camera_id)
    )
    saved: list[Zone] = []
    for z in body.zones:
        zone = Zone(
            session_id=session_id,
            camera_id=body.camera_id,
            name=z.name,
            zone_type=z.zone_type,
            polygon=z.polygon,
        )
        db.add(zone)
        saved.append(zone)
    db.commit()

    # Push updated zones into the live engine so rules use them immediately.
    pipeline = get_pipeline()
    if pipeline is not None:
        pipeline.set_zones(session_id, body.camera_id, [
            {"name": z.name, "zone_type": z.zone_type, "polygon": z.polygon} for z in body.zones
        ])
    return saved
