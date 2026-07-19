import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Session } from "../lib/api";
import { store } from "../lib/store";

export default function Sessions() {
  const nav = useNavigate();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [name, setName] = useState("Simulated Appendectomy");
  const [room, setRoom] = useState("Demo OR 1");
  const [busy, setBusy] = useState(false);

  const refresh = () => api.listSessions().then(setSessions).catch(console.error);
  useEffect(() => {
    refresh();
  }, []);

  const start = async () => {
    setBusy(true);
    try {
      const s = await api.createSession(name, room);
      store.setSession(s.id);
      nav(`/monitor/${s.id}`);
    } finally {
      setBusy(false);
    }
  };

  const statusColor = (s: string) =>
    s === "active"
      ? "text-emerald-400"
      : s === "review"
      ? "text-amber-400"
      : "text-slate-400";

  return (
    <div className="grid md:grid-cols-3 gap-6">
      <section className="md:col-span-1 bg-panel border border-edge rounded-xl p-5 h-fit">
        <h2 className="font-semibold mb-4">New procedure session</h2>
        <label className="block text-xs text-slate-400 mb-1">Procedure name</label>
        <input
          className="w-full mb-3 bg-ink border border-edge rounded-md px-3 py-2 text-sm"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <label className="block text-xs text-slate-400 mb-1">Operating room</label>
        <input
          className="w-full mb-4 bg-ink border border-edge rounded-md px-3 py-2 text-sm"
          value={room}
          onChange={(e) => setRoom(e.target.value)}
        />
        <button
          onClick={start}
          disabled={busy}
          className="w-full bg-sky-600 hover:bg-sky-500 disabled:opacity-50 rounded-md py-2 text-sm font-medium"
        >
          {busy ? "Starting…" : "Start & monitor"}
        </button>
      </section>

      <section className="md:col-span-2">
        <h2 className="font-semibold mb-4">Sessions</h2>
        <div className="space-y-2">
          {sessions.length === 0 && (
            <p className="text-sm text-slate-500">No sessions yet.</p>
          )}
          {sessions.map((s) => (
            <div
              key={s.id}
              className="bg-panel border border-edge rounded-lg px-4 py-3 flex items-center gap-4"
            >
              <div className="flex-1">
                <div className="font-medium text-sm">{s.procedure_name}</div>
                <div className="text-xs text-slate-500">
                  {s.room_name} · {new Date(s.created_at).toLocaleString()}
                </div>
              </div>
              <span className={`text-xs font-medium ${statusColor(s.status)}`}>
                {s.status}
              </span>
              <div className="flex gap-1.5">
                <button
                  onClick={() => {
                    store.setSession(s.id);
                    nav(`/monitor/${s.id}`);
                  }}
                  className="text-xs px-2.5 py-1 rounded bg-edge hover:bg-sky-700"
                >
                  Monitor
                </button>
                <button
                  onClick={() => {
                    store.setSession(s.id);
                    nav(`/report/${s.id}`);
                  }}
                  className="text-xs px-2.5 py-1 rounded bg-edge hover:bg-sky-700"
                >
                  Report
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
