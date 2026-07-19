import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API base is read at runtime from window/env; dev proxy forwards /api and
// /ws to the FastAPI backend so the browser talks to a single origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/evidence": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
});
