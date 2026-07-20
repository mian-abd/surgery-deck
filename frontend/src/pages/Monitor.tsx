import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import ViewerStage from "../components/ViewerStage";
import GeminiInsightBlock from "../components/GeminiInsight";
import { api, Zone } from "../lib/api";
import {
  AlertMessage,
  DetectionsMessage,
  Detection,
  FrameMessage,
  HandPoint,
  SessionSocket,
} from "../lib/live";
import { store } from "../lib/store";

const ZONE_TYPES = ["sterile", "nonsterile", "tray", "sink", "patient", "entry"];
const sevColor: Record<string, string> = {
  information: "border-sky-500/50 bg-sky-500/10",
  warning: "border-amber-500/50 bg-amber-500/10",
  critical: "border-red-500/60 bg-red-500/10",
};

// Viewer-only dashboard (the Android APK). Receives the relayed feed +
// detections + alerts over /ws/session/{id}. Does not access a camera.
export default function Monitor() {
  const params = useParams();
  const nav = useNavigate();
  const sessionId = params.sessionId || store.getSession();
  const sockRef = useRef<SessionSocket | null>(null);

  const [connected, setConnected] = useState(false);
  const [fps, setFps] = useState(0);
  const [frame, setFrame] = useState<string | null>(null);
  const [cameraId, setCameraId] = useState("");
  const [detections, setDetections] = useState<Detection[]>([]);
  const [hands, setHands] = useState<HandPoint[][]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [alerts, setAlerts] = useState<AlertMessage[]>([]);
  const [demoRunning, setDemoRunning] = useState(false);

  // zone editor
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<number[][]>([]);
  const [zoneType, setZoneType] = useState("sterile");
  const [suggesting, setSuggesting] = useState(false);
  const [suggestNote, setSuggestNote] = useState("");

  useEffect(() => {
    if (!sessionId) return;
    api.getZones(sessionId).then(setZones).catch(() => {});
    const sock = new SessionSocket(sessionId, {
      onFrame: (m: FrameMessage) => {
        setConnected(true); // a frame means a camera is actively streaming
        if (m.image) setFrame(m.image);
        if (m.camera_id) setCameraId(m.camera_id);
        if (m.fps != null) setFps(m.fps);
      },
      onDetections: (m: DetectionsMessage) => {
        if (m.camera_id) setCameraId(m.camera_id);
        if (m.detections) setDetections(m.detections);
        if (m.hands) setHands(m.hands);
      },
      onStatus: (up) => {
        if (!up) setConnected(false); // socket dropped → not live until frames resume
      },
      onAlert: (m) => setAlerts((a) => [m, ...a].slice(0, 50)),
      // Gemini finishes analysing a beat after the alert fires — patch the
      // matching card in place so the AI text appears live on screen.
      onEventUpdate: (m) =>
        setAlerts((a) =>
          a.map((al) => (al.id === m.id ? { ...al, gemini: m.gemini } : al))
        ),
    });
    sock.start();
    sockRef.current = sock;
    return () => sock.stop();
  }, [sessionId]);

  const startDemo = async () => {
    if (!sessionId) return;
    try {
      await api.startDemo(sessionId);
      setDemoRunning(true);
      // demo seeds zones server-side; pull them in so the overlay shows them
      setTimeout(() => api.getZones(sessionId).then(setZones).catch(() => {}), 1500);
    } catch (e) {
      console.error(e);
    }
  };
  const stopDemo = async () => {
    if (!sessionId) return;
    try {
      await api.stopDemo(sessionId);
    } finally {
      setDemoRunning(false);
    }
  };

  const [searchParams] = useSearchParams();
  useEffect(() => {
    if (sessionId && searchParams.get("demo") === "1") {
      startDemo();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const liveCounts = useMemo(() => {
    const c: Record<string, number> = {};
    detections
      .filter((d) => d.label !== "person" && d.label !== "hand")
      .forEach((d) => (c[d.label] = (c[d.label] || 0) + 1));
    return c;
  }, [detections]);

  // Ask Gemini to read the current frame and propose zones. Suggestions are
  // saved like hand-drawn ones so the operator can immediately edit/redraw.
  const suggestZones = async () => {
    if (!sessionId || !cameraId) return;
    setSuggesting(true);
    setSuggestNote("");
    try {
      const { zones: proposed, reason } = await api.suggestZones(sessionId);
      if (!proposed.length) {
        setSuggestNote(reason || "No zones proposed");
        return;
      }
      const next = proposed.map((z) => ({ ...z, camera_id: cameraId }));
      setZones(next);
      await api.saveZones(sessionId, cameraId, next);
      setSuggestNote(`✨ ${next.length} zones proposed — edit if needed`);
    } catch (e) {
      console.error(e);
      setSuggestNote("Suggestion failed");
    } finally {
      setSuggesting(false);
    }
  };

  const finishZone = async () => {
    if (draft.length < 3 || !sessionId || !cameraId) return;
    const next = [
      ...zones,
      { camera_id: cameraId, name: `${zoneType} zone`, zone_type: zoneType, polygon: draft },
    ];
    setZones(next);
    setDraft([]);
    setEditing(false);
    await api.saveZones(sessionId, cameraId, next);
  };

  const snapshot = async (type: "initial" | "final") => {
    if (!sessionId) return;
    try {
      const snap = await api.captureSnapshot(sessionId, type);
      setAlerts((a) => [
        {
          type: "alert",
          event_type: "info",
          severity: "information",
          title: `${type} count captured: ${snap.total_count} instruments`,
          description: Object.entries(snap.counts)
            .map(([k, v]) => `${v} ${k}`)
            .join(", "),
        },
        ...a,
      ]);
    } catch (e) {
      console.error(e);
    }
  };

  const endSession = async () => {
    if (!sessionId) return;
    await snapshot("final");
    await api.endSession(sessionId);
    nav(`/report/${sessionId}`);
  };

  if (!sessionId) return <p className="text-sm text-slate-400">Start a session first.</p>;

  return (
    <div className="grid lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          {!demoRunning ? (
            <button onClick={startDemo} className="btn-primary">
              ▶ Start live demo
            </button>
          ) : (
            <button onClick={stopDemo} className="btn-ghost">
              ■ Stop demo
            </button>
          )}
          <button onClick={() => snapshot("initial")} disabled={!connected} className="btn-ghost">
            Capture initial count
          </button>
          <button onClick={endSession} className="btn-danger">
            End session & report
          </button>
          <span className="ml-auto text-xs text-slate-400">
            {connected ? (
              <>
                <span className="text-emerald-400">●</span> live · {fps} fps
              </>
            ) : (
              <span className="text-slate-500">no feed — click "Start live demo"</span>
            )}
          </span>
        </div>

        <ViewerStage
          frame={frame}
          detections={detections}
          hands={hands}
          zones={zones}
          editing={editing}
          draftPolygon={draft}
          onAddPoint={(x, y) => setDraft((d) => [...d, [x, y]])}
        />

        <div className="bg-panel border border-edge rounded-lg p-3 flex items-center gap-2 flex-wrap">
          <span className="text-xs text-slate-400">Zones:</span>
          {!editing ? (
            <>
              <button
                onClick={() => setEditing(true)}
                disabled={!cameraId}
                className="btn-ghost text-xs"
              >
                + Draw zone
              </button>
              <button
                onClick={suggestZones}
                disabled={!cameraId || suggesting}
                className="btn-ghost text-xs"
                title="Ask Gemini to propose zones from the current frame"
              >
                {suggesting ? "✨ Analyzing…" : "✨ Suggest zones"}
              </button>
              {suggestNote && (
                <span className="text-[11px] text-slate-500">{suggestNote}</span>
              )}
            </>
          ) : (
            <>
              <select
                value={zoneType}
                onChange={(e) => setZoneType(e.target.value)}
                className="bg-ink border border-edge rounded px-2 py-1 text-xs"
              >
                {ZONE_TYPES.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
              <span className="text-xs text-slate-500">tap feed to add points</span>
              <button onClick={finishZone} className="btn-primary text-xs">
                Finish ({draft.length})
              </button>
              <button
                onClick={() => {
                  setDraft([]);
                  setEditing(false);
                }}
                className="btn-ghost text-xs"
              >
                Cancel
              </button>
            </>
          )}
          {zones.map((z, i) => (
            <span key={i} className="text-[11px] px-2 py-0.5 rounded bg-edge">
              {z.zone_type}
            </span>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        <div className="bg-panel border border-edge rounded-xl p-4">
          <h3 className="font-semibold text-sm mb-2">Live instrument count</h3>
          {Object.keys(liveCounts).length === 0 ? (
            <p className="text-xs text-slate-500">No instruments detected.</p>
          ) : (
            <ul className="text-sm space-y-1">
              {Object.entries(liveCounts).map(([k, v]) => (
                <li key={k} className="flex justify-between">
                  <span className="capitalize">{k}</span>
                  <span className="text-slate-300">{v}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="bg-panel border border-edge rounded-xl p-4">
          <h3 className="font-semibold text-sm mb-2">Live alerts</h3>
          <div className="space-y-2 max-h-[420px] overflow-auto">
            {alerts.length === 0 && <p className="text-xs text-slate-500">No alerts yet.</p>}
            {alerts.map((a, i) => (
              <div
                key={i}
                className={`border rounded-lg px-3 py-2 ${sevColor[a.severity] || "border-edge"}`}
              >
                <div className="text-sm font-medium">{a.title}</div>
                {a.description && (
                  <div className="text-xs text-slate-400 mt-0.5">{a.description}</div>
                )}
                <GeminiInsightBlock insight={a.gemini} compact />
                <div className="text-[10px] uppercase tracking-wide text-slate-500 mt-1">
                  {a.severity}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
