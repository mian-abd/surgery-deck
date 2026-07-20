"""End-of-session safety report (PRD 7.9). Pure DB read + aggregation.

Everything below is derived from real DB rows (ProcedureSession,
InstrumentSnapshot, SafetyEvent). No mock/placeholder numbers. A single
events query + two snapshot lookups keeps ``build_report`` well under a
few hundred ms.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import InstrumentSnapshot, ProcedureSession, SafetyEvent
from ..schemas import (
    CountRow,
    EventOut,
    ReportOut,
    ReviewSummary,
    SessionOut,
    SnapshotOut,
)


def _latest_snapshot(
    db: Session, session_id: str, snapshot_type: str
) -> InstrumentSnapshot | None:
    return db.scalars(
        select(InstrumentSnapshot)
        .where(
            InstrumentSnapshot.session_id == session_id,
            InstrumentSnapshot.snapshot_type == snapshot_type,
        )
        .order_by(InstrumentSnapshot.captured_at.desc())
    ).first()


def build_report(
    db: Session,
    sess: ProcedureSession,
    gemini_summary: str | None = None,
    gemini_key_risks: list[str] | None = None,
) -> ReportOut:
    events = list(
        db.scalars(
            select(SafetyEvent)
            .where(SafetyEvent.session_id == sess.id)
            .order_by(SafetyEvent.occurred_at.asc())
        )
    )

    # --- instrument counts (initial vs final) ---
    initial_snap = _latest_snapshot(db, sess.id, "initial")
    final_snap = _latest_snapshot(db, sess.id, "final")
    initial = dict(initial_snap.counts) if initial_snap and initial_snap.counts else {}
    final = dict(final_snap.counts) if final_snap and final_snap.counts else {}

    all_keys = sorted(set(initial) | set(final))
    count_summary = [
        CountRow(
            instrument=k,
            initial=int(initial.get(k, 0)),
            final=int(final.get(k, 0)),
            difference=int(initial.get(k, 0)) - int(final.get(k, 0)),
        )
        for k in all_keys
    ]
    difference = {
        row.instrument: row.difference for row in count_summary if row.difference != 0
    }
    count_mismatch = bool(difference)

    # --- event aggregates by type ---
    event_counts_by_type: dict[str, int] = {}
    for e in events:
        event_counts_by_type[e.event_type] = event_counts_by_type.get(e.event_type, 0) + 1

    hygiene_events = event_counts_by_type.get("hygiene_ok", 0)
    hygiene_violations = event_counts_by_type.get("hygiene_missing", 0)
    breach_alerts = event_counts_by_type.get("sterile_breach", 0)
    count_mismatch_alerts = event_counts_by_type.get("count_mismatch", 0)

    critical_count = sum(1 for e in events if e.severity == "critical")
    warning_count = sum(1 for e in events if e.severity == "warning")
    info_count = sum(1 for e in events if e.severity == "information")

    # --- human review decisions (persisted on the SafetyEvent) ---
    confirmed = sum(1 for e in events if e.review_status == "confirmed")
    dismissed = sum(1 for e in events if e.review_status == "dismissed")
    unclear = sum(
        1 for e in events if e.review_status in ("unclear", "further_review")
    )
    pending = sum(1 for e in events if e.review_status == "pending")

    review_summary = ReviewSummary(
        confirmed=confirmed,
        dismissed=dismissed,
        unclear=unclear,
        pending=pending,
        total=len(events),
    )

    # --- top-line status ---
    # A session needs review if any critical event exists, any actionable
    # (non-information) event is still unconfirmed/undismissed, or the
    # instrument count does not reconcile.
    unresolved = sum(
        1
        for e in events
        if e.severity != "information" and e.review_status in ("pending", "unclear", "further_review")
    )
    has_critical = critical_count > 0
    review_required = bool(has_critical or unresolved or count_mismatch)
    overall = "Review required" if review_required else "No issues flagged"

    duration = None
    if sess.started_at and sess.ended_at:
        duration = round((sess.ended_at - sess.started_at).total_seconds() / 60.0, 1)

    critical_timeline = [e for e in events if e.severity in ("warning", "critical")]

    return ReportOut(
        session=SessionOut.model_validate(sess),
        generated_at=datetime.now(timezone.utc),
        duration_minutes=duration,
        initial_counts=initial,
        final_counts=final,
        count_difference=difference,
        count_summary=count_summary,
        initial_total=int(sum(initial.values())),
        final_total=int(sum(final.values())),
        count_mismatch=count_mismatch,
        initial_snapshot=(
            SnapshotOut.model_validate(initial_snap) if initial_snap else None
        ),
        final_snapshot=(
            SnapshotOut.model_validate(final_snap) if final_snap else None
        ),
        total_events=len(events),
        event_counts_by_type=event_counts_by_type,
        hygiene_events=hygiene_events,
        hygiene_violations=hygiene_violations,
        breach_alerts=breach_alerts,
        count_mismatch_alerts=count_mismatch_alerts,
        critical_count=critical_count,
        warning_count=warning_count,
        info_count=info_count,
        confirmed_alerts=confirmed,
        dismissed_alerts=dismissed,
        unclear_alerts=unclear,
        pending_alerts=pending,
        review_summary=review_summary,
        events=[EventOut.model_validate(e) for e in events],
        critical_timeline=[EventOut.model_validate(e) for e in critical_timeline],
        review_required=review_required,
        overall_status=overall,
        gemini_summary=gemini_summary,
        gemini_key_risks=gemini_key_risks or [],
    )
