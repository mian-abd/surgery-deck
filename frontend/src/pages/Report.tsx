import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { SafetyEvent, Session, Snapshot } from "../lib/api";
import { API_BASE, assetUrl } from "../lib/config";
import { store } from "../lib/store";
import Timeline from "../components/Timeline";

// The report endpoint returns richer data than the shared api.ts `Report`
// type. api.ts is not owned here, so we describe the full shape locally and
// fetch it directly. Every field below is real DB-derived data from the API.
interface CountRow {
  instrument: string;
  initial: number;
  final: number;
  difference: number;
}
interface ReviewSummary {
  confirmed: number;
  dismissed: number;
  unclear: number;
  pending: number;
  total: number;
}
interface FullReport {
  session: Session;
  generated_at: string;
  duration_minutes: number | null;
  initial_counts: Record<string, number>;
  final_counts: Record<string, number>;
  count_difference: Record<string, number>;
  count_summary: CountRow[];
  initial_total: number;
  final_total: number;
  count_mismatch: boolean;
  initial_snapshot: Snapshot | null;
  final_snapshot: Snapshot | null;
  total_events: number;
  event_counts_by_type: Record<string, number>;
  hygiene_events: number;
  hygiene_violations: number;
  breach_alerts: number;
  count_mismatch_alerts: number;
  critical_count: number;
  warning_count: number;
  info_count: number;
  confirmed_alerts: number;
  dismissed_alerts: number;
  unclear_alerts: number;
  pending_alerts: number;
  review_summary: ReviewSummary;
  events: SafetyEvent[];
  critical_timeline: SafetyEvent[];
  review_required: boolean;
  overall_status: string;
  gemini_summary?: string | null;
  gemini_key_risks?: string[];
}

const TYPE_LABEL: Record<string, string> = {
  sterile_breach: "Sterile-field breaches",
  hygiene_missing: "Hygiene violations",
  hygiene_ok: "Hygiene checks passed",
  count_mismatch: "Instrument count mismatch",
  instrument_missing: "Instrument missing",
  info: "Information",
};

const sevBadge: Record<string, string> = {
  information: "bg-sky-600 print:bg-sky-100 print:text-sky-800",
  warning: "bg-amber-600 print:bg-amber-100 print:text-amber-800",
  critical: "bg-red-600 print:bg-red-100 print:text-red-800",
};

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone?: string;
}) {
  return (
    <div className="bg-panel border border-edge rounded-xl p-4 print:bg-white print:border-gray-300">
      <div className={`text-2xl font-semibold print:text-black ${tone || ""}`}>{value}</div>
      <div className="text-xs text-slate-400 mt-1 print:text-gray-600">{label}</div>
    </div>
  );
}

function Card({
  title,
  children,
  className = "",
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`bg-panel border border-edge rounded-xl p-4 print:bg-white print:border-gray-300 print:break-inside-avoid ${className}`}
    >
      <h3 className="font-semibold text-sm mb-3 print:text-black">{title}</h3>
      {children}
    </div>
  );
}

export default function Report() {
  const params = useParams();
  const nav = useNavigate();
  const sessionId = params.sessionId || store.getSession();
  const [r, setReport] = useState<FullReport | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    setReport(null);
    setErr(null);
    fetch(`${API_BASE}/api/sessions/${sessionId}/report`)
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return res.json() as Promise<FullReport>;
      })
      .then(setReport)
      .catch((e) => setErr(String(e)));
  }, [sessionId]);

  if (!sessionId) return <p className="text-sm text-slate-400">No session selected.</p>;
  if (err) return <p className="text-sm text-red-400">Failed to load report: {err}</p>;
  if (!r) return <p className="text-sm text-slate-500">Loading report…</p>;

  const reviewNeeded = r.review_required;
  const evidenceEvents = r.events.filter((e) => e.evidence_path);

  // Group all events by type for the breakdown section.
  const grouped = new Map<string, SafetyEvent[]>();
  for (const e of r.events) {
    const arr = grouped.get(e.event_type) || [];
    arr.push(e);
    grouped.set(e.event_type, arr);
  }

  return (
    <div className="space-y-6 print:space-y-4 text-slate-200 print:text-black">
      {/* print-only stylesheet: white page, hide chrome & interactive controls */}
      <style>{`
        @media print {
          @page { margin: 14mm; }
          html, body { background: #fff !important; color: #000 !important; }
          header, nav { display: none !important; }
          main { max-width: none !important; padding: 0 !important; }
          .no-print { display: none !important; }
          img { max-height: 220px; }
        }
      `}</style>

      {/* Header */}
      <div className="flex flex-wrap items-center gap-3 print:border-b print:border-gray-300 print:pb-3">
        <div>
          <h2 className="font-semibold text-lg print:text-black">
            {r.session.procedure_name}
          </h2>
          <p className="text-xs text-slate-500 print:text-gray-600">
            {r.session.room_name} ·{" "}
            {r.duration_minutes != null ? `${r.duration_minutes} min` : "duration —"}
            {r.session.started_at &&
              ` · ${new Date(r.session.started_at).toLocaleString()}`}
          </p>
          <p className="hidden print:block text-[10px] text-gray-500 mt-1">
            Argus end-of-session report · generated{" "}
            {new Date(r.generated_at).toLocaleString()}
          </p>
        </div>
        <span
          className={`ml-auto text-sm px-3 py-1 rounded-full text-white ${
            reviewNeeded
              ? "bg-amber-600 print:bg-amber-100 print:text-amber-800"
              : "bg-emerald-600 print:bg-emerald-100 print:text-emerald-800"
          }`}
        >
          {r.overall_status}
        </span>
        <button
          onClick={() => window.print()}
          className="btn-ghost text-sm no-print"
        >
          Print / PDF
        </button>
        <button
          onClick={() => nav(`/review/${sessionId}`)}
          className="btn-ghost text-sm no-print"
        >
          Open review
        </button>
      </div>

      {/* Gemini narrative summary — omitted entirely when unavailable */}
      {r.gemini_summary && (
        <div className="rounded-xl border border-sky-400/30 bg-gradient-to-br from-sky-500/10 to-fuchsia-500/5 p-4 print:bg-white print:border-gray-300 print:break-inside-avoid">
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded bg-sky-500/20 border border-sky-400/40 text-sky-200 print:text-black print:border-gray-400">
              ✨ Gemini
            </span>
            <h3 className="font-semibold text-sm print:text-black">AI Safety Summary</h3>
          </div>
          <p className="text-sm leading-relaxed text-slate-200 print:text-black">
            {r.gemini_summary}
          </p>
          {!!r.gemini_key_risks?.length && (
            <ul className="mt-3 space-y-1">
              {r.gemini_key_risks.map((risk, i) => (
                <li
                  key={i}
                  className="text-xs text-amber-200 print:text-black flex gap-2"
                >
                  <span className="text-amber-400 print:text-black">▸</span>
                  {risk}
                </li>
              ))}
            </ul>
          )}
          <p className="text-[10px] text-slate-500 mt-3 print:text-gray-600">
            Generated by Google Gemini from the recorded events. Decision support
            only — every item requires human confirmation.
          </p>
        </div>
      )}

      {/* Top-line stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 print:grid-cols-4">
        <Stat label="Total events" value={r.total_events} />
        <Stat
          label="Critical / warning"
          value={`${r.critical_count} / ${r.warning_count}`}
          tone={
            r.critical_count
              ? "text-red-400 print:text-red-700"
              : r.warning_count
              ? "text-amber-400 print:text-amber-700"
              : ""
          }
        />
        <Stat
          label="Sterile-field alerts"
          value={r.breach_alerts}
          tone={r.breach_alerts ? "text-red-400 print:text-red-700" : ""}
        />
        <Stat
          label="Hygiene violations"
          value={r.hygiene_violations}
          tone={r.hygiene_violations ? "text-amber-400 print:text-amber-700" : ""}
        />
      </div>

      {/* Review decisions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 print:grid-cols-4">
        <Stat
          label="Confirmed"
          value={r.confirmed_alerts}
          tone={r.confirmed_alerts ? "text-red-400 print:text-red-700" : ""}
        />
        <Stat label="Dismissed" value={r.dismissed_alerts} />
        <Stat
          label="Unclear"
          value={r.unclear_alerts}
          tone={r.unclear_alerts ? "text-amber-400 print:text-amber-700" : ""}
        />
        <Stat
          label="Awaiting review"
          value={r.pending_alerts}
          tone={r.pending_alerts ? "text-amber-400 print:text-amber-700" : ""}
        />
      </div>

      <div className="grid md:grid-cols-2 gap-4 print:grid-cols-2">
        {/* Instrument count reconciliation */}
        <Card title="Instrument count reconciliation">
          <div className="grid grid-cols-4 text-xs text-slate-400 mb-1 print:text-gray-600">
            <span>Type</span>
            <span className="text-center">Initial</span>
            <span className="text-center">Final</span>
            <span className="text-center">Δ</span>
          </div>
          {r.count_summary.length === 0 && (
            <p className="text-xs text-slate-500 print:text-gray-500">
              No instrument snapshots were captured for this session.
            </p>
          )}
          {r.count_summary.map((row) => {
            const missing = row.difference !== 0;
            return (
              <div
                key={row.instrument}
                className={`grid grid-cols-4 text-sm py-1 print:text-black ${
                  missing ? "text-red-400 print:text-red-700 font-medium" : ""
                }`}
              >
                <span className="capitalize">{row.instrument}</span>
                <span className="text-center">{row.initial}</span>
                <span className="text-center">{row.final}</span>
                <span className="text-center">
                  {row.difference > 0 ? `+${row.difference}` : row.difference}
                </span>
              </div>
            );
          })}
          {r.count_summary.length > 0 && (
            <div className="grid grid-cols-4 text-sm py-1 mt-1 border-t border-edge font-semibold print:border-gray-300 print:text-black">
              <span>Total</span>
              <span className="text-center">{r.initial_total}</span>
              <span className="text-center">{r.final_total}</span>
              <span className="text-center">
                {r.initial_total - r.final_total > 0
                  ? `+${r.initial_total - r.final_total}`
                  : r.initial_total - r.final_total}
              </span>
            </div>
          )}
          <p
            className={`text-xs mt-2 ${
              r.count_mismatch
                ? "text-red-400 print:text-red-700"
                : "text-emerald-400 print:text-emerald-700"
            }`}
          >
            {r.count_mismatch
              ? `Count mismatch — possible missing: ${Object.entries(r.count_difference)
                  .map(([k, v]) => `${v} ${k}`)
                  .join(", ")}. Requires review.`
              : "Counts reconcile."}
          </p>
        </Card>

        {/* Critical timeline via shared component */}
        <Card title="Critical event timeline">
          <div className="max-h-80 overflow-auto print:max-h-none print:overflow-visible">
            <Timeline
              events={r.critical_timeline}
              emptyText="No warning or critical events."
            />
          </div>
        </Card>
      </div>

      {/* Snapshot evidence images */}
      {(r.initial_snapshot?.image_path || r.final_snapshot?.image_path) && (
        <Card title="Instrument snapshots">
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: "Initial", snap: r.initial_snapshot },
              { label: "Final", snap: r.final_snapshot },
            ].map(({ label, snap }) =>
              snap?.image_path ? (
                <figure key={label}>
                  <img
                    src={assetUrl(snap.image_path)}
                    alt={`${label} instrument snapshot`}
                    className="w-full rounded-lg border border-edge object-cover print:border-gray-300"
                  />
                  <figcaption className="text-[11px] text-slate-500 mt-1 print:text-gray-600">
                    {label} · {snap.total_count} items ·{" "}
                    {new Date(snap.captured_at).toLocaleTimeString()}
                  </figcaption>
                </figure>
              ) : (
                <div
                  key={label}
                  className="text-[11px] text-slate-500 print:text-gray-500"
                >
                  {label} snapshot: no image
                </div>
              )
            )}
          </div>
        </Card>
      )}

      {/* Events grouped by type */}
      <Card title="Safety events by type">
        {r.total_events === 0 && (
          <p className="text-xs text-slate-500 print:text-gray-500">
            No safety events recorded this session.
          </p>
        )}
        <div className="space-y-4">
          {Array.from(grouped.entries()).map(([type, list]) => (
            <div key={type} className="print:break-inside-avoid">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium print:text-black">
                  {TYPE_LABEL[type] || type}
                </span>
                <span className="text-xs text-slate-500 print:text-gray-600">
                  {list.length}
                </span>
              </div>
              <div className="space-y-1">
                {list.map((e) => (
                  <div
                    key={e.id}
                    className="flex flex-wrap items-center gap-2 text-xs border-b border-edge/50 py-1 print:border-gray-200"
                  >
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded text-white ${
                        sevBadge[e.severity] || "bg-slate-600"
                      }`}
                    >
                      {e.severity}
                    </span>
                    <span className="print:text-black">{e.title}</span>
                    <span className="text-slate-500 print:text-gray-600">
                      {new Date(e.occurred_at).toLocaleTimeString()}
                    </span>
                    <span className="text-slate-500 print:text-gray-600">
                      {(e.confidence * 100).toFixed(0)}%
                    </span>
                    <span className="ml-auto text-slate-400 print:text-gray-600">
                      {e.review_status}
                    </span>
                    {e.evidence_path && (
                      <span className="text-slate-600 print:text-gray-500 truncate max-w-[10rem]">
                        {e.evidence_path}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Evidence thumbnails */}
      {evidenceEvents.length > 0 && (
        <Card title="Evidence frames">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 print:grid-cols-4">
            {evidenceEvents.map((e) => (
              <figure key={e.id}>
                <img
                  src={assetUrl(e.evidence_path)}
                  alt={e.title}
                  className="w-full h-28 object-cover rounded-lg border border-edge print:border-gray-300"
                />
                <figcaption className="text-[10px] text-slate-500 mt-1 truncate print:text-gray-600">
                  {e.title}
                </figcaption>
              </figure>
            ))}
          </div>
        </Card>
      )}

      <p className="text-[11px] text-slate-500 print:text-gray-500">
        Argus is a prototype safety aid. All alerts are possible events requiring human
        confirmation and do not constitute clinical determinations.
      </p>
    </div>
  );
}
