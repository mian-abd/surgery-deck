// API/WS base resolution.
// - Dev / same-origin web build: VITE_API_BASE is empty -> relative URLs, so the
//   Vite proxy (or same origin) forwards /api and /ws to the backend.
// - Packaged Android APK (Capacitor) loads from a local origin, so it must call
//   an absolute backend URL. Build with VITE_API_BASE=https://<cloud-run-url>.

export const API_BASE: string = (import.meta as any).env?.VITE_API_BASE || "";

export const WS_BASE: string = API_BASE
  ? API_BASE.replace(/^http/, "ws")
  : (location.protocol === "https:" ? "wss://" : "ws://") + location.host;

/** Absolute URL for a backend-relative asset (e.g. an evidence image path). */
export function assetUrl(path: string | null | undefined): string | undefined {
  if (!path) return undefined;
  if (/^https?:\/\//.test(path)) return path;
  return API_BASE + path;
}
