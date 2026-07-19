# ORGuard — AI Surgical-Safety Monitor (Prototype)

Computer-vision safety monitor for a simulated operating room. A **camera
station** streams a live webcam feed to a cloud backend that runs object
detection, tracking, hand-landmark, and zone/state reasoning; an **Android
viewer app** (or any browser) shows the live feed with overlaid detections and
real-time safety alerts.

> Prototype for demonstration only. Every alert is a *possible* event that
> requires human confirmation. Not a medical device; no clinical use.

## What it does (MVP)
- **Live feed relay** — camera device → backend → viewer devices (viewer-only).
- **Instrument detection + tracking** — YOLO (ultralytics) + ByteTrack persistent IDs.
- **Hand-hygiene check** — MediaPipe hands + sink-zone dwell before sterile entry.
- **Sterile-zone breach** — instrument crossing sterile ⇄ nonsterile → contamination alert.
- **Instrument count** — initial vs final snapshot → count-mismatch alert.
- **Dashboard / review / report** — live alerts, human confirm/dismiss, end-of-session report.

## Architecture
```
Camera station (/capture)  --JPEG frames-->  FastAPI backend (GCP)  --frame+detections+alerts-->  Viewer (Android APK / browser)
   getUserMedia, WS ingest        YOLO + ByteTrack + MediaPipe + zone/state engine        WS /ws/session, canvas overlay
                                              |
                                        SQLite / Cloud SQL   +   evidence frames (disk / GCS)
```

## Roles
- **Camera station** = the device pointed at the tray/sterile field (a laptop or a
  spare phone browser). Open `/capture`, pick the session, Start streaming.
- **Viewer** = the Android app (Capacitor-wrapped web app) or any browser at
  `/monitor/<sessionId>`. Shows the feed + detections + alerts. Does not use a camera.

---

## Run locally (Windows)

Prereqs: **Python 3.10** and **Node 20+**. (This machine: `py -3.10`, Node at
`C:\Program Files\nodejs`.)

### 1. Backend
```powershell
cd backend
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
First start downloads `yolo11n.pt` (~5 MB) and initializes MediaPipe.
Health check: http://127.0.0.1:8000/health → `"perception": true`.

Optional: drop a fine-tuned/downloaded surgical model at `backend/models/instrument.pt`
and it is auto-loaded (its classes are added to detection). Without it, the demo
uses COCO `person` + `scissors`/`knife` as stand-in instruments.

### 2. Frontend
```powershell
cd frontend
npm install
npm run dev      # http://localhost:5173  (proxies /api and /ws to :8000)
```

### 3. Demo flow (matches PRD §10)
1. **Sessions** → create "Simulated Appendectomy" → it opens the Monitor (viewer).
2. On the camera device, open **Camera** (`/capture`), select the session, **Start streaming**.
3. Back on the viewer, **Draw zone** → outline the sterile field, tray, nonsterile
   table, and sink; save each.
4. Place instruments on the tray → **Capture initial count**.
5. Perform hand-hygiene at the sink, then enter the sterile zone (hygiene observed);
   have a second person enter directly (hygiene-missing alert).
6. Move an instrument onto the nonsterile table and back (contamination alert).
7. Hide one instrument → **End session & report** (captures final count →
   count-mismatch alert).
8. **Review** each alert with its evidence frame; **Report** shows the summary.

---

## Tests / verification
```powershell
cd backend
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe tools\pipeline_test.py       # detector+hands+tracker load
.\.venv\Scripts\python.exe tools\engine_test.py         # breach + hygiene rules
# with the server running:
.\.venv\Scripts\python.exe tools\ws_relay_test.py       # camera->viewer relay
.\.venv\Scripts\python.exe tools\integration_test.py    # real image -> tracked detections
```

## Android app & cloud deploy
See [`deploy/README.md`](deploy/README.md) for building the Android APK (Capacitor)
and deploying the backend to Google Cloud (Cloud Run + Cloud SQL + GCS).

## Configuration
Backend reads `.env` (see `backend/.env.example`): `DB_URL` (SQLite ↔ Postgres),
`STORAGE_BACKEND` (local ↔ gcs), detector/hygiene thresholds, CORS origins.
