"use client";

import { groundedIn, hasGrounding } from "@/lib/copilot/grounding";
import type { ClassifiedStatement, EvidenceSummary } from "@/types/chat";
import { cn } from "@/lib/utils";

/**
 * How much of a finished answer is carried by the passages that were cited.
 *
 * Deliberately reported as counts, not as a verdict per sentence. The backend
 * classifier is lexical overlap against the cited chunk — measured at 78.8%
 * on an answer's own citations versus 30.1% on unrelated ones. That gap is
 * real signal, but a ~30% floor is far too high to call anything a "fact",
 * so nothing here claims verification. See
 * `backend/app/services/evidence_classification.py`.
 */
export type AnswerGroundingState = {
  summary: EvidenceSummary;
  statements: ClassifiedStatement[];
};

const dot = "size-1.5 shrink-0 rounded-full";
const sep = <span className="text-muted-foreground/35">·</span>;

function Segment({
  count,
  label,
  tone,
  title,
}: {
  count: number;
  label: string;
  tone: string;
  title: string;
}) {
  if (count === 0) return null;
  return (
    <span className="inline-flex items-center gap-1" title={title}>
      <span aria-hidden className={cn(dot, tone)} />
      <span className="font-mono tabular-nums text-foreground/80">{count}</span>
      <span className="text-muted-foreground">{label}</span>
    </span>
  );
}

export function AnswerGrounding({ state }: { state: AnswerGroundingState }) {
  const { summary, statements } = state;

  // No classifiable claims — a refusal, or an answer with nothing to check.
  // Absence of claims is not a measurement, so render nothing at all.
  if (!hasGrounding(summary)) return null;

  const sources = groundedIn(statements);
  const groundedTitle = sources.length
    ? `Wording overlaps the cited passages from: ${sources.join(", ")}. ` +
      "Lexical overlap, not verification."
    : "Wording overlaps the cited passages. Lexical overlap, not verification.";

  const segments = [
    <Segment
      key="grounded"
      count={summary.fact_count}
      label="grounded"
      tone="bg-[var(--success)]"
      title={groundedTitle}
    />,
    <Segment
      key="hedged"
      count={summary.hypothesis_count}
      label="hedged"
      tone="bg-[var(--warning)]"
      title="Stated with uncertainty (may, likely, suggests) — the model is inferring rather than reporting."
    />,
    <Segment
      key="unsupported"
      count={summary.unknown_count}
      label="unsupported"
      tone="bg-muted-foreground/50"
      title="No cited passage shares enough wording with this statement. Treat it as unverified."
    />,
  ].filter((segment) => segment.props.count > 0);

  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11px] leading-none">
      {segments.map((segment, index) => (
        <span key={segment.key} className="inline-flex items-center gap-1.5">
          {index > 0 && sep}
          {segment}
        </span>
      ))}
    </div>
  );
}
