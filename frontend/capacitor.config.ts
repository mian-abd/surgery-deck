import type { CapacitorConfig } from "@capacitor/cli";

// The viewer APK loads the built web assets locally and talks to the cloud
// backend via the absolute VITE_API_BASE baked in at build time. Cleartext is
// allowed only for local testing against an http backend; use https in prod.
const config: CapacitorConfig = {
  appId: "com.orguard.viewer",
  appName: "ORGuard",
  webDir: "dist",
  server: {
    androidScheme: "https",
    cleartext: true,
  },
};

export default config;
