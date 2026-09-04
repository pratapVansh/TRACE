"use client";

import { ArrowUpRight, FileClock } from "lucide-react";

export type Suggestion = {
  id: string;
  text: string;
  source: "history" | "curated";
};

/**
 * Used only when this account has no conversation history to draw on.
 * Written against the kinds of records TRACE actually indexes — maintenance
 * logs, inspection reports, SOPs, OEM manuals — not generic assistant copy.
 */
export const CURATED_SUGGESTIONS: Suggestion[] = [
  {
    id: "curated-seal-failures",
    text: "Which pumps have recorded seal failures, and what causes were identified?",
    source: "curated",
  },
  {
    id: "curated-loto",
    text: "What are the lockout/tagout steps for the compressor train?",
    source: "curated",
  },
  {
    id: "curated-inspection-interval",
    text: "What inspection intervals are specified for pressure vessels?",
    source: "curated",
  },
  {
    id: "curated-corrective-actions",
    text: "List the corrective actions raised in the most recent inspection reports.",
    source: "curated",
  },
];

type ThreadEmptyStateProps = {
  variant: "default" | "not_found";
  suggestions: Suggestion[];
  onSelect: (prompt: string) => void;
};

export function ThreadEmptyState({
  variant,
  suggestions,
  onSelect,
}: ThreadEmptyStateProps) {
  const fromHistory = suggestions.length > 0 && suggestions[0].source === "history";

  return (
    <div className="mx-auto max-w-2xl px-1 pt-6">
      {variant === "not_found" ? (
        <div className="mb-5 flex items-start gap-2 rounded border border-border bg-[var(--surface-secondary)] px-2.5 py-2">
          <FileClock
            className="mt-[1px] size-3.5 shrink-0 text-muted-foreground"
            strokeWidth={1.75}
          />
          <div>
            <p className="text-[11px] font-semibold tracking-wide text-foreground uppercase">
              Conversation not found
            </p>
            <p className="mt-0.5 text-[12px] leading-[1.5] text-muted-foreground">
              It was deleted or is no longer available. Anything you ask below
              starts a new one.
            </p>
          </div>
        </div>
      ) : null}

      <p className="section-label">Ask the corpus</p>
      <p className="mt-1.5 max-w-xl text-[12px] leading-[1.6] text-muted-foreground">
        Answers are drawn only from indexed technical records — maintenance logs,
        inspection reports, SOPs and OEM manuals. Retrieved passages appear in
        the sources panel before the answer is written, and every claim traces
        back to the passage it came from.
      </p>

      {suggestions.length > 0 && (
        <>
          <p className="section-label mt-6">
            {fromHistory ? "Continue a line of enquiry" : "Starting points"}
          </p>
          <ul className="mt-1.5 flex flex-col">
            {suggestions.map((suggestion) => (
              <li key={suggestion.id}>
                <button
                  type="button"
                  onClick={() => onSelect(suggestion.text)}
                  className="group flex w-full items-start gap-2 rounded border border-transparent px-1.5 py-1.5 text-left transition-industrial hover:border-border hover:bg-[var(--surface-secondary)]"
                >
                  <ArrowUpRight
                    className="mt-[2px] size-3 shrink-0 text-muted-foreground/50 transition-industrial group-hover:text-[var(--accent-steel)]"
                    strokeWidth={2}
                  />
                  <span className="min-w-0 flex-1 text-[12px] leading-[1.5] text-muted-foreground transition-industrial group-hover:text-foreground">
                    {suggestion.text}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {fromHistory && (
            <p className="mt-2 px-1.5 text-[10px] text-muted-foreground/60">
              Drawn from your recent conversations.
            </p>
          )}
        </>
      )}
    </div>
  );
}
