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

# DocCheck/medical-instrument-detection ships 12 GERMAN class names. Map them to
# coarse, demo-legible English instrument labels. The model's *index* order is
# not guaranteed, so remapping is done by name (case/whitespace-insensitive) at
# runtime against ``results.names``; unmapped names fall back to the raw name.
DOCCHECK_GERMAN_CLASS_MAP = {
    "Anatomische Pinzette Standard": "forceps",
    "Anatomische Pinzette schlank": "forceps",
    "Chirurgische Pinzette": "forceps",
    "Splitterpinzette": "forceps",
    "Skalpellgriff Nr.3": "scalpel",
    "Skalpellgriff Nr.4": "scalpel",
    "Skalpell geballt": "scalpel",
    "Skalpell schmal": "scalpel",
    "Chirurgische Schere spitz/spitz": "scissors",
    "Chirurgische Schere spitz/stumpf": "scissors",
    "Praeparierschere Standard": "scissors",
    "Praepariernadel": "needle",
}


def load_yolov5_model(weights: str):
    """Load a classic YOLOv5 checkpoint via the ``yolov5`` package.

    torch >= 2.6 flipped ``torch.load``'s default to ``weights_only=True``, which
    cannot unpickle a full ``models.yolo.DetectionModel`` (as shipped by
    DocCheck). These are trusted local weights, so we load with
    ``weights_only=False`` via a scoped monkeypatch of ``torch.load`` that is
    always restored, even on error.
    """
    import torch
    import yolov5  # lazy import (heavy, optional dependency)

    orig_load = torch.load

    def _patched(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return orig_load(*args, **kwargs)

    torch.load = _patched
    try:
        return yolov5.load(weights)
    finally:
        torch.load = orig_load


def _norm(name: str) -> str:
    """Normalize a class name for case/whitespace-insensitive matching."""
    return " ".join(str(name).split()).casefold()


def _build_norm_map(*maps: dict[str, str]) -> dict[str, str]:
    """Merge class maps into a single normalized-key lookup (later wins)."""
    out: dict[str, str] = {}
    for m in maps:
        for k, v in m.items():
            out[_norm(k)] = v
    return out


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


class Yolov5HubDetector:
    """Wraps a CLASSIC YOLOv5 checkpoint loaded via the ``yolov5`` pip package.

    The DocCheck weights are a plain ``models.yolo.DetectionModel`` pickle and do
    NOT load through ``ultralytics.YOLO()``; ``yolov5.load()`` handles them. The
    results API differs from ultralytics: ``results.pred[0]`` is a tensor of
    rows ``[x1, y1, x2, y2, conf, cls]`` and ``results.names`` maps class idx to
    name. Raw (often German) names are remapped to coarse demo labels by name.
    """

    def __init__(
        self,
        weights: str,
        conf: float,
        class_map: dict[str, str] | None = None,
    ) -> None:
        self.model = load_yolov5_model(weights)
        self.model.conf = conf
        self.conf = conf
        # Merge the built-in German map with any config override (override wins).
        self.norm_map = _build_norm_map(
            DOCCHECK_GERMAN_CLASS_MAP, class_map or {}
        )
        self.names = self.model.names

    def _label_for(self, name: str) -> str:
        return self.norm_map.get(_norm(name), name)

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        results = self.model(frame_bgr)
        pred = results.pred[0]  # tensor [N, 6]: x1,y1,x2,y2,conf,cls
        names = results.names
        out: list[Detection] = []
        for row in pred.tolist():
            x1, y1, x2, y2, conf, cls = row
            if conf < self.conf:
                continue
            idx = int(cls)
            if isinstance(names, dict):
                raw = names.get(idx, str(idx))
            else:
                raw = names[idx] if 0 <= idx < len(names) else str(idx)
            out.append(
                Detection(
                    bbox=(float(x1), float(y1), float(x2), float(y2)),
                    label=self._label_for(raw),
                    conf=float(conf),
                    meta={"raw_label": raw, "source": "doccheck"},
                )
            )
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


DOCCHECK_LOCAL_NAME = "instrument_yolov5.pt"


def _ensure_doccheck_weights() -> str | None:
    """Return a local path to the DocCheck YOLOv5 weights, downloading if needed.

    Downloads ``settings.hf_model_file`` from ``settings.hf_model_repo`` into
    ``models/instrument_yolov5.pt`` via huggingface_hub. Returns ``None`` (never
    raises) if the download can't be performed so the server keeps running.
    """
    local_path = os.path.join(settings.models_dir, DOCCHECK_LOCAL_NAME)
    if os.path.exists(local_path):
        return local_path
    try:
        from huggingface_hub import hf_hub_download
    except Exception as exc:  # pragma: no cover - optional dep
        print(f"[detector] huggingface_hub unavailable ({exc}); skipping DocCheck download")
        return None
    try:
        os.makedirs(settings.models_dir, exist_ok=True)
        print(
            f"[detector] downloading DocCheck weights "
            f"{settings.hf_model_repo}/{settings.hf_model_file} ..."
        )
        cached = hf_hub_download(
            repo_id=settings.hf_model_repo,
            filename=settings.hf_model_file,
        )
        # Copy out of the HF cache into models/ so the path is stable/inspectable.
        import shutil

        shutil.copyfile(cached, local_path)
        print(f"[detector] DocCheck weights ready at {local_path}")
        return local_path
    except Exception as exc:  # pragma: no cover - network/fs failures
        print(f"[detector] DocCheck download failed ({exc}); falling back to COCO only")
        return None


def _try_build_doccheck() -> Detector | None:
    """Build the DocCheck YOLOv5 surgical detector, or None on any failure."""
    weights = _ensure_doccheck_weights()
    if weights is None:
        return None
    try:
        det = Yolov5HubDetector(
            weights,
            conf=settings.instrument_conf,
            class_map=settings.class_map_override,
        )
        print(f"[detector] loaded DocCheck surgical model: {weights}")
        return det
    except Exception as exc:  # e.g. yolov5/torch missing or load error
        print(
            f"[detector] could not load DocCheck model ({exc}); "
            f"install with `pip install yolov5` — falling back to COCO only"
        )
        return None


def _try_build_ultralytics_instrument() -> Detector | None:
    """Load models/instrument.pt via ultralytics (fine-tuned path), or None."""
    instrument_path = os.path.join(settings.models_dir, "instrument.pt")
    if not os.path.exists(instrument_path):
        return None
    try:
        det = UltralyticsDetector(
            instrument_path,
            conf=settings.instrument_conf,
            label_map=settings.class_map_override or None,
        )
        print(f"[detector] loaded surgical model: {instrument_path}")
        return det
    except Exception as exc:  # pragma: no cover
        print(f"[detector] could not load {instrument_path} ({exc})")
        return None


def build_detector() -> Detector:
    """Assemble the configured detector stack.

    The COCO person detector is ALWAYS included (hygiene logic depends on
    reliable ``person`` detection). A surgical instrument detector is added on
    top based on ``settings.surgical_model``:

      * ``doccheck``    -> DocCheck YOLOv5 weights (auto-downloaded via HF).
      * ``ultralytics`` -> fine-tuned models/instrument.pt via ultralytics.
      * ``coco``/``none`` -> COCO stand-in instruments only.

    Any failure to load the surgical model degrades gracefully to COCO-only;
    the server never crashes. As a final fallback, a dropped-in
    models/instrument.pt is auto-loaded even when not explicitly selected.
    """
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

    mode = (settings.surgical_model or "none").strip().lower()
    surgical: Detector | None = None

    if mode == "doccheck":
        surgical = _try_build_doccheck()
    elif mode == "ultralytics":
        surgical = _try_build_ultralytics_instrument()
    elif mode in ("coco", "none"):
        surgical = None
    else:
        print(f"[detector] unknown surgical_model={mode!r}; using COCO only")

    if surgical is not None:
        detectors.append(surgical)
    else:
        # Fallback: honor the classic "drop models/instrument.pt in" behavior
        # even when it wasn't the explicitly selected mode.
        if mode != "ultralytics":
            fallback = _try_build_ultralytics_instrument()
            if fallback is not None:
                detectors.append(fallback)
                surgical = fallback

    if surgical is None:
        print("[detector] no surgical model active — using COCO person+scissors only")

    return CompositeDetector(detectors)
