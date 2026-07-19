import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, Session } from "../lib/api";
import { LiveClient } from "../lib/live";
import { store } from "../lib/store";

// The Camera Station: runs on whatever device is the OR camera (a laptop or a
// spare phone browser). It streams webcam frames to the backend; the Android
// viewer app then sees the processed feed. Not part of the viewer APK.
export default function Capture() {
  const params = useParams();
  const videoRef = useRef<HTMLVideoElement>(null);
  const liveRef = useRef<LiveClient | null>(null);

  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState(params.sessionId || store.getSession());
  const [camName, setCamName] = useState("Camera 1");
  const [camType, setCamType] = useState("overhead");
  const [running, setRunning] = useState(false);
  const [fps, setFps] = useState(0);
  const [cameraId, setCameraId] = useState("");

  useEffect(() => {
    api.listSessions().then(setSessions).catch(console.error);
  }, []);

  const start = async () => {
    if (!sessionId) return;
    const cam = await api.createCamera(camName, camType);
    setCameraId(cam.id);
    await api.bindCamera(sessionId, cam.id);
    const live = new LiveClient(cam.id, {
      video: videoRef.current!,
      fps: 8,
      onFrame: (m) => m.fps && setFps(m.fps),
    });
    await live.start();
    liveRef.current = live;
    setRunning(true);
  };

  const stop = () => {
    liveRef.current?.stop();
    setRunning(false);
  };
  useEffect(() => () => stop(), []);

  return (
    <div className="max-w-xl mx-auto space-y-4">
      <div>
        <h2 className="font-semibold text-lg">Camera Station</h2>
        <p className="text-xs text-slate-500">
          Run this on the device pointed at the tray / sterile field. It streams
          frames to the backend so the viewer app can monitor them.
        </p>
      </div>

      <div className="bg-panel border border-edge rounded-xl p-4 space-y-3">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Session</label>
          <select
            value={sessionId}
            onChange={(e) => {
              setSessionId(e.target.value);
              store.setSession(e.target.value);
            }}
            disabled={running}
            className="w-full bg-ink border border-edge rounded px-2 py-2 text-sm"
          >
            <option value="">— select —</option>
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.procedure_name} ({s.status})
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Camera name</label>
            <input
              value={camName}
              onChange={(e) => setCamName(e.target.value)}
              disabled={running}
              className="w-full bg-ink border border-edge rounded px-2 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Type</label>
            <select
              value={camType}
              onChange={(e) => setCamType(e.target.value)}
              disabled={running}
              className="w-full bg-ink border border-edge rounded px-2 py-2 text-sm"
            >
              {["overhead", "tray", "sink", "entry"].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
        </div>
        {!running ? (
          <button onClick={start} disabled={!sessionId} className="btn-primary w-full">
            ▶ Start streaming
          </button>
        ) : (
          <button onClick={stop} className="btn-danger w-full">
            ■ Stop streaming
          </button>
        )}
      </div>

      <div className="relative bg-black rounded-xl overflow-hidden border border-edge">
        <video ref={videoRef} className="w-full block" muted playsInline />
        {running && (
          <span className="absolute top-2 left-2 text-xs bg-black/60 px-2 py-1 rounded">
            <span className="text-emerald-400">●</span> streaming · {fps} fps
          </span>
        )}
      </div>
      {cameraId && (
        <p className="text-[11px] text-slate-500">camera id: {cameraId}</p>
      )}
    </div>
  );
}
