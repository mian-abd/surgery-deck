"""Directly exercise the safety-event rules (Phase 3) without a camera."""
import time

from app.engine.events import evaluate_hygiene, evaluate_instruments
from app.engine.state import SessionWorld
from app.engine.zones import ZoneDef

# left half = nonsterile, right half = sterile, small sink box top-left
ZONES = [
    ZoneDef("sterile", "sterile", [[0.5, 0], [1, 0], [1, 1], [0.5, 1]]),
    ZoneDef("nonsterile", "nonsterile", [[0, 0], [0.5, 0], [0.5, 1], [0, 1]]),
    ZoneDef("sink", "sink", [[0.0, 0.0], [0.2, 0.0], [0.2, 0.2], [0.0, 0.2]]),
]


def sev(events, etype):
    return [e["severity"] for e in events if e["event_type"] == etype]


def test_breach():
    w = SessionWorld(min_dwell_sec=1.0, window_sec=300)
    w.set_zones("cam", ZONES)
    # instrument starts sterile (right)
    evaluate_instruments(w, "cam", [{"track_id": 1, "label": "clamp", "cx": 0.8, "cy": 0.5}])
    # moves to nonsterile (left) -> warning + contaminated
    e1 = evaluate_instruments(w, "cam", [{"track_id": 1, "label": "clamp", "cx": 0.2, "cy": 0.5}])
    # returns to sterile -> critical breach
    e2 = evaluate_instruments(w, "cam", [{"track_id": 1, "label": "clamp", "cx": 0.8, "cy": 0.5}])
    assert sev(e1, "sterile_breach") == ["warning"], e1
    assert sev(e2, "sterile_breach") == ["critical"], e2
    print("breach rule OK:", [e["title"] for e in e1 + e2])


def test_hygiene_missing():
    w = SessionWorld(min_dwell_sec=1.0, window_sec=300)
    w.set_zones("cam", ZONES)
    # person enters sterile with no prior hygiene -> warning
    e = evaluate_hygiene(w, "cam", persons=[{"cx": 0.8, "cy": 0.5}], hands=[])
    assert sev(e, "hygiene_missing") == ["warning"], e
    print("hygiene-missing rule OK:", [x["title"] for x in e])


def test_hygiene_ok():
    w = SessionWorld(min_dwell_sec=0.2, window_sec=300)
    w.set_zones("cam", ZONES)
    # hands dwell in sink; second call after dwell threshold -> hygiene_ok
    evaluate_hygiene(w, "cam", persons=[], hands=[{"cx": 0.1, "cy": 0.1}])
    time.sleep(0.25)
    e = evaluate_hygiene(w, "cam", persons=[], hands=[{"cx": 0.1, "cy": 0.1}])
    assert sev(e, "hygiene_ok") == ["information"], e
    # now entering sterile should NOT flag missing (recent hygiene)
    e2 = evaluate_hygiene(w, "cam", persons=[{"cx": 0.8, "cy": 0.5}], hands=[])
    assert not sev(e2, "hygiene_missing"), e2
    print("hygiene-ok + suppression OK")


if __name__ == "__main__":
    test_breach()
    test_hygiene_missing()
    test_hygiene_ok()
    print("ALL ENGINE TESTS PASSED")
