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


# Cache the GCS client/bucket across calls (creating a client per upload is slow
# and re-reads Application Default Credentials every time).
_gcs_bucket = None  # type: ignore[var-annotated]


def _get_gcs_bucket():
    """Return a cached GCS bucket handle, importing the SDK lazily.

    google-cloud-storage is only required when STORAGE_BACKEND=gcs, so it is
    imported here (not at module load) to keep local/dev runs dependency-free.
    """
    global _gcs_bucket
    if _gcs_bucket is not None:
        return _gcs_bucket

    try:
        from google.cloud import storage  # lazy: prod-only dependency
    except ImportError as e:  # pragma: no cover - depends on install profile
        raise RuntimeError(
            "STORAGE_BACKEND=gcs requires the 'google-cloud-storage' package. "
            "Install it with: pip install google-cloud-storage"
        ) from e

    if not settings.gcs_bucket:
        raise RuntimeError(
            "STORAGE_BACKEND=gcs but GCS_BUCKET is empty. Set GCS_BUCKET to your "
            "bucket name (e.g. orguard-evidence-<project>)."
        )

    try:
        # Client() uses Application Default Credentials: the Cloud Run service
        # account in prod, or `gcloud auth application-default login` locally.
        client = storage.Client()
        _gcs_bucket = client.bucket(settings.gcs_bucket)
    except Exception as e:  # pragma: no cover - env/credential dependent
        raise RuntimeError(
            f"Could not initialize GCS client for bucket '{settings.gcs_bucket}': {e}"
        ) from e

    return _gcs_bucket


def _upload_gcs(fname: str, data: bytes) -> str:
    """Upload a JPEG to gs://<bucket>/evidence/<fname>; return a viewable URL."""
    blob = _get_gcs_bucket().blob(f"evidence/{fname}")
    try:
        blob.upload_from_string(data, content_type="image/jpeg")
    except Exception as e:  # pragma: no cover - network/permission dependent
        raise RuntimeError(
            f"GCS upload failed for evidence/{fname} in bucket "
            f"'{settings.gcs_bucket}': {e}. Check that the service account has "
            "roles/storage.objectAdmin on the bucket."
        ) from e

    # Public HTTPS object URL. This resolves only if bucket objects are readable
    # (e.g. bucket has allUsers:objectViewer, or the caller is authenticated).
    # See deploy/README.md "Evidence storage (GCS)" for the two access options.
    return f"https://storage.googleapis.com/{settings.gcs_bucket}/evidence/{fname}"


def evidence_dir() -> str:
    return _evidence_dir
