// REST client for the ORGuard backend. Same-origin in dev via Vite proxy;
// absolute (VITE_API_BASE) in the packaged Android app.
import { API_BASE } from "./config";

const f = (path: string, init?: RequestInit) => fetch(API_BASE + path, init);

export interface Session {
  id: string;
  procedure_name: string;
  room_name: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
}

export interface Camera {
  id: string;
  name: string;
  camera_type: string;
  status: string;
}

export interface Zone {
  id?: string;
  camera_id: string;
  name: string;
  zone_type: string;
  polygon: number[][]; // normalized [[x,y],...]
}

export interface SafetyEvent {
  id: string;
  camera_id: string | null;
  event_type: string;
  severity: "information" | "warning" | "critical";
  title: string;
  description: string;
  confidence: number;
  review_status: string;
  review_note: string;
  evidence_path: string | null;
  meta: Record<string, unknown>;
  occurred_at: string;
}

export interface Snapshot {
  id: string;
  snapshot_type: string;
  captured_at: string;
  total_count: number;
  counts: Record<string, number>;
  image_path: string | null;
}

export interface Report {
  session: Session;
  duration_minutes: number | null;
  initial_counts: Record<string, number>;
  final_counts: Record<string, number>;
  count_difference: Record<string, number>;
  hygiene_events: number;
  hygiene_violations: number;
  breach_alerts: number;
  confirmed_alerts: number;
  dismissed_alerts: number;
  overall_status: string;
  critical_timeline: SafetyEvent[];
}

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
  createSession: (procedure_name: string, room_name: string) =>
    f("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ procedure_name, room_name }),
    }).then(j<Session>),

  listSessions: () => f("/api/sessions").then(j<Session[]>),
  getSession: (id: string) => f(`/api/sessions/${id}`).then(j<Session>),
  endSession: (id: string) =>
    f(`/api/sessions/${id}/end`, { method: "POST" }).then(j<Session>),

  createCamera: (name: string, camera_type: string) =>
    f("/api/cameras", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, camera_type }),
    }).then(j<Camera>),

  bindCamera: (session_id: string, camera_id: string) =>
    f(`/api/sessions/${session_id}/bind-camera?camera_id=${camera_id}`, {
      method: "POST",
    }).then(j<{ ok: boolean }>),

  getZones: (session_id: string) =>
    f(`/api/sessions/${session_id}/zones`).then(j<Zone[]>),
  saveZones: (session_id: string, camera_id: string, zones: Zone[]) =>
    f(`/api/sessions/${session_id}/zones`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ camera_id, zones }),
    }).then(j<Zone[]>),

  getEvents: (session_id: string) =>
    f(`/api/sessions/${session_id}/events`).then(j<SafetyEvent[]>),
  getSnapshots: (session_id: string) =>
    f(`/api/sessions/${session_id}/snapshots`).then(j<Snapshot[]>),
  reviewEvent: (event_id: string, decision: string, note: string) =>
    f(`/api/events/${event_id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, note }),
    }).then(j<SafetyEvent>),

  getReport: (session_id: string) =>
    f(`/api/sessions/${session_id}/report`).then(j<Report>),

  captureSnapshot: (session_id: string, snapshot_type: string) =>
    f(`/api/sessions/${session_id}/snapshot?snapshot_type=${snapshot_type}`, {
      method: "POST",
    }).then(j<Snapshot>),
};
