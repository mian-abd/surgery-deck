import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, SafetyEvent } from "../lib/api";
import { assetUrl } from "../lib/config";
import { store } from "../lib/store";

const sevBadge: Record<string, string> = {
  information: "bg-sky-600",
  warning: "bg-amber-600",
  critical: "bg-red-600",
};

export default function Review() {
  const params = useParams();
  const sessionId = params.sessionId || store.getSession();
  const [events, setEvents] = useState<SafetyEvent[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});

  const refresh = () => {
    if (sessionId) api.getEvents(sessionId).then(setEvents).catch(console.error);
  };
  useEffect(refresh, [sessionId]);

  const decide = async (id: string, decision: string) => {
    await api.reviewEvent(id, decision, notes[id] || "");
    refresh();
  };

  if (!sessionId) return <p className="text-sm text-slate-400">No session selected.</p>;

  return (
    <div>
      <h2 className="font-semibold mb-4">Review · {events.length} events</h2>
      <div className="space-y-3">
        {events.length === 0 && <p className="text-sm text-slate-500">No events recorded.</p>}
        {events.map((e) => (
          <div key={e.id} className="bg-panel border border-edge rounded-xl p-4 flex gap-4">
            {e.evidence_path && (
              <img
                src={assetUrl(e.evidence_path)}
                className="w-40 h-28 object-cover rounded-lg border border-edge"
                alt="evidence"
              />
            )}
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className={`text-[10px] px-2 py-0.5 rounded ${sevBadge[e.severity]}`}>
                  {e.severity}
                </span>
                <span className="font-medium text-sm">{e.title}</span>
                <span className="ml-auto text-xs text-slate-500">
                  {new Date(e.occurred_at).toLocaleTimeString()}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">{e.description}</p>
              <p className="text-[11px] text-slate-500 mt-1">
                confidence {(e.confidence * 100).toFixed(0)}% · status{" "}
                <span className="text-slate-300">{e.review_status}</span>
              </p>
              <div className="flex items-center gap-2 mt-2">
                <input
                  placeholder="reviewer note…"
                  value={notes[e.id] || ""}
                  onChange={(ev) => setNotes((n) => ({ ...n, [e.id]: ev.target.value }))}
                  className="flex-1 bg-ink border border-edge rounded px-2 py-1 text-xs"
                />
                <button onClick={() => decide(e.id, "confirmed")} className="btn-danger text-xs">
                  Confirm
                </button>
                <button onClick={() => decide(e.id, "dismissed")} className="btn-ghost text-xs">
                  Dismiss
                </button>
                <button onClick={() => decide(e.id, "unclear")} className="btn-ghost text-xs">
                  Unclear
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
