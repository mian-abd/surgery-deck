"""Detector-agnostic multi-object tracking via supervision.ByteTrack.

One tracker instance per camera gives stable track IDs (e.g. Clamp #3) that
survive brief occlusion, which keeps instrument counts robust.
"""
from __future__ import annotations

import numpy as np

from .detector import Detection


class ByteTracker:
    def __init__(self) -> None:
        import supervision as sv  # lazy import

        self._sv = sv
        self.tracker = sv.ByteTrack()

    def update(self, detections: list[Detection], frame_shape: tuple[int, int]) -> list[Detection]:
        sv = self._sv
        if not detections:
            # still advance the tracker so lost tracks age out
            self.tracker.update_with_detections(sv.Detections.empty())
            return []

        xyxy = np.array([d.bbox for d in detections], dtype=float)
        conf = np.array([d.conf for d in detections], dtype=float)
        class_ids = np.arange(len(detections))  # index back into our list

        sv_dets = sv.Detections(xyxy=xyxy, confidence=conf, class_id=class_ids)
        tracked = self.tracker.update_with_detections(sv_dets)

        out: list[Detection] = []
        for i in range(len(tracked)):
            src = detections[int(tracked.class_id[i])]
            out.append(
                Detection(
                    bbox=tuple(tracked.xyxy[i].tolist()),
                    label=src.label,
                    conf=float(tracked.confidence[i]) if tracked.confidence is not None else src.conf,
                    track_id=int(tracked.tracker_id[i]) if tracked.tracker_id is not None else None,
                )
            )
        return out
