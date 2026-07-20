import type { CapacitorConfig } from "@capacitor/cli";

// ORGuard viewer (Android). The APK bundles the built web assets (webDir) and
// talks to the REMOTE backend over the absolute VITE_API_BASE baked in at
// web-build time (see src/lib/config.ts; the WS base is auto-derived, http→ws /
// https→wss). This is a VIEWER-ONLY app — it displays a relayed feed + alerts
// and never captures a camera, so no camera permission is declared. The camera
// station is a separate browser page (`/capture`).
//
// Production MUST use https/wss (Cloud Run terminates TLS), so cleartext HTTP is
// DISABLED by default to keep release builds correct. Enable it ONLY for local
// testing against an http / LAN backend by exporting CAP_CLEARTEXT=1 before the
// sync, e.g.  CAP_CLEARTEXT=1 npx cap sync android
const allowCleartext = process.env.CAP_CLEARTEXT === "1";

const config: CapacitorConfig = {
  // Reverse-DNS application id (Android package name).
  appId: "com.orguard.viewer",
  appName: "Argus",
  // Vite builds the web app to dist/.
  webDir: "dist",
  server: {
    // Serve bundled assets over the https scheme on Android (secure-context
    // APIs, mixed-content rules); actual backend calls are absolute https URLs.
    androidScheme: "https",
    // Off in production; opt in per above for local/LAN http backends.
    cleartext: allowCleartext,
  },
};

export default config;
