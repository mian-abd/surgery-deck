"""Evidence-frame storage abstraction: local disk (dev) or GCS (prod)."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import cv2
import numpy as np

from .config import settings

_evidence_dir = os.path.abspath(settings.evidence_dir)
os.makedirs(_evidence_dir, exist_ok=True)


def save_evidence(frame_bgr: np.ndarray, prefix: str = "evt") -> str:
    """Persist a JPEG evidence frame; return a path/URL reference.

    Local backend writes under EVIDENCE_DIR and returns a web path served at
    /evidence/<file>. GCS backend uploads and returns a gs:// or https URL.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    fname = f"{prefix}_{ts}_{uuid.uuid4().hex[:8]}.jpg"

    ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise RuntimeError("Failed to encode evidence frame")

    if settings.storage_backend == "gcs" and settings.gcs_bucket:
        return _upload_gcs(fname, buf.tobytes())

    path = os.path.join(_evidence_dir, fname)
    with open(path, "wb") as f:
        f.write(buf.tobytes())
    return f"/evidence/{fname}"


def _upload_gcs(fname: str, data: bytes) -> str:
    from google.cloud import storage  # imported lazily; only needed in prod

    client = storage.Client()
    blob = client.bucket(settings.gcs_bucket).blob(f"evidence/{fname}")
    blob.upload_from_string(data, content_type="image/jpeg")
    return f"https://storage.googleapis.com/{settings.gcs_bucket}/evidence/{fname}"


def evidence_dir() -> str:
    return _evidence_dir
