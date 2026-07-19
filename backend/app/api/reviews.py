"""Human review decisions on safety events."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import SafetyEvent
from ..schemas import EventOut, ReviewIn

router = APIRouter()

_VALID = {"confirmed", "dismissed", "unclear", "further_review"}


@router.post("/events/{event_id}/review", response_model=EventOut)
def review_event(event_id: str, body: ReviewIn, db: Session = Depends(get_db)) -> SafetyEvent:
    event = db.get(SafetyEvent, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if body.decision not in _VALID:
        raise HTTPException(422, f"decision must be one of {sorted(_VALID)}")
    event.review_status = body.decision
    event.review_note = body.note
    event.meta = {**(event.meta or {}), "reviewed_at": datetime.now(timezone.utc).isoformat()}
    db.commit()
    return event
