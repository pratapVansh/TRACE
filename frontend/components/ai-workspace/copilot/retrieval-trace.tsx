"use client";

import { cn } from "@/lib/utils";

/**
 * What the SSE stream told us about one turn.
 *
 * Every field here is read straight off events the page already receives —
 * `citations` carries the passage and document counts and arrives before the
 * first answer token, `done` carries the score. Nothing is simulated.
 */
export type RetrievalTraceState = {
  phase: "retrieving" | "composing" | "complete" | "empty" | "error" | "cancelled";
  passageCount: number;
  documentCount: number;
  /** `confidence` from the `done` event — the top passage's similarity score. */
  topScore: number | null;
  startedAt: number;
  finishedAt: number | null;
};

function elapsedLabel(state: RetrievalTraceState): string | null {
  if (state.finishedAt === null) return null;
  const seconds = (state.finishedAt - state.startedAt) / 1000;
  if (!Number.isFinite(seconds) || seconds < 0) return null;
  return `${seconds.toFixed(1)}s`;
}

const dot = "size-1.5 shrink-0 rounded-full";
const sep = <span className="text-muted-foreground/35">·</span>;

export function RetrievalTrace({ state }: { state: RetrievalTraceState }) {
  const elapsed = elapsedLabel(state);
  const counts = (
    <>
      <span className="font-mono tabular-nums text-foreground/80">
        {state.passageCount}
      </span>
      <span className="text-muted-foreground">
        {state.passageCount === 1 ? "passage" : "passages"}
      </span>
      {sep}
      <span className="font-mono tabular-nums text-foreground/80">
        {state.documentCount}
      </span>
      <span className="text-muted-foreground">
        {state.documentCount === 1 ? "document" : "documents"}
      </span>
    </>
  );

  return (
    <div className="mb-1.5 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11px] leading-none">
      {state.phase === "retrieving" && (
        <>
          <span className={cn(dot, "animate-pulse bg-[var(--accent-steel)]")} />
          <span className="text-muted-foreground">Searching corpus…</span>
        </>
      )}

      {state.phase === "composing" && (
        <>
          <span className={cn(dot, "bg-[var(--success)]")} />
          {counts}
          {sep}
          <span className="inline-flex items-center gap-1 text-muted-foreground">
            <span className={cn(dot, "animate-pulse bg-[var(--accent-steel)]")} />
            composing…
          </span>
        </>
      )}

      {state.phase === "complete" && (
        <>
          <span className={cn(dot, "bg-[var(--success)]")} />
          {counts}
          {state.topScore !== null && (
            <>
              {sep}
              <span
                className="text-muted-foreground"
                title="Similarity score of the highest-ranked retrieved passage. This is a raw retrieval score, not a calibrated confidence measure."
              >
                top score{" "}
                <span className="font-mono tabular-nums text-foreground/80">
                  {state.topScore.toFixed(2)}
                </span>
              </span>
            </>
          )}
          {elapsed && (
            <>
              {sep}
              <span className="font-mono tabular-nums text-muted-foreground">
                {elapsed}
              </span>
            </>
          )}
        </>
      )}

      {state.phase === "empty" && (
        <>
          <span className={cn(dot, "bg-[var(--warning)]")} />
          <span className="text-[var(--warning)]">
            No matching passages in the indexed corpus
          </span>
        </>
      )}

      {state.phase === "cancelled" && (
        <>
          <span className={cn(dot, "bg-muted-foreground/60")} />
          <span className="text-muted-foreground">Stopped</span>
          {state.passageCount > 0 && (
            <>
              {sep}
              {counts}
            </>
          )}
        </>
      )}

      {state.phase === "error" && (
        <>
          <span className={cn(dot, "bg-[var(--danger)]")} />
          <span className="text-[var(--danger)]">Retrieval interrupted</span>
          {state.passageCount > 0 && (
            <>
              {sep}
              {counts}
            </>
          )}
        </>
      )}
    </div>
  );
}
