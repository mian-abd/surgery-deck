"""ORM models — trimmed subset of the PRD ERD for the MVP.

IDs are string UUIDs for SQLite/Postgres portability. Every camera-scoped
row carries ``camera_id`` so the pipeline is multi-camera-ready.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, default="Camera")
    camera_type: Mapped[str] = mapped_column(String, default="overhead")  # entry|overhead|tray|sink
    status: Mapped[str] = mapped_column(String, default="online")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ProcedureSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    procedure_name: Mapped[str] = mapped_column(String, default="Simulated Procedure")
    room_name: Mapped[str] = mapped_column(String, default="Demo OR 1")
    status: Mapped[str] = mapped_column(String, default="setup")  # setup|active|review|completed
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    zones: Mapped[list["Zone"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    events: Mapped[list["SafetyEvent"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    snapshots: Mapped[list["InstrumentSnapshot"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    camera_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    zone_type: Mapped[str] = mapped_column(String)  # sterile|nonsterile|tray|sink|patient|entry
    polygon: Mapped[list] = mapped_column(JSON)  # [[x,y], ...] in frame coords (0..1 normalized)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    session: Mapped[ProcedureSession] = relationship(back_populates="zones")


class InstrumentSnapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    snapshot_type: Mapped[str] = mapped_column(String)  # initial|interim|final
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    counts: Mapped[dict] = mapped_column(JSON, default=dict)  # {"forceps": 3, "scissors": 2, ...}
    image_path: Mapped[str | None] = mapped_column(String, nullable=True)

    session: Mapped[ProcedureSession] = relationship(back_populates="snapshots")


class SafetyEvent(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    camera_id: Mapped[str | None] = mapped_column(String, nullable=True)
    event_type: Mapped[str] = mapped_column(String)  # hygiene_missing|count_mismatch|sterile_breach|instrument_missing|info
    severity: Mapped[str] = mapped_column(String, default="warning")  # information|warning|critical
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    review_status: Mapped[str] = mapped_column(String, default="pending")  # pending|confirmed|dismissed|unclear
    review_note: Mapped[str] = mapped_column(Text, default="")
    evidence_path: Mapped[str | None] = mapped_column(String, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    session: Mapped[ProcedureSession] = relationship(back_populates="events")
