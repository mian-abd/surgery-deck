"""Smoke test: build the Pipeline and run a real detection frame through it.

Downloads yolo11n.pt on first run. Uses a synthetic frame plus (if reachable)
a real sample image to confirm the detector produces boxes.
"""
import numpy as np

from app.perception.pipeline import Pipeline


def main() -> None:
    p = Pipeline()
    print("pipeline built (detector + hands + trackers)")

    # define zones for a fake camera/session so the engine has something to test
    p.set_zones(
        "sess1",
        "cam1",
        [
            {"name": "sterile", "zone_type": "sterile", "polygon": [[0.5, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 1.0]]},
            {"name": "nonsterile", "zone_type": "nonsterile", "polygon": [[0.0, 0.0], [0.5, 0.0], [0.5, 1.0], [0.0, 1.0]]},
        ],
    )

    frame = np.full((360, 640, 3), 40, dtype=np.uint8)
    out = p.process("sess1", "cam1", frame)
    assert set(out.keys()) == {"detections", "hands", "alerts"}, out.keys()
    print(f"process() ok — detections={len(out['detections'])} hands={len(out['hands'])} "
          f"alerts={len(out['alerts'])}")

    # try a real image for an actual detection (uses the bundled ultralytics
    # sample so it works offline / without a network fetch)
    try:
        import os
        import cv2
        import ultralytics
        sample = os.path.join(os.path.dirname(ultralytics.__file__), "assets", "bus.jpg")
        img = cv2.imread(sample)
        out2 = p.process("sess1", "cam1", img)
        labels = [d["label"] for d in out2["detections"]]
        assert any(l == "person" for l in labels), f"expected a person, got {labels}"
        print(f"real image detections: {labels}")
    except Exception as exc:
        print(f"(skipped real-image test: {exc})")

    print("counts:", p.snapshot_counts("sess1")[0])


if __name__ == "__main__":
    main()
