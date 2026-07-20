# ORGuard — Android viewer APK build runbook

This is the precise, ordered procedure to produce an installable Android APK of
the ORGuard **viewer**.

> **Viewer-only.** This app wraps the built web UI and *displays* the relayed
> live feed + safety alerts. It does **not** capture a camera and declares no
> camera permission. The camera comes from a separate **camera station** — a
> device running the `/capture` page in a normal browser (see `deploy/README.md`
> section C). Do not add camera capture to this APK.

All commands run from the repository's `frontend/` directory unless noted.
Node lives at `C:\Program Files\nodejs` (v24 / npm 11) and is not on PATH on the
build machine — invoke `npm`/`npx` with the full path there, or add it to PATH.

---

## 0. Prerequisites (install once)

- **JDK 17** (Temurin/Adoptium or the one bundled with Android Studio).
- **Android Studio** (recommended) — installs the **Android SDK**, platform
  tools (`adb`), and the emulator. Open it once and let it install a recent
  SDK Platform + Build-Tools.
  - Or, headless: Android **command-line tools** + `sdkmanager` to install
    `platform-tools`, a `platforms;android-XX`, and `build-tools;XX.y.z`.
- **Node 20+** (this repo builds on Node 24).
- Environment variables so Gradle can find the SDK/JDK:
  - `ANDROID_HOME` → your SDK path
    (Windows default: `%LOCALAPPDATA%\Android\Sdk`).
  - `JAVA_HOME` → your JDK 17 path.
- A **deployed backend URL** (Cloud Run) — see the checklist at the end.

Install web dependencies once:

```bash
cd frontend
npm install
```

---

## 1. Build the web app pointing at the PRODUCTION backend

The viewer loads bundled assets from a local origin, so it must call an
**absolute** backend URL. That URL is baked in at web-build time via
`VITE_API_BASE` (read in `src/lib/config.ts`). The WebSocket base is derived
automatically from it (`https` → `wss`), so you normally set only
`VITE_API_BASE`.

Use the **https** Cloud Run backend URL (service `orguard-backend`, per
`deploy/cloudbuild.yaml`):

**bash / macOS / Linux / Git Bash:**
```bash
VITE_API_BASE=https://orguard-backend-xxxx.run.app npm run build
```

**Windows PowerShell:**
```powershell
$env:VITE_API_BASE="https://orguard-backend-xxxx.run.app"; npm run build
```

> For local testing against an http / LAN backend (e.g.
> `http://192.168.1.50:8000`) you must ALSO allow cleartext in the native sync —
> see step 3. Production stays https and needs no cleartext.

Output lands in `frontend/dist/` (this is Capacitor's `webDir`).

---

## 2. Add the Android platform (first time only)

```bash
npx cap add android          # or: npm run android:add
```

This scaffolds `frontend/android/` (a Gradle project). Run it once; commit or
keep it locally as you prefer. It is safe to delete and re-add.

---

## 3. Sync web assets + plugins into the native project

After every web rebuild, copy `dist/` and plugin config into the Android
project:

```bash
npx cap sync android         # native-only sync
# or do build + sync in one step:
npm run android:sync         # == npm run build && cap sync android
```

**Local http/LAN backend only** — enable cleartext for this sync (default is
off so release builds stay https-correct):

```bash
# bash
CAP_CLEARTEXT=1 npx cap sync android
# PowerShell
$env:CAP_CLEARTEXT="1"; npx cap sync android
```

---

## 4a. Build a DEBUG APK (quick install / testing)

Use Gradle directly:

```bash
cd android

# macOS / Linux / Git Bash
./gradlew assembleDebug

# Windows PowerShell / cmd
.\gradlew.bat assembleDebug
```

Output APK:

```
frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

This APK is signed with Android's auto-generated debug key — fine for testing on
your own devices, **not** for distribution.

## 4b. Build via Android Studio (GUI)

```bash
npx cap open android         # or: npm run android:open
```

Then in Android Studio: **Build ▸ Build Bundle(s) / APK(s) ▸ Build APK(s)**.
A notification links to the generated `app-debug.apk`. Use **Run ▸ Run 'app'**
to build + install onto a connected device/emulator in one action.

---

## 5. Build a signed RELEASE APK (for distribution)

Debug APKs cannot be distributed. Produce a release build signed with your own
keystore.

### 5.1 Create a keystore (once — keep it safe and backed up)

```bash
keytool -genkey -v -keystore orguard-release.jks \
  -keyalg RSA -keysize 2048 -validity 10000 -alias orguard
```

Record the keystore password, key alias, and key password. **If you lose this
keystore you cannot ship updates to the same app** — store it securely.

### 5.2 Point Gradle at the keystore

Create `frontend/android/keystore.properties` (do NOT commit it):

```properties
storeFile=/absolute/path/to/orguard-release.jks
storePassword=********
keyAlias=orguard
keyPassword=********
```

Wire it into `frontend/android/app/build.gradle` (inside `android { }`):

```gradle
def keystoreProps = new Properties()
def keystorePropsFile = rootProject.file("keystore.properties")
if (keystorePropsFile.exists()) {
    keystoreProps.load(new FileInputStream(keystorePropsFile))
}

signingConfigs {
    release {
        storeFile file(keystoreProps['storeFile'])
        storePassword keystoreProps['storePassword']
        keyAlias keystoreProps['keyAlias']
        keyPassword keystoreProps['keyPassword']
    }
}
buildTypes {
    release {
        signingConfig signingConfigs.release
        minifyEnabled false
    }
}
```

> Note: `frontend/android/` is generated by `npx cap add android`. Editing files
> under it is expected when configuring signing; it is not owned by another
> workflow.

### 5.3 Build the signed APK

```bash
cd android
./gradlew assembleRelease        # Windows: .\gradlew.bat assembleRelease
```

Output:

```
frontend/android/app/build/outputs/apk/release/app-release.apk
```

For the Play Store, build an **AAB** instead: `./gradlew bundleRelease` →
`app/build/outputs/bundle/release/app-release.aab`.

---

## 6. Install on a device

1. Enable **Developer options ▸ USB debugging** on the Android device and
   connect it (or start an emulator from Android Studio's Device Manager).
2. Confirm it is visible:
   ```bash
   adb devices
   ```
3. Install:
   ```bash
   adb install -r app/build/outputs/apk/debug/app-debug.apk
   # or the release APK path
   ```
   `-r` reinstalls over an existing copy.

Alternatively, sideload: copy the `.apk` to the device and open it (requires
"Install unknown apps" for the file manager/browser).

Launch **ORGuard**, open a session's **Monitor** view — it connects to the
baked-in backend over https/wss and shows the live feed + alerts.

---

## 7. Updating the app after a web change

```bash
# rebuild web assets (re-supply the backend URL) then sync:
VITE_API_BASE=https://orguard-backend-xxxx.run.app npm run build
npx cap sync android
# then rebuild the APK (step 4 or 5) and reinstall (step 6)
```

---

## WHAT THE USER MUST PROVIDE

- [ ] **Deployed backend URL** — the Cloud Run **https** URL of the
      `orguard-backend` service (e.g. `https://orguard-backend-xxxx.run.app`),
      passed as `VITE_API_BASE` at web-build time. WS is derived automatically.
- [ ] **Android build toolchain** — Android Studio (or command-line tools) with
      the Android SDK + platform-tools, plus **JDK 17**; `ANDROID_HOME` and
      `JAVA_HOME` set.
- [ ] **A signing keystore** (`.jks`) with its passwords/alias — required only
      to build the distributable **release** APK/AAB (step 5). Debug builds do
      not need it. Keep it backed up.
- [ ] **A target** — a physical Android device with USB debugging enabled, or an
      emulator/AVD, to install and run the APK.

## Handy npm scripts (in `frontend/package.json`)

- `npm run android:add`   — `cap add android` (first-time platform scaffold)
- `npm run android:sync`  — `npm run build && cap sync android`
- `npm run android:build` — `npm run build && cap sync android`
- `npm run cap:sync`      — `cap sync android` (native-only, no web rebuild)
- `npm run android:open`  — open the project in Android Studio

(The actual APK is produced by Gradle / Android Studio — steps 4–5 above.)
