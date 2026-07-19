# ORGuard — Android APK & Google Cloud Deployment

## A. Build the Android viewer APK (Capacitor)

The Android app is the **viewer** — it wraps the built web app and points at the
cloud backend. It does not capture a camera.

Prereqs: Android Studio (SDK + JDK 17), Node 20+.

```bash
cd frontend
npm install

# 1) Build web assets pointing at your deployed backend
#    (or a LAN IP like http://192.168.1.50:8000 for local testing)
VITE_API_BASE=https://orguard-backend-xxxx.run.app npm run build

# 2) Add the Android platform (first time only) and sync
npx cap add android
npx cap sync android

# 3) Open in Android Studio and Run/Build > Build APK
npx cap open android
```
The APK installs on a phone/tablet; open it and go to a session's Monitor to see
the live feed + alerts. Rebuild assets (`npm run build`) + `npx cap sync android`
after any web change.

> Because the viewer only *displays* a relayed feed, no camera permission is
> needed in the APK. The camera comes from a separate **camera station** device
> running the `/capture` page in a browser.

## B. Deploy the backend to Google Cloud

### One-time setup
```bash
gcloud artifacts repositories create orguard --repository-format=docker --location=us-central1
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

### Build + deploy (both services)
```bash
gcloud builds submit --config deploy/cloudbuild.yaml \
  --substitutions=_REGION=us-central1,_AR=orguard,_API_URL=https://orguard-backend-xxxx.run.app
```
Deploy the backend once to learn its URL, then re-run with that URL as `_API_URL`
so the frontend build targets it. Notes:
- Backend runs CPU inference — `--memory=4Gi --cpu=2`, `--min-instances=1` keeps
  the per-session world model warm. For higher fps / more cameras, move inference
  to a **GPU-enabled Cloud Run** service or a GPU VM (the perception layer is
  isolated in `app/perception`).
- WebSockets work on Cloud Run; keep `--timeout=3600` for long sessions.

### Database (Cloud SQL for PostgreSQL)
```bash
gcloud sql instances create orguard-db --database-version=POSTGRES_15 \
  --tier=db-f1-micro --region=us-central1
# then set on the backend service:
#   DB_URL=postgresql+psycopg2://USER:PASS@/orguard?host=/cloudsql/PROJECT:us-central1:orguard-db
```
Add `psycopg2-binary` to `backend/requirements.txt` and attach the Cloud SQL
connection to the Cloud Run service. SQLite remains the default for local runs.

### Evidence storage (GCS)
```bash
gsutil mb -l us-central1 gs://orguard-evidence-<project>
# on the backend service:
#   STORAGE_BACKEND=gcs   GCS_BUCKET=orguard-evidence-<project>
```
Add `google-cloud-storage` to requirements; grant the Cloud Run service account
`roles/storage.objectAdmin` on the bucket.

## C. Camera station in production
Open `https://<frontend-url>/capture` on the OR camera device (laptop/phone
browser), pick the session, Start streaming. It uses that device's webcam via
`getUserMedia` (requires https, which Cloud Run provides). Multiple camera
devices can stream into the same session — each registers its own `camera_id`.
