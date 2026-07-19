"""Safety-event rules. Pure logic: mutate the world model, return event descriptors.

The Pipeline persists descriptors and attaches evidence frames. Descriptors are
plain dicts: {event_type, severity, title, description, confidence, meta}.
"""
from __future__ import annotations

import time

from .state import CONTAMINATED, IN_USE, NON_INSTRUMENT, STERILE, InstrumentTrack, SessionWorld


def evaluate_instruments(
    world: SessionWorld, camera_id: str, instruments: list[dict]
) -> list[dict]:
    """instruments: [{track_id, label, cx, cy}] with normalized centers."""
    zones = world.zones(camera_id)
    events: list[dict] = []
    now = time.time()

    for det in instruments:
        tid = det["track_id"]
        zone = zones.locate(det["cx"], det["cy"])
        ztype = zone.zone_type if zone else None

        track = world.tracks.get(tid)
        if track is None:
            track = InstrumentTrack(track_id=tid, label=det["label"], zone_type=ztype)
            world.tracks[tid] = track
        track.prev_zone_type = track.zone_type
        track.zone_type = ztype
        track.last_seen = now
        det["state"] = track.state  # surface for the overlay

        if ztype == track.prev_zone_type:
            continue  # only react on zone change

        # sterile instrument enters a nonsterile surface -> potentially contaminated
        if ztype == "nonsterile" and not track.touched_nonsterile:
            track.touched_nonsterile = True
            track.state = CONTAMINATED
            det["state"] = CONTAMINATED
            events.append(
                {
                    "event_type": "sterile_breach",
                    "severity": "warning",
                    "title": f"{track.label} #{tid} touched a nonsterile surface",
                    "description": "Instrument entered a designated nonsterile zone and is now "
                    "potentially contaminated. Requires review.",
                    "confidence": 0.85,
                    "meta": {"track_id": tid, "zone": ztype},
                }
            )
        # contaminated instrument returns to the sterile field -> critical breach
        elif ztype == "sterile" and track.touched_nonsterile:
            track.touched_nonsterile = False
            events.append(
                {
                    "event_type": "sterile_breach",
                    "severity": "critical",
                    "title": f"Possible sterile-field contamination: {track.label} #{tid}",
                    "description": "A potentially contaminated instrument re-entered the sterile "
                    "field. Requires immediate review.",
                    "confidence": 0.9,
                    "meta": {"track_id": tid, "zone": ztype},
                }
            )
        elif ztype in ("sterile", "tray") and track.state == STERILE:
            track.state = IN_USE if ztype == "sterile" else STERILE

    return events


def evaluate_hygiene(
    world: SessionWorld, camera_id: str, persons: list[dict], hands: list[dict]
) -> list[dict]:
    """persons/hands: [{cx, cy}] normalized centers for this camera."""
    zones = world.zones(camera_id)
    hs = world.hygiene
    events: list[dict] = []
    now = time.time()

    if "sink" not in zones.types and "sterile" not in zones.types and "entry" not in zones.types:
        return events  # nothing to reason about until zones exist

    # --- sink dwell -> hygiene observed ---
    hand_in_sink = any(
        (z := zones.locate(h["cx"], h["cy"])) and z.zone_type == "sink" for h in hands
    )
    if hand_in_sink:
        if hs.sink_dwell_start is None:
            hs.sink_dwell_start = now
        elif now - hs.sink_dwell_start >= world.min_dwell_sec and (
            hs.last_hygiene_ok_at is None or now - hs.last_hygiene_ok_at > 10
        ):
            hs.last_hygiene_ok_at = now
            hs.flagged_entry = False
            events.append(
                {
                    "event_type": "hygiene_ok",
                    "severity": "information",
                    "title": "Hand hygiene observed",
                    "description": f"Hands remained in the sink zone for "
                    f"{world.min_dwell_sec:.0f}s with rubbing motion.",
                    "confidence": 0.8,
                    "meta": {},
                }
            )
    else:
        hs.sink_dwell_start = None

    # --- entry into sterile/entry zone without a recent hygiene event ---
    entering = any(
        (z := zones.locate(p["cx"], p["cy"])) and z.zone_type in ("sterile", "entry")
        for p in persons
    )
    if entering and not hs.flagged_entry:
        recent_ok = (
            hs.last_hygiene_ok_at is not None
            and now - hs.last_hygiene_ok_at <= world.window_sec
        )
        if not recent_ok:
            hs.flagged_entry = True
            events.append(
                {
                    "event_type": "hygiene_missing",
                    "severity": "warning",
                    "title": "Possible hand-hygiene noncompliance",
                    "description": "A participant entered the sterile area with no completed "
                    "hand-hygiene event detected beforehand. Review video.",
                    "confidence": 0.82,
                    "meta": {},
                }
            )

    return events
