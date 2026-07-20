import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, SafetyEvent } from "../lib/api";
import GeminiInsightBlock from "../components/GeminiInsight";
import { assetUrl } from "../lib/config";
import { store } from "../lib/store";

const sevBadge: Record<string, string> = {
  information: "bg-sky-600",
  warning: "bg-amber-600",
  critical: "bg-red-600",
};

const statusChip: Record<string, string> = {
  pending: "bg-slate-700 text-slate-300",
  confirmed: "bg-red-600 text-white",
  dismissed: "bg-slate-600 text-white",
  unclear: "bg-amber-600 text-white",
  further_review: "bg-amber-600 text-white",
};

type Filter = "all" | "pending" | "reviewed";

const TYPE_LABEL: Record<string, string> = {
  sterile_breach: "Sterile breach",
  hygiene_missing: "Hygiene missing",
  hygiene_ok: "Hygiene OK",
  count_mismatch: "Count mismatch",
  instrument_missing: "Instrument missing",
  info: "Info",
};

export default function Review() {
  const params = useParams();
  const nav = useNavigate();
  const sessionId = params.sessionId || store.getSession();
  const [events, setEvents] = useState<SafetyEvent[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [filter, setFilter] = useState<Filter>("all");
  const [loading, setLoading] = useState(true);

  const refresh = () => {
    if (!sessionId) return;
    api
      .getEvents(sessionId)
      .then((ev) => {
        setEvents(ev);
        // seed note inputs with any persisted reviewer notes
        setNotes((prev) => {
          const next = { ...prev };
          for (const e of ev) if (!(e.id in next)) next[e.id] = e.review_note || "";
          return next;
        });
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };
  useEffect(refresh, [sessionId]);

  const decide = async (id: string, decision: string) => {
    setBusy((b) => ({ ...b, [id]: true }));
    try {
      await api.reviewEvent(id, decision, notes[id] || "");
      refresh();
    } finally {
      setBusy((b) => ({ ...b, [id]: false }));
    }
  };

  const counts = useMemo(() => {
    const c = { total: events.length, pending: 0, confirmed: 0, dismissed: 0, unclear: 0 };
    for (const e of events) {
      if (e.review_status === "pending") c.pending++;
      else if (e.review_status === "confirmed") c.confirmed++;
      else if (e.review_status === "dismissed") c.dismissed++;
      else c.unclear++;
    }
    return c;
  }, [events]);

  const shown = useMemo(() => {
    if (filter === "pending") return events.filter((e) => e.review_status === "pending");
    if (filter === "reviewed") return events.filter((e) => e.review_status !== "pending");
    return events;
  }, [events, filter]);

  if (!sessionId) return <p className="text-sm text-slate-400">No session selected.</p>;

  const active = (e: SafetyEvent, d: string) =>
    e.review_status === d || (d === "unclear" && e.review_status === "further_review");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-semibold">Review</h2>
        <div className="flex gap-2 text-xs text-slate-400">
          <span>{counts.total} events</span>
          <span className="text-amber-400">{counts.pending} pending</span>
          <span className="text-red-400">{counts.confirmed} confirmed</span>
          <span>{counts.dismissed} dismissed</span>
          <span className="text-amber-400">{counts.unclear} unclear</span>
        </div>
        <button
          onClick={() => nav(`/report/${sessionId}`)}
          className="btn-ghost text-xs ml-auto"
        >
          View report
        </button>
      </div>

      <div className="flex gap-1 text-xs">
        {(["all", "pending", "reviewed"] as Filter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-2.5 py-1 rounded-md capitalize ${
              filter === f ? "bg-sky-600 text-white" : "bg-edge text-slate-300 hover:bg-slate-700"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {loading && <p className="text-sm text-slate-500">Loading events…</p>}
        {!loading && shown.length === 0 && (
          <p className="text-sm text-slate-500">
            {events.length === 0 ? "No events recorded." : "No events match this filter."}
          </p>
        )}
        {shown.map((e) => (
          <div key={e.id} className="bg-panel border border-edge rounded-xl p-4 flex gap-4">
            {e.evidence_path ? (
              <img
                src={assetUrl(e.evidence_path)}
                className="w-40 h-28 object-cover rounded-lg border border-edge shrink-0"
                alt="evidence"
              />
            ) : (
              <div className="w-40 h-28 rounded-lg border border-dashed border-edge shrink-0 flex items-center justify-center text-[10px] text-slate-600">
                no frame
              </div>
            )}
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`text-[10px] px-2 py-0.5 rounded text-white ${
                    sevBadge[e.severity] || "bg-slate-600"
                  }`}
                >
                  {e.severity}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded bg-edge text-slate-300">
                  {TYPE_LABEL[e.event_type] || e.event_type}
                </span>
                <span className="font-medium text-sm truncate">{e.title}</span>
                <span
                  className={`text-[10px] px-2 py-0.5 rounded ${
                    statusChip[e.review_status] || "bg-slate-700 text-slate-300"
                  }`}
                >
                  {e.review_status}
                </span>
                <span className="ml-auto text-xs text-slate-500">
                  {new Date(e.occurred_at).toLocaleTimeString()}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">{e.description}</p>
              <GeminiInsightBlock insight={(e.meta as any)?.gemini} />
              <p className="text-[11px] text-slate-500 mt-1">
                confidence {(e.confidence * 100).toFixed(0)}%
                {e.review_note && (
                  <>
                    {" "}· note: <span className="text-slate-300">{e.review_note}</span>
                  </>
                )}
              </p>
              <div className="flex flex-wrap items-center gap-2 mt-2">
                <input
                  placeholder="reviewer note…"
                  value={notes[e.id] ?? ""}
                  onChange={(ev) => setNotes((n) => ({ ...n, [e.id]: ev.target.value }))}
                  className="flex-1 min-w-[8rem] bg-ink border border-edge rounded px-2 py-1 text-xs"
                />
                <button
                  onClick={() => decide(e.id, "confirmed")}
                  disabled={busy[e.id]}
                  className={`text-xs rounded-md px-3 py-1.5 font-medium disabled:opacity-40 ${
                    active(e, "confirmed")
                      ? "bg-red-600 ring-2 ring-red-300"
                      : "bg-red-600/70 hover:bg-red-500"
                  }`}
                >
                  Confirm
                </button>
                <button
                  onClick={() => decide(e.id, "dismissed")}
                  disabled={busy[e.id]}
                  className={`btn-ghost text-xs ${active(e, "dismissed") ? "ring-2 ring-slate-300" : ""}`}
                >
                  Dismiss
                </button>
                <button
                  onClick={() => decide(e.id, "unclear")}
                  disabled={busy[e.id]}
                  className={`btn-ghost text-xs ${active(e, "unclear") ? "ring-2 ring-amber-300" : ""}`}
                >
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
