"""Human review decisions on safety events."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import SafetyEvent
from ..schemas import EventOut, ReviewIn, ReviewSummary

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
    db.refresh(event)
    return event


@router.get("/sessions/{session_id}/reviews", response_model=list[EventOut])
def list_reviewed_events(session_id: str, db: Session = Depends(get_db)) -> list[SafetyEvent]:
    """Events that have received a human decision (status != pending)."""
    return list(
        db.scalars(
            select(SafetyEvent)
            .where(
                SafetyEvent.session_id == session_id,
                SafetyEvent.review_status != "pending",
            )
            .order_by(SafetyEvent.occurred_at.desc())
        )
    )


@router.get("/sessions/{session_id}/reviews/summary", response_model=ReviewSummary)
def review_summary(session_id: str, db: Session = Depends(get_db)) -> ReviewSummary:
    """Aggregate decision tally for a session (report + review dashboards)."""
    events = list(
        db.scalars(select(SafetyEvent).where(SafetyEvent.session_id == session_id))
    )
    return ReviewSummary(
        confirmed=sum(1 for e in events if e.review_status == "confirmed"),
        dismissed=sum(1 for e in events if e.review_status == "dismissed"),
        unclear=sum(
            1 for e in events if e.review_status in ("unclear", "further_review")
        ),
        pending=sum(1 for e in events if e.review_status == "pending"),
        total=len(events),
    )
