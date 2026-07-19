# ORGuard — Hosting Guide (Google Cloud + Android APK)

A step-by-step runbook to put ORGuard online on **Google Cloud** and build the
**Android viewer APK**. Follow the sections in order the first time.

> For the deep reference (why single-instance, WebSocket details, GPU notes,
> signed-URL storage) see [`deploy/README.md`](deploy/README.md). This file is
> the short, copy-paste path.

---

## What gets hosted

Two services deploy to **Cloud Run**:

| Service | What it is | Cloud Run settings |
|---------|------------|--------------------|
| `orguard-backend` | FastAPI + WebSockets + CPU perception (YOLO / ByteTrack / MediaPipe) | 4Gi / 2 cpu, **1 always-on instance**, `--timeout=3600`, no CPU throttling |
| `orguard-frontend` | Vite/React app built to static files, served by nginx | 256Mi / 1 cpu, scales 0→2 |

Plus **Cloud SQL (Postgres)** for data and a **GCS bucket** for evidence JPEGs.

The **Android app is a viewer** — it bundles the built web app and points at the
deployed backend. It never uses a camera. The camera station stays a browser page
(`<frontend-url>/capture`).

> ⚠️ **Single instance is deliberate.** The backend holds camera→session state in
> process memory (`SessionHub`), so it runs pinned at `min=max=1`, `--workers 1`.
> Do not raise the instance count without externalizing that state (see the deep
> reference). This is fine for the MVP/demo.

---

## Part A — Prerequisites

1. **A GCP project** with **billing enabled**.
2. **`gcloud` CLI** installed and authed:
   ```bash
   gcloud auth login
   gcloud config set project <YOUR_PROJECT_ID>
   ```
   > In this Claude Code session you can run the login yourself by typing
   > `! gcloud auth login` at the prompt.
3. Pick a **region** and use it everywhere. This guide uses `us-central1`.
4. **Uncomment the prod-only Python deps** in `backend/requirements.txt` before
   deploying (they are commented out so local runs stay lean):
   - `psycopg2-binary` — Postgres driver for Cloud SQL
   - `google-cloud-storage` — GCS evidence uploads

For the Android APK you also need **Android Studio** (SDK + JDK 17) and **Node 20+**.

Set these shell variables once (used throughout):

```bash
export PROJECT=<YOUR_PROJECT_ID>
export REGION=us-central1
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
export RUNTIME_SA=${PROJECT_NUMBER}-compute@developer.gserviceaccount.com
export BUCKET=orguard-evidence-$PROJECT        # must be globally unique
export DB_PASSWORD='<choose-a-strong-password>'
```

---

## Part B — One-time Google Cloud setup

### B.1 Enable APIs
```bash
gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  sqladmin.googleapis.com secretmanager.googleapis.com storage.googleapis.com
```

### B.2 Artifact Registry (holds the Docker images)
```bash
gcloud artifacts repositories create orguard \
  --repository-format=docker --location=$REGION
```

### B.3 Cloud SQL (Postgres)
```bash
gcloud sql instances create orguard-db \
  --database-version=POSTGRES_15 --tier=db-f1-micro --region=$REGION
gcloud sql databases create orguard --instance=orguard-db
gcloud sql users set-password postgres --instance=orguard-db --password="$DB_PASSWORD"

# Grab the connection name — you'll pass it to the build:
export CLOUDSQL_INSTANCE=$(gcloud sql instances describe orguard-db --format='value(connectionName)')
echo "$CLOUDSQL_INSTANCE"   # -> PROJECT:us-central1:orguard-db
```

### B.4 GCS evidence bucket
```bash
gcloud storage buckets create gs://$BUCKET --location=$REGION

# Let the backend write objects:
gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member=serviceAccount:$RUNTIME_SA --role=roles/storage.objectAdmin

# Simplest for the demo — make evidence frames publicly viewable:
gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member=allUsers --role=roles/storage.objectViewer
```
> Prefer private storage? Keep the bucket private and switch `_upload_gcs` in
> `backend/app/storage.py` to signed URLs (see the deep reference).

### B.5 Secret Manager — the database URL
The full SQLAlchemy URL contains the password, so store it as a secret. The build
wires it into the backend as `DB_URL`.

```bash
printf 'postgresql+psycopg2://postgres:%s@/orguard?host=/cloudsql/%s' \
  "$DB_PASSWORD" "$CLOUDSQL_INSTANCE" \
  | gcloud secrets create orguard-db-url --data-file=-

# Let the runtime SA read the secret and open the Cloud SQL socket:
gcloud secrets add-iam-policy-binding orguard-db-url \
  --member=serviceAccount:$RUNTIME_SA --role=roles/secretmanager.secretAccessor
gcloud projects add-iam-policy-binding $PROJECT \
  --member=serviceAccount:$RUNTIME_SA --role=roles/cloudsql.client
```

---

## Part C — Build & deploy (two passes)

The frontend bakes the backend URL in at build time, and the backend needs the
frontend origin for CORS. Neither URL exists until after the first deploy, so you
run the build **twice**.

### Pass 1 — build images and deploy the backend to learn its URL
```bash
gcloud builds submit --config deploy/cloudbuild.yaml \
  --substitutions=_REGION=$REGION,_AR=orguard,_GCS_BUCKET=$BUCKET,_CLOUDSQL_INSTANCE=$CLOUDSQL_INSTANCE
```

Read the two service URLs:
```bash
export BACKEND_URL=$(gcloud run services describe orguard-backend  --region=$REGION --format='value(status.url)')
export FRONTEND_URL=$(gcloud run services describe orguard-frontend --region=$REGION --format='value(status.url)')
echo "backend:  $BACKEND_URL"
echo "frontend: $FRONTEND_URL"
```

### Pass 2 — rebuild the frontend against the real backend URL and set CORS
```bash
gcloud builds submit --config deploy/cloudbuild.yaml \
  --substitutions=_REGION=$REGION,_AR=orguard,_GCS_BUCKET=$BUCKET,_CLOUDSQL_INSTANCE=$CLOUDSQL_INSTANCE,_API_URL=$BACKEND_URL,_CORS_ORIGINS=$FRONTEND_URL
```

> The backend deploys with `STORAGE_BACKEND=gcs`, the bucket, the CORS origin,
> and the `DB_URL` secret already wired in by `deploy/cloudbuild.yaml` — you don't
> set those by hand.

### Verify
- Backend health: open `$BACKEND_URL/health` → should report `"perception": true`.
- API docs: `$BACKEND_URL/docs`.
- App: open **`$FRONTEND_URL`**.
- Camera station: **`$FRONTEND_URL/capture`** (Cloud Run's HTTPS satisfies the
  browser's `getUserMedia` secure-context requirement).

> First backend request is a **cold start** — it downloads YOLO weights and warms
> the models; give it up to a minute. The always-on instance stays warm after.

### Redeploying later
Re-run **Pass 2** (it rebuilds both images and redeploys). Bump the image tag to
keep versions distinct: add `,_TAG=v2` (or a git sha) to the substitutions.

---

## Part D — Android viewer APK (Capacitor)

The APK wraps the built web assets and talks to the **remote** backend over the
absolute URL you bake in. Because it loads from a local origin, the backend URL
**must be absolute** (relative `/api` won't work in the APK).

```bash
cd frontend
npm install

# 1. Build web assets pointing at the deployed backend.
#    WS base is auto-derived (https -> wss), so just give the https backend URL.
VITE_API_BASE=$BACKEND_URL npm run build

# 2. Add the Android platform (first time only) and sync the assets in.
npx cap add android      # first time only
npx cap sync android

# 3. Open in Android Studio, then Build > Build Bundle(s)/APK(s) > Build APK(s).
npx cap open android
```

The debug APK lands at:
```
frontend/android/app/build/outputs/apk/debug/app-debug.apk
```
Copy it to a phone and install (enable "install from unknown sources"), or use
`adb install app-debug.apk`.

**After any web change**, rebuild and re-sync:
```bash
VITE_API_BASE=$BACKEND_URL npm run build && npx cap sync android
```

### Notes
- **Viewer-only:** no camera permission is declared (`capacitor.config.ts`). The
  app only displays a relayed feed + alerts. Point the camera station at
  `$FRONTEND_URL/capture` from a laptop or a second phone's browser.
- **Production must use HTTPS/WSS.** Cleartext HTTP is **disabled by default** in
  `capacitor.config.ts`. To test against a local/LAN HTTP backend, opt in per
  sync: `CAP_CLEARTEXT=1 npx cap sync android`.
- **App identity:** `appId = com.orguard.viewer`, `appName = ORGuard`. Change
  these in `frontend/capacitor.config.ts` before a real release build.
- For a **signed release APK** (not debug), create a keystore and configure
  signing in Android Studio (Build > Generate Signed Bundle/APK).

---

## Part E — Sanity checklist before a demo

- [ ] `backend/requirements.txt` has `psycopg2-binary` + `google-cloud-storage` uncommented.
- [ ] Both passes of the build finished green; `$BACKEND_URL/health` shows `perception: true`.
- [ ] `$FRONTEND_URL/capture` opens the camera on the camera device (HTTPS ✓).
- [ ] Creating a session, drawing a zone, and capturing a count all persist (Cloud SQL wired via the `orguard-db-url` secret).
- [ ] An alert's evidence frame URL loads (bucket is public-read, or signed URLs configured).
- [ ] APK built with `VITE_API_BASE=$BACKEND_URL`; opening it shows the live relayed feed + alerts.

---

## What you must provide (quick reference)

| Item | Where it's used |
|------|-----------------|
| GCP project id + billing | `gcloud config set project`, every step |
| Region (default `us-central1`) | Keep consistent; `_REGION` substitution |
| DB password | Cloud SQL user (B.3) + the `orguard-db-url` secret (B.5) |
| GCS bucket name (globally unique) | `_GCS_BUCKET` substitution |
| Cloud SQL connection name | `_CLOUDSQL_INSTANCE` substitution (from B.3) |
| Backend & frontend URLs | Learned after Pass 1 → `_API_URL`, `_CORS_ORIGINS` on Pass 2; `VITE_API_BASE` for the APK |
| Evidence access model | Public-read (simple) vs private + signed URLs |
| GPU? | Not needed for the MVP — CPU on one instance is enough |
