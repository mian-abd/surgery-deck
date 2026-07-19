"""Hand landmarks via MediaPipe Hands.

Returns normalized (0..1) landmark points per detected hand. Degrades to an
empty list if mediapipe is unavailable so the rest of the pipeline still runs.
"""
from __future__ import annotations

import numpy as np


class HandDetector:
    def __init__(self, max_hands: int = 4) -> None:
        import mediapipe as mp  # lazy import

        self._mp = mp
        self.hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def detect(self, frame_bgr: np.ndarray) -> list[list[dict]]:
        import cv2

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        res = self.hands.process(rgb)
        hands: list[list[dict]] = []
        if res.multi_hand_landmarks:
            for lm in res.multi_hand_landmarks:
                hands.append([{"x": p.x, "y": p.y} for p in lm.landmark])
        return hands

    @staticmethod
    def centers(hands: list[list[dict]]) -> list[dict]:
        """Normalized centroid per hand — used for zone occupancy checks."""
        out = []
        for pts in hands:
            if not pts:
                continue
            cx = sum(p["x"] for p in pts) / len(pts)
            cy = sum(p["y"] for p in pts) / len(pts)
            out.append({"cx": cx, "cy": cy})
        return out
