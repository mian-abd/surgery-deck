import { SafetyEvent } from "../lib/api";

/**
 * Vertical, time-ordered list of safety events. Colour + icon are driven by
 * severity. Reused by the end-of-session Report; exportable for Monitor later.
 */

type Sev = "information" | "warning" | "critical" | string;

const SEV: Record<
  string,
  { dot: string; ring: string; text: string; icon: string; label: string }
> = {
  critical: {
    dot: "bg-red-500",
    ring: "ring-red-500/30",
    text: "text-red-400 print:text-red-700",
    icon: "!",
    label: "Critical",
  },
  warning: {
    dot: "bg-amber-500",
    ring: "ring-amber-500/30",
    text: "text-amber-400 print:text-amber-700",
    icon: "▲",
    label: "Warning",
  },
  information: {
    dot: "bg-sky-500",
    ring: "ring-sky-500/30",
    text: "text-sky-400 print:text-sky-700",
    icon: "i",
    label: "Info",
  },
};

const sevOf = (s: Sev) => SEV[s] ?? SEV.information;

function fmtTime(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function Timeline({
  events,
  emptyText = "No events recorded.",
}: {
  events: SafetyEvent[];
  emptyText?: string;
}) {
  if (!events.length) {
    return <p className="text-xs text-slate-500 print:text-gray-500">{emptyText}</p>;
  }

  return (
    <ol className="relative">
      {/* vertical rail */}
      <span
        className="absolute left-[7px] top-1 bottom-1 w-px bg-edge print:bg-gray-300"
        aria-hidden
      />
      {events.map((e) => {
        const s = sevOf(e.severity);
        return (
          <li key={e.id} className="relative pl-7 pb-4 last:pb-0">
            <span
              className={`absolute left-0 top-1 flex h-4 w-4 items-center justify-center rounded-full ring-4 ${s.dot} ${s.ring} text-[9px] font-bold text-white`}
              title={s.label}
              aria-hidden
            >
              {s.icon}
            </span>
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="text-[11px] tabular-nums text-slate-500 print:text-gray-500">
                {fmtTime(e.occurred_at)}
              </span>
              <span className={`text-sm font-medium ${s.text}`}>{e.title}</span>
              {e.review_status && e.review_status !== "pending" && (
                <span className="text-[10px] uppercase tracking-wide text-slate-500 print:text-gray-500">
                  · {e.review_status}
                </span>
              )}
            </div>
            {e.description && (
              <p className="mt-0.5 text-xs text-slate-400 print:text-gray-600">{e.description}</p>
            )}
            {typeof e.confidence === "number" && e.confidence > 0 && (
              <p className="mt-0.5 text-[10px] text-slate-500 print:text-gray-500">
                confidence {(e.confidence * 100).toFixed(0)}%
              </p>
            )}
          </li>
        );
      })}
    </ol>
  );
}
