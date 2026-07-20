import { GeminiInsight as Insight } from "../lib/live";

export function GeminiBadge() {
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded bg-gradient-to-r from-sky-500/20 to-fuchsia-500/20 border border-sky-400/40 text-sky-200">
      ✨ Gemini
    </span>
  );
}

/** Gemini's narration + visual second opinion for a safety event.
 *  Renders nothing when Gemini is unavailable, so the UI degrades quietly. */
export default function GeminiInsightBlock({
  insight,
  compact,
}: {
  insight?: Insight | null;
  compact?: boolean;
}) {
  if (!insight || !insight.explanation) return null;

  const disagrees = insight.agrees === false;
  const pct =
    typeof insight.visual_confidence === "number"
      ? `${Math.round(insight.visual_confidence * 100)}%`
      : null;

  return (
    <div className="mt-2 rounded-lg border border-sky-400/25 bg-sky-400/5 px-2.5 py-2">
      <div className="flex items-center gap-2 mb-1">
        <GeminiBadge />
        {insight.agrees !== undefined && (
          <span
            className={`text-[10px] font-medium ${
              disagrees ? "text-amber-300" : "text-emerald-300"
            }`}
          >
            {disagrees ? "⚠ image does not clearly support this" : "✓ confirmed in frame"}
            {pct ? ` · ${pct}` : ""}
          </span>
        )}
      </div>

      <p className="text-xs text-slate-200 leading-relaxed">{insight.explanation}</p>

      {!compact && insight.recommended_action && (
        <p className="text-xs text-slate-300 mt-1.5">
          <span className="text-slate-400">Recommended: </span>
          {insight.recommended_action}
        </p>
      )}

      {!compact && insight.verification_reason && (
        <p className="text-[11px] text-slate-400 mt-1.5 italic">
          {insight.verification_reason}
        </p>
      )}
    </div>
  );
}
