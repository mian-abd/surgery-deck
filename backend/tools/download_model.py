"""Download + sanity-check the DocCheck surgical-instrument YOLOv5 weights.

Run from the backend/ directory:

    python tools/download_model.py

It fetches the classic YOLOv5 checkpoint from Hugging Face
(DocCheck/medical-instrument-detection) into backend/models/, then does a quick
load + dummy inference to confirm the `yolov5` runtime path works.

License note: the DocCheck weights are CC-BY-NC (non-commercial). Fine for the
hackathon/demo; swap in a fine-tuned model for production (see train_surgical.md).
"""
from __future__ import annotations

import os
import shutil
import sys

# Make `app` importable whether run from backend/ or backend/tools/.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.config import settings  # noqa: E402
from app.perception.detector import DOCCHECK_LOCAL_NAME  # noqa: E402


def download() -> str:
    """Download the weights into models/ and return the local path."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("ERROR: huggingface_hub is not installed. Run: pip install huggingface_hub")
        raise SystemExit(1)

    models_dir = settings.models_dir
    os.makedirs(models_dir, exist_ok=True)
    local_path = os.path.join(models_dir, DOCCHECK_LOCAL_NAME)

    if os.path.exists(local_path):
        print(f"Already present: {local_path}")
        return local_path

    print(f"Downloading {settings.hf_model_repo}/{settings.hf_model_file} ...")
    cached = hf_hub_download(
        repo_id=settings.hf_model_repo,
        filename=settings.hf_model_file,
    )
    shutil.copyfile(cached, local_path)
    print(f"Saved weights to: {local_path}")
    return local_path


def sanity_check(weights_path: str) -> None:
    """Load via the yolov5 package and run one dummy inference."""
    try:
        import numpy as np

        from app.perception.detector import load_yolov5_model
    except ImportError as exc:
        print(f"WARNING: cannot run sanity check ({exc}). Install with: pip install yolov5")
        return

    print("Loading model via yolov5.load() ...")
    # load_yolov5_model applies the weights_only=False shim needed on torch>=2.6.
    model = load_yolov5_model(weights_path)
    model.conf = settings.instrument_conf
    print(f"Class names ({len(model.names)}): {model.names}")

    print("Running dummy inference on a blank 640x640 frame ...")
    dummy = np.zeros((640, 640, 3), dtype=np.uint8)
    results = model(dummy)
    n = int(results.pred[0].shape[0])
    print(f"Inference OK — {n} detection(s) on blank frame (0 expected).")


def main() -> None:
    path = download()
    print(f"\nMODEL PATH: {os.path.abspath(path)}")
    sanity_check(path)
    print("\nDone. Set SURGICAL_MODEL=doccheck to use it.")


if __name__ == "__main__":
    main()
