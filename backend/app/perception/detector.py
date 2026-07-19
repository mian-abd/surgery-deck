"""Swappable object-detection layer.

The rest of the system depends only on the ``Detector`` protocol and the
``Detection`` dataclass, so a fine-tuned surgical model can be dropped in later
by changing config — no downstream changes.

Default build:
  * an ultralytics COCO model for reliable ``person`` detection (and COCO
    ``scissors``/``knife`` surfaced as instruments), which works out of the box;
  * an OPTIONAL second ultralytics model loaded from ``models/instrument.pt``
    (a downloaded/fine-tuned surgical model) whose classes are remapped to the
    demo instrument names via ``class_map``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from ..config import settings

# COCO classes we treat as stand-in surgical instruments for an out-of-box demo.
COCO_INSTRUMENT_MAP = {"scissors": "scissors", "knife": "scalpel"}


@dataclass
class Detection:
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 (pixels)
    label: str
    conf: float
    track_id: int | None = None
    meta: dict = field(default_factory=dict)

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return (x1 + x2) / 2, (y1 + y2) / 2


class Detector(Protocol):
    def detect(self, frame_bgr: np.ndarray) -> list[Detection]: ...


class UltralyticsDetector:
    """Wraps an ultralytics YOLO model with optional label filtering/renaming."""

    def __init__(
        self,
        weights: str,
        conf: float,
        keep: set[str] | None = None,
        label_map: dict[str, str] | None = None,
    ) -> None:
        from ultralytics import YOLO  # lazy import (heavy)

        self.model = YOLO(weights)
        self.conf = conf
        self.keep = keep
        self.label_map = label_map or {}
        self.names = self.model.names

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        res = self.model.predict(frame_bgr, conf=self.conf, verbose=False)[0]
        out: list[Detection] = []
        for b in res.boxes:
            cls = int(b.cls[0])
            name = self.names.get(cls, str(cls)) if isinstance(self.names, dict) else self.names[cls]
            if self.keep is not None and name not in self.keep:
                continue
            label = self.label_map.get(name, name)
            xyxy = b.xyxy[0].tolist()
            out.append(Detection(bbox=tuple(xyxy), label=label, conf=float(b.conf[0])))
        return out


class CompositeDetector:
    """Runs several detectors and concatenates their detections."""

    def __init__(self, detectors: list[Detector]) -> None:
        self.detectors = detectors

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        out: list[Detection] = []
        for d in self.detectors:
            out.extend(d.detect(frame_bgr))
        return out


def build_detector() -> Detector:
    """Assemble the configured detector stack."""
    weights = os.path.join(settings.models_dir, settings.person_model)
    if not os.path.exists(weights):
        weights = settings.person_model  # let ultralytics fetch the pretrained weights

    # COCO model: person + a couple of instrument-like classes out of the box.
    coco = UltralyticsDetector(
        weights,
        conf=settings.detect_conf,
        keep={"person", *COCO_INSTRUMENT_MAP.keys()},
        label_map=COCO_INSTRUMENT_MAP,
    )
    detectors: list[Detector] = [coco]

    # Optional drop-in surgical model: models/instrument.pt
    instrument_path = os.path.join(settings.models_dir, "instrument.pt")
    if os.path.exists(instrument_path):
        detectors.append(
            UltralyticsDetector(instrument_path, conf=settings.detect_conf)
        )
        print(f"[detector] loaded surgical model: {instrument_path}")
    else:
        print("[detector] no models/instrument.pt — using COCO person+scissors only")

    return CompositeDetector(detectors)
