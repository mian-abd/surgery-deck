"""End-of-session safety report (PRD 7.9). Pure DB read + aggregation."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import InstrumentSnapshot, ProcedureSession, SafetyEvent
from ..schemas import EventOut, ReportOut, SessionOut


def _counts_of(db: Session, session_id: str, snapshot_type: str) -> dict:
    snap = db.scalars(
        select(InstrumentSnapshot)
        .where(
            InstrumentSnapshot.session_id == session_id,
            InstrumentSnapshot.snapshot_type == snapshot_type,
        )
        .order_by(InstrumentSnapshot.captured_at.desc())
    ).first()
    return dict(snap.counts) if snap and snap.counts else {}


def build_report(db: Session, sess: ProcedureSession) -> ReportOut:
    events = list(
        db.scalars(select(SafetyEvent).where(SafetyEvent.session_id == sess.id))
    )

    initial = _counts_of(db, sess.id, "initial")
    final = _counts_of(db, sess.id, "final")
    all_keys = set(initial) | set(final)
    difference = {
        k: initial.get(k, 0) - final.get(k, 0)
        for k in all_keys
        if initial.get(k, 0) - final.get(k, 0) != 0
    }

    hygiene_events = sum(1 for e in events if e.event_type == "hygiene_ok")
    hygiene_violations = sum(1 for e in events if e.event_type == "hygiene_missing")
    breach_alerts = sum(1 for e in events if e.event_type == "sterile_breach")
    confirmed = sum(1 for e in events if e.review_status == "confirmed")
    dismissed = sum(1 for e in events if e.review_status == "dismissed")

    unresolved = sum(1 for e in events if e.review_status == "pending" and e.severity != "information")
    has_critical = any(e.severity == "critical" for e in events)
    overall = "Review required" if (has_critical or unresolved or difference) else "No issues flagged"

    duration = None
    if sess.started_at and sess.ended_at:
        duration = round((sess.ended_at - sess.started_at).total_seconds() / 60.0, 1)

    critical_timeline = sorted(
        (e for e in events if e.severity in ("warning", "critical")),
        key=lambda e: e.occurred_at,
    )

    return ReportOut(
        session=SessionOut.model_validate(sess),
        duration_minutes=duration,
        initial_counts=initial,
        final_counts=final,
        count_difference=difference,
        hygiene_events=hygiene_events,
        hygiene_violations=hygiene_violations,
        breach_alerts=breach_alerts,
        confirmed_alerts=confirmed,
        dismissed_alerts=dismissed,
        overall_status=overall,
        critical_timeline=[EventOut.model_validate(e) for e in critical_timeline],
    )
