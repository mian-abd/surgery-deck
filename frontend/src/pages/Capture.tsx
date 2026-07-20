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
  const [source, setSource] = useState<"camera" | "file">("camera");
  const [targetFps, setTargetFps] = useState(15);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listSessions().then(setSessions).catch(console.error);
  }, []);

  const start = async (fileOverride?: File) => {
    if (!sessionId) return;
    const chosen = fileOverride ?? file;
    if (source === "file" && !chosen) {
      setError("Choose a video file first.");
      return;
    }
    setError("");
    try {
      const cam = await api.createCamera(camName, camType);
      setCameraId(cam.id);
      await api.bindCamera(sessionId, cam.id);
      const live = new LiveClient(cam.id, {
        video: videoRef.current!,
        fps: targetFps,
        onFrame: (m) => m.fps && setFps(m.fps),
      });
      if (source === "file") await live.startFile(chosen!, { loop: true });
      else await live.start();
      liveRef.current = live;
      setRunning(true);
    } catch (e) {
      setError((e as Error).message || "Could not start streaming.");
    }
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

        {/* Source: live webcam or an uploaded video file (same pipeline). */}
        <div>
          <label className="block text-xs text-slate-400 mb-1">Source</label>
          <div className="flex gap-2">
            {(["camera", "file"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSource(s)}
                disabled={running}
                className={`flex-1 rounded px-2 py-2 text-sm border ${
                  source === s
                    ? "border-sky-500 bg-sky-500/10 text-sky-200"
                    : "border-edge bg-ink text-slate-400"
                }`}
              >
                {s === "camera" ? "📷 Live webcam" : "🎞 Upload video"}
              </button>
            ))}
          </div>
        </div>

        {source === "file" && (
          <div>
            <label className="block text-xs text-slate-400 mb-1">Video file</label>
            <input
              type="file"
              accept="video/*"
              disabled={running}
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null;
                setFile(f);
                if (f && sessionId && !running) {
                  // auto-start streaming as soon as a video is chosen — no
                  // separate "Start streaming" click needed for uploads
                  setTimeout(() => start(f), 0);
                }
              }}
              className="w-full text-xs text-slate-300 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-edge file:text-slate-200"
            />
            <p className="text-[11px] text-slate-500 mt-1">Streaming starts automatically when you pick a file.</p>
            {file && <p className="text-[11px] text-slate-500 mt-1">{file.name}</p>}
          </div>
        )}

        <div>
          <label className="block text-xs text-slate-400 mb-1">
            Target frame rate: {targetFps} fps
          </label>
          <input
            type="range"
            min={4}
            max={30}
            step={1}
            value={targetFps}
            disabled={running}
            onChange={(e) => setTargetFps(Number(e.target.value))}
            className="w-full accent-sky-500"
          />
        </div>

        {error && <p className="text-xs text-red-400">{error}</p>}
        {!running ? (
          <button onClick={() => start()} disabled={!sessionId} className="btn-primary w-full">
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
