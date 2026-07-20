# Fine-tuning a surgical-instrument detector (`ultralytics` path)

This produces `backend/models/instrument.pt`, a clean Ultralytics YOLO checkpoint
that loads directly via `ultralytics.YOLO()` and is used when
`SURGICAL_MODEL=ultralytics`.

Unlike the DocCheck weights (CC-BY-NC, classic YOLOv5, German labels), a model
you fine-tune here is yours to relabel and, depending on the dataset license,
use commercially. Recommended base: `yolo11n` (nano — fast, CPU-friendly demo).

## What YOU must provide

- A **Roboflow account + API key** (free tier works) — get it from
  https://app.roboflow.com → Settings → API. The dataset below is CC-BY-4.0.
- A **GPU** for training. Easiest is a free **Google Colab** GPU runtime; local
  CPU training is possible but slow. Inference afterward runs fine on CPU.
- ~15 min of GPU time for a nano model at 640px.

## 1. Install training deps

```bash
pip install ultralytics roboflow
```

## 2. Download the dataset from Roboflow

Recommended: `reto-lvy74/surgical-tools-bxgxg` (3004 images, YOLO format, CC-BY-4.0).

```python
from roboflow import Roboflow

rf = Roboflow(api_key="YOUR_ROBOFLOW_API_KEY")   # <-- you provide this
project = rf.workspace("reto-lvy74").project("surgical-tools-bxgxg")
version = project.version(1)                       # use the latest version number
dataset = version.download("yolov11")             # writes a data.yaml + images/labels
print("dataset at:", dataset.location)            # note the path to data.yaml
```

Alternative dataset: **SID-RAS** (Mendeley `cyghvmjrt3`, 9 classes incl.
gauze/hemostat) — download manually, ensure it is in YOLO format with a
`data.yaml`, and point `data=` at that file below.

## 3. Train yolo11n

```bash
yolo detect train \
  model=yolo11n.pt \
  data="{dataset.location}/data.yaml" \
  epochs=100 imgsz=640 batch=16 \
  project=runs name=surgical
```

(On Colab, run the same as `!yolo detect train ...`.)

The best checkpoint is written to `runs/surgical/weights/best.pt`.

## 4. Install the model

Copy the trained weights into place:

```bash
cp runs/surgical/weights/best.pt backend/models/instrument.pt
```

Then set `SURGICAL_MODEL=ultralytics` in `.env` and restart the backend.
`build_detector()` loads `models/instrument.pt` via `UltralyticsDetector`.

## 5. (Optional) remap class names to demo labels

If the dataset's class names aren't already the coarse demo labels
(`forceps`/`scalpel`/`scissors`/`needle`/...), set a JSON override in `.env`, e.g.:

```
CLASS_MAP={"hemostat": "forceps", "blade": "scalpel"}
```

`class_map_override` is applied by name (case/whitespace-insensitive) to the
model's own class names; unmapped names pass through unchanged.
