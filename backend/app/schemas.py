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


# --- Report ---
class ReportOut(BaseModel):
    session: SessionOut
    duration_minutes: float | None
    initial_counts: dict
    final_counts: dict
    count_difference: dict
    hygiene_events: int
    hygiene_violations: int
    breach_alerts: int
    confirmed_alerts: int
    dismissed_alerts: int
    overall_status: str
    critical_timeline: list[EventOut]
