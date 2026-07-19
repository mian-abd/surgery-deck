"""Per-session world model: instrument states, hygiene tracking, live zones.

Held in memory by the Pipeline for the duration of a session. Fused across all
cameras of the session; each camera contributes its own ZoneSet.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .zones import ZoneDef, ZoneSet

# Instrument sterility state machine (PRD 8.4)
STERILE = "sterile"
IN_USE = "in_use"
CONTAMINATED = "potentially_contaminated"
NON_INSTRUMENT = {"person", "hand"}


@dataclass
class InstrumentTrack:
    track_id: int
    label: str
    state: str = STERILE
    zone_type: str | None = None
    prev_zone_type: str | None = None
    touched_nonsterile: bool = False
    last_seen: float = field(default_factory=time.time)


@dataclass
class HygieneState:
    sink_dwell_start: float | None = None
    last_hygiene_ok_at: float | None = None
    # participants that have already triggered a "missing" alert (debounce)
    flagged_entry: bool = False


class SessionWorld:
    def __init__(self, min_dwell_sec: float, window_sec: float) -> None:
        self.min_dwell_sec = min_dwell_sec
        self.window_sec = window_sec
        self.zones_by_camera: dict[str, ZoneSet] = {}
        self.tracks: dict[int, InstrumentTrack] = {}
        self.hygiene = HygieneState()
        self.last_frame_by_camera: dict[str, np.ndarray] = {}

    def set_zones(self, camera_id: str, zones: list[ZoneDef]) -> None:
        self.zones_by_camera.setdefault(camera_id, ZoneSet()).set(zones)

    def zones(self, camera_id: str) -> ZoneSet:
        return self.zones_by_camera.setdefault(camera_id, ZoneSet())

    def current_counts(self) -> dict[str, int]:
        """Live instrument counts by label from active tracks."""
        counts: dict[str, int] = {}
        for t in self.tracks.values():
            if t.label in NON_INSTRUMENT:
                continue
            counts[t.label] = counts.get(t.label, 0) + 1
        return counts
