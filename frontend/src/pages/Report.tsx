import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, Report as ReportT } from "../lib/api";
import { store } from "../lib/store";

function Stat({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <div className="bg-panel border border-edge rounded-xl p-4">
      <div className={`text-2xl font-semibold ${tone || ""}`}>{value}</div>
      <div className="text-xs text-slate-400 mt-1">{label}</div>
    </div>
  );
}

export default function Report() {
  const params = useParams();
  const nav = useNavigate();
  const sessionId = params.sessionId || store.getSession();
  const [r, setReport] = useState<ReportT | null>(null);

  useEffect(() => {
    if (sessionId) api.getReport(sessionId).then(setReport).catch(console.error);
  }, [sessionId]);

  if (!sessionId) return <p className="text-sm text-slate-400">No session selected.</p>;
  if (!r) return <p className="text-sm text-slate-500">Loading report…</p>;

  const diffEntries = Object.entries(r.count_difference);
  const reviewNeeded = r.overall_status === "Review required";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div>
          <h2 className="font-semibold text-lg">{r.session.procedure_name}</h2>
          <p className="text-xs text-slate-500">
            {r.session.room_name} · {r.duration_minutes ?? "—"} min
          </p>
        </div>
        <span
          className={`ml-auto text-sm px-3 py-1 rounded-full ${
            reviewNeeded ? "bg-amber-600" : "bg-emerald-600"
          }`}
        >
          {r.overall_status}
        </span>
        <button onClick={() => nav(`/review/${sessionId}`)} className="btn-ghost text-sm">
          Open review
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Hygiene events observed" value={r.hygiene_events} tone="text-emerald-400" />
        <Stat
          label="Possible hygiene violations"
          value={r.hygiene_violations}
          tone={r.hygiene_violations ? "text-amber-400" : ""}
        />
        <Stat
          label="Sterile-field alerts"
          value={r.breach_alerts}
          tone={r.breach_alerts ? "text-red-400" : ""}
        />
        <Stat label="Confirmed / dismissed" value={`${r.confirmed_alerts} / ${r.dismissed_alerts}`} />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-panel border border-edge rounded-xl p-4">
          <h3 className="font-semibold text-sm mb-3">Instrument count</h3>
          <div className="grid grid-cols-3 text-xs text-slate-400 mb-1">
            <span>Type</span>
            <span className="text-center">Initial</span>
            <span className="text-center">Final</span>
          </div>
          {Array.from(
            new Set([...Object.keys(r.initial_counts), ...Object.keys(r.final_counts)])
          ).map((k) => {
            const missing = (r.count_difference[k] || 0) !== 0;
            return (
              <div
                key={k}
                className={`grid grid-cols-3 text-sm py-1 ${missing ? "text-red-400" : ""}`}
              >
                <span className="capitalize">{k}</span>
                <span className="text-center">{r.initial_counts[k] ?? 0}</span>
                <span className="text-center">{r.final_counts[k] ?? 0}</span>
              </div>
            );
          })}
          {diffEntries.length > 0 && (
            <p className="text-xs text-red-400 mt-2">
              Possible missing:{" "}
              {diffEntries.map(([k, v]) => `${v} ${k}`).join(", ")} — requires review.
            </p>
          )}
        </div>

        <div className="bg-panel border border-edge rounded-xl p-4">
          <h3 className="font-semibold text-sm mb-3">Critical timeline</h3>
          <div className="space-y-2 max-h-72 overflow-auto">
            {r.critical_timeline.length === 0 && (
              <p className="text-xs text-slate-500">No warning/critical events.</p>
            )}
            {r.critical_timeline.map((e) => (
              <div key={e.id} className="flex gap-2 text-xs">
                <span className="text-slate-500 tabular-nums">
                  {new Date(e.occurred_at).toLocaleTimeString()}
                </span>
                <span
                  className={
                    e.severity === "critical" ? "text-red-400" : "text-amber-400"
                  }
                >
                  {e.title}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <p className="text-[11px] text-slate-500">
        ORGuard is a prototype safety aid. All alerts are possible events requiring human
        confirmation and do not constitute clinical determinations.
      </p>
    </div>
  );
}
