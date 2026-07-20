# ORGuard — Deployment (Google Cloud Run) + Android viewer

ORGuard is two services:

- **backend** — FastAPI (uvicorn) with WebSockets (`/ws/ingest/{camera_id}`,
  `/ws/session/{session_id}`), SQLAlchemy, and CPU perception (torch /
  ultralytics / mediapipe). Evidence JPEGs are written to local disk (dev) or a
  GCS bucket (prod).
- **frontend** — a Vite/React app built to static files and served by nginx.
  nginx can either proxy `/api`, `/ws`, `/evidence` to the backend (same-origin)
  or the app can call an absolute backend URL baked in at build time (split).

> **Critical constraint:** the backend keeps camera→session bindings and live
> dashboard clients in **process memory** (`SessionHub` in `app/runtime.py`).
> That state is not shared between instances or workers, so the production MVP
> runs a **single always-on backend instance** (`min=max=1`, `--workers 1`).
> See [WebSockets on Cloud Run](#websockets-on-cloud-run) before changing this.

---

## 0. What you need installed

- `gcloud` CLI (authenticated: `gcloud auth login`, `gcloud config set project <id>`)
- Docker + `docker compose` (for local runs only)
- For the Android viewer: Android Studio (SDK + JDK 17), Node 20+

Two Python packages are **only needed in prod** and are commented out in
`backend/requirements.txt` — uncomment them (or install into the image) before
deploying:

- `google-cloud-storage` — GCS evidence storage (`STORAGE_BACKEND=gcs`).
  `app/storage.py` imports it lazily, so local runs don't need it.
- `psycopg2-binary` — PostgreSQL driver for Cloud SQL.

---

## 1. Local full stack (docker compose)

```bash
docker compose up --build
```

- Frontend: <http://localhost:8081> (nginx proxies `/api`, `/ws`, `/evidence`
  to the backend — no CORS, single origin).
- Backend API docs: <http://localhost:8080/docs>, health: `/health`.
- The frontend image is built with an **empty** `VITE_API_BASE`, so the app
  uses relative URLs and relies on the nginx proxy (`BACKEND_URL=http://backend:8080`).

Optional Postgres instead of SQLite:

```bash
docker compose --profile pg up --build
# then set backend DB_URL to:
#   postgresql+psycopg2://orguard:orguard@db:5432/orguard
```

The camera station is `http://localhost:8081/capture`; the monitor view is under
a session. `getUserMedia` needs a secure context — `localhost` counts as secure,
so the webcam works locally without HTTPS.

---

## 2. Deploy to Google Cloud

### 2.1 Enable APIs

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com
```

### 2.2 Artifact Registry repo

```bash
gcloud artifacts repositories create orguard \
  --repository-format=docker --location=us-central1
```

### 2.3 Cloud SQL (PostgreSQL)

```bash
gcloud sql instances create orguard-db \
  --database-version=POSTGRES_15 --tier=db-f1-micro --region=us-central1

gcloud sql databases create orguard --instance=orguard-db
gcloud sql users set-password postgres --instance=orguard-db --password='<DB_PASSWORD>'
```

The instance **connection name** is `PROJECT:us-central1:orguard-db`
(`gcloud sql instances describe orguard-db --format='value(connectionName)'`).

Cloud Run reaches Cloud SQL over a Unix socket mounted at
`/cloudsql/<connection-name>` (added via `--add-cloudsql-instances`, which the
cloudbuild already does). The SQLAlchemy URL uses the socket via the `host`
query param:

```
postgresql+psycopg2://postgres:<DB_PASSWORD>@/orguard?host=/cloudsql/PROJECT:us-central1:orguard-db
```

SQLite remains the default (`sqlite:///./orguard.db`) for local runs.

### 2.4 GCS evidence bucket

```bash
gcloud storage buckets create gs://orguard-evidence-<project> --location=us-central1
```

The backend uploads to `gs://<bucket>/evidence/<file>.jpg` and returns
`https://storage.googleapis.com/<bucket>/evidence/<file>.jpg`. That URL is only
viewable if the object is readable. Pick one:

- **Public read (simplest for the demo):**
  ```bash
  gcloud storage buckets add-iam-policy-binding gs://orguard-evidence-<project> \
    --member=allUsers --role=roles/storage.objectViewer
  ```
- **Private + signed URLs:** keep the bucket private and change `_upload_gcs` in
  `app/storage.py` to `blob.generate_signed_url(...)`. Signing needs a key or
  `roles/iam.serviceAccountTokenCreator` on the runtime service account.

Grant the Cloud Run runtime service account write access:

```bash
gcloud storage buckets add-iam-policy-binding gs://orguard-evidence-<project> \
  --member=serviceAccount:<PROJECT_NUMBER>-compute@developer.gserviceaccount.com \
  --role=roles/storage.objectAdmin
```

### 2.5 Secret Manager — the DB URL

Store the full SQLAlchemy URL (it contains the password) as a secret; the
cloudbuild wires it in with `--set-secrets=DB_URL=orguard-db-url:latest`.

```bash
printf 'postgresql+psycopg2://postgres:<DB_PASSWORD>@/orguard?host=/cloudsql/PROJECT:us-central1:orguard-db' \
  | gcloud secrets create orguard-db-url --data-file=-

# allow the runtime SA to read it
gcloud secrets add-iam-policy-binding orguard-db-url \
  --member=serviceAccount:<PROJECT_NUMBER>-compute@developer.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

### 2.5b Secret Manager — the Gemini API key

The backend reads `GEMINI_API_KEY`; the cloudbuild wires it in alongside the DB
URL via `--set-secrets`. Without it the app still runs — every Gemini feature
falls back to rule-based text — but the AI narration and report summary go away.

```bash
printf '<YOUR_GEMINI_API_KEY>' | gcloud secrets create orguard-gemini-key --data-file=-

gcloud secrets add-iam-policy-binding orguard-gemini-key \
  --member=serviceAccount:<PROJECT_NUMBER>-compute@developer.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

Rotate the key with `gcloud secrets versions add orguard-gemini-key --data-file=-`;
`:latest` picks it up on the next deploy.

Also grant the runtime SA `roles/cloudsql.client` so it can open the socket:

```bash
gcloud projects add-iam-policy-binding PROJECT \
  --member=serviceAccount:<PROJECT_NUMBER>-compute@developer.gserviceaccount.com \
  --role=roles/cloudsql.client
```

### 2.6 Build + deploy (two passes)

The frontend bakes the backend URL at build time and the backend needs the
frontend origin for CORS, so run cloudbuild twice.

**Pass 1 — build images + deploy backend to learn its URL:**

```bash
gcloud builds submit --config deploy/cloudbuild.yaml \
  --substitutions=_REGION=us-central1,_AR=orguard,\
_GCS_BUCKET=orguard-evidence-<project>,\
_CLOUDSQL_INSTANCE=PROJECT:us-central1:orguard-db
```

Read the URLs:

```bash
gcloud run services describe orguard-backend  --region=us-central1 --format='value(status.url)'
gcloud run services describe orguard-frontend --region=us-central1 --format='value(status.url)'
```

**Pass 2 — rebuild the frontend against the real backend URL and set CORS:**

```bash
gcloud builds submit --config deploy/cloudbuild.yaml \
  --substitutions=_REGION=us-central1,_AR=orguard,\
_GCS_BUCKET=orguard-evidence-<project>,\
_CLOUDSQL_INSTANCE=PROJECT:us-central1:orguard-db,\
_API_URL=https://orguard-backend-xxx.run.app,\
_CORS_ORIGINS=https://orguard-frontend-xxx.run.app
```

Open the **frontend** URL. The camera station is `<frontend-url>/capture`
(HTTPS from Cloud Run satisfies `getUserMedia`).

---

## WebSockets on Cloud Run

Cloud Run supports WebSockets, but ORGuard's in-process `SessionHub` makes the
scaling model the important part.

- **Single instance is the MVP choice.** `SessionHub` holds camera→session
  bindings and the set of live dashboard WebSockets **in memory**. If a camera
  ingests on instance A but a dashboard connects to instance B, B has no clients
  for that session and sees nothing. So the cloudbuild pins
  `--min-instances=1 --max-instances=1`. This is deliberate, not a placeholder.
- **`--workers 1`** in the backend Dockerfile for the same reason — multiple
  uvicorn workers are separate processes with separate `SessionHub` copies.
- **`--timeout=3600`** so long OR sessions aren't cut at the default 5 min. This
  is the max request timeout; a WebSocket counts as one long request. nginx
  mirrors this with `proxy_read_timeout 3600s` when proxying.
- **`--session-affinity`** is set so a client's requests stick to the instance.
  With `max-instances=1` affinity is moot, but it keeps behaviour correct if you
  ever raise the ceiling temporarily.
- **`--no-cpu-throttling`** keeps CPU allocated between request bursts so the
  perception loop and the warmed model stay responsive on the always-on instance.
- **Concurrency:** the default (80) is fine — all connections share the one
  process and the one `SessionHub`, which is exactly what we want.

**To scale beyond one instance** you must externalize the hub state (e.g. Redis
pub/sub for fan-out and a shared camera→session map) and drop
`min=max=1`/`--workers 1`. That is out of scope for the MVP.

---

## GPU / image size notes

- The backend image is **large (~3–5 GB)**: torch, torchvision, ultralytics,
  mediapipe and opencv-contrib. The Dockerfile installs **CPU-only** torch from
  the PyTorch CPU wheel index to avoid ~2 GB of unusable CUDA libraries. If the
  pinned versions aren't on that index, build with
  `--build-arg TORCH_INDEX_URL=https://pypi.org/simple` (bigger image).
- First backend cold start downloads the YOLO weights (`yolo11n.pt`); the
  always-on instance keeps them warm.
- **GPU:** managed Cloud Run now supports GPUs (e.g. NVIDIA L4) in some regions,
  or use a GPU VM / GKE. The perception layer is isolated in `app/perception`,
  so moving inference off CPU is contained. For the MVP, CPU on one instance is
  sufficient.

---

## Android viewer APK (Capacitor)

The Android app is a **viewer** — it wraps the built web app and points at the
cloud backend. It does not capture a camera.

```bash
cd frontend
npm install

# Build web assets pointing at the deployed backend (absolute URL required in
# the APK because it loads from a local origin).
VITE_API_BASE=https://orguard-backend-xxx.run.app npm run build

npx cap add android      # first time only
npx cap sync android
npx cap open android      # then Build > Build APK in Android Studio
```

Rebuild assets (`npm run build`) + `npx cap sync android` after any web change.
The viewer only displays a relayed feed, so it needs no camera permission.

---

## WHAT THE USER MUST PROVIDE

| Item | Example / notes |
|------|-----------------|
| **GCP project id** | `my-orguard-proj` — `gcloud config set project <id>` |
| **Billing enabled** | Required for Cloud Run, Cloud SQL, Artifact Registry, GCS |
| **Region** | Default `us-central1`. Keep it consistent across every step and the `_REGION` substitution |
| **GPU?** | No for the MVP (CPU, 1 instance). Say yes only if you need higher fps / more cameras — then plan a GPU Cloud Run service or VM |
| **DB password** | Used in the Cloud SQL user and in the `orguard-db-url` secret |
| **GCS bucket name** | e.g. `orguard-evidence-<project>` — must be globally unique; pass as `_GCS_BUCKET` |
| **Cloud SQL connection name** | `PROJECT:REGION:orguard-db` — pass as `_CLOUDSQL_INSTANCE` |
| **Backend & frontend URLs** | Learned after pass 1; feed back as `_API_URL` and `_CORS_ORIGINS` on pass 2 |
| **requirements.txt prod deps** | Uncomment `psycopg2-binary` and `google-cloud-storage` before deploying |
| **Evidence access model** | Public-read bucket (simple) vs private + signed URLs |
