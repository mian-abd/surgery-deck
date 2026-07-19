"""Zone polygon persistence, scoped per session + camera."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ProcedureSession, Zone
from ..runtime import hub, get_pipeline
from ..schemas import ZoneBulkIn, ZoneOut

router = APIRouter()


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
