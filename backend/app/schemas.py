"""Pydantic request/response models and WS message shapes."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Cameras ---
class CameraCreate(BaseModel):
    name: str = "Camera"
    camera_type: str = "overhead"


class CameraOut(ORMModel):
    id: str
    name: str
    camera_type: str
    status: str


# --- Sessions ---
class SessionCreate(BaseModel):
    procedure_name: str = "Simulated Procedure"
    room_name: str = "Demo OR 1"


class SessionOut(ORMModel):
    id: str
    procedure_name: str
    room_name: str
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime


# --- Zones ---
class ZoneIn(BaseModel):
    camera_id: str
    name: str
    zone_type: str
    polygon: list[list[float]] = Field(default_factory=list)


class ZoneOut(ORMModel):
    id: str
    camera_id: str
    name: str
    zone_type: str
    polygon: list[list[float]]


class ZoneBulkIn(BaseModel):
    camera_id: str
    zones: list[ZoneIn]


# --- Snapshots ---
class SnapshotOut(ORMModel):
    id: str
    snapshot_type: str
    captured_at: datetime
    total_count: int
    counts: dict
    image_path: str | None


# --- Events / reviews ---
class EventOut(ORMModel):
    id: str
    camera_id: str | None
    event_type: str
    severity: str
    title: str
    description: str
    confidence: float
    review_status: str
    review_note: str
    evidence_path: str | None
    meta: dict
    occurred_at: datetime


class ReviewIn(BaseModel):
    decision: str  # confirmed|dismissed|unclear|further_review
    note: str = ""


class ReviewSummary(BaseModel):
    """Aggregate of human review decisions for a session."""
    confirmed: int = 0
    dismissed: int = 0
    unclear: int = 0
    pending: int = 0
    total: int = 0


# --- Report ---
class CountRow(BaseModel):
    """Per-instrument-class initial vs final tally."""
    instrument: str
    initial: int
    final: int
    difference: int  # initial - final (positive => possibly missing)


class ReportOut(BaseModel):
    session: SessionOut
    generated_at: datetime
    duration_minutes: float | None

    # --- instrument counts ---
    initial_counts: dict
    final_counts: dict
    count_difference: dict
    count_summary: list[CountRow]
    initial_total: int
    final_total: int
    count_mismatch: bool
    initial_snapshot: SnapshotOut | None
    final_snapshot: SnapshotOut | None

    # --- event aggregates ---
    total_events: int
    event_counts_by_type: dict
    hygiene_events: int          # hygiene_ok observations
    hygiene_violations: int      # hygiene_missing alerts
    breach_alerts: int           # sterile_breach alerts
    count_mismatch_alerts: int
    critical_count: int
    warning_count: int
    info_count: int

    # --- review decisions ---
    confirmed_alerts: int
    dismissed_alerts: int
    unclear_alerts: int
    pending_alerts: int
    review_summary: ReviewSummary

    # --- ordered event lists ---
    events: list[EventOut]            # all events, chronological ascending
    critical_timeline: list[EventOut] # warning + critical, chronological ascending

    # --- top-line status ---
    review_required: bool
    overall_status: str

    # --- Gemini-generated narrative (None when Gemini is unavailable) ---
    gemini_summary: str | None = None
    gemini_key_risks: list[str] = Field(default_factory=list)
