"use client";

import { useEffect, useRef } from "react";
import { ChevronRight, FileText, X } from "lucide-react";

import type { Citation } from "@/types/chat";
import { cn } from "@/lib/utils";

type SourcesPanelProps = {
  /** Citations for the turn currently in view. */
  citations: Citation[];
  /** Distinct document names cited across the conversation. */
  sources: string[];
  /** Index into `citations` that is expanded, or null. */
  expandedIndex: number | null;
  onToggle: (index: number | null) => void;
  /**
   * A citation opened from an earlier turn, which is therefore not in
   * `citations`. Pinned above the list so the click still shows the passage.
   */
  pinned: Citation | null;
  onClearPinned: () => void;
};

function scorePercent(citation: Citation): number {
  return Math.round(citation.similarity_score * 100);
}

function CitationBody({ citation }: { citation: Citation }) {
  return (
    <div className="mt-1.5 border-t border-border pt-1.5">
      {citation.highlighted_excerpt && (
        <div
          className="mb-1.5 break-words text-[11px] leading-[1.5] text-foreground/85 [&>mark]:rounded-sm [&>mark]:bg-[var(--accent-steel)]/30 [&>mark]:px-0.5 [&>mark]:text-foreground"
          dangerouslySetInnerHTML={{ __html: citation.highlighted_excerpt }}
        />
      )}
      <p className="max-h-56 overflow-y-auto break-words whitespace-pre-wrap text-[11px] leading-[1.5] text-muted-foreground">
        {citation.chunk_content}
      </p>
      {citation.chunk_id && (
        <p className="mt-1 font-mono text-[9px] text-muted-foreground/50">
          chunk {citation.chunk_id.slice(0, 12)}
        </p>
      )}
    </div>
  );
}

function CitationRow({
  citation,
  index,
  expanded,
  onToggle,
}: {
  citation: Citation;
  index: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const ref = useRef<HTMLLIElement>(null);

  // Opening a source from the answer text scrolls it into view here, so the
  // claim and its evidence stay on screen together.
  useEffect(() => {
    if (expanded) {
      ref.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [expanded]);

  return (
    <li
      ref={ref}
      className={cn(
        "rounded border transition-industrial",
        expanded
          ? "border-[var(--accent-steel)]/50 bg-[var(--surface-secondary)]"
          : "border-border bg-[var(--surface-secondary)] hover:border-[var(--accent-steel)]/35",
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full items-center gap-1.5 px-2 py-1.5 text-left"
      >
        <ChevronRight
          className={cn(
            "size-3 shrink-0 text-muted-foreground transition-transform",
            expanded && "rotate-90 text-[var(--accent-steel)]",
          )}
          strokeWidth={2}
        />
        <span className="shrink-0 font-mono text-[10px] text-[var(--accent-steel)]">
          {index + 1}
        </span>
        <span className="min-w-0 flex-1 truncate text-[11px] font-medium text-foreground">
          {citation.document_name}
        </span>
        {citation.page_number != null && (
          <span className="shrink-0 font-mono text-[10px] whitespace-nowrap text-muted-foreground">
            p.{citation.page_number}
          </span>
        )}
        <span className="shrink-0 font-mono text-[10px] tabular-nums whitespace-nowrap text-[var(--accent-steel-muted)]">
          {scorePercent(citation)}%
        </span>
      </button>

      {expanded ? (
        <div className="px-2 pb-2">
          <CitationBody citation={citation} />
        </div>
      ) : (
        <p className="line-clamp-2 px-2 pb-1.5 pl-[38px] text-[11px] leading-[1.45] text-muted-foreground">
          {citation.chunk_content}
        </p>
      )}
    </li>
  );
}

export function SourcesPanel({
  citations,
  sources,
  expandedIndex,
  onToggle,
  pinned,
  onClearPinned,
}: SourcesPanelProps) {
  const hasCitations = citations.length > 0;

  return (
    <div className="industrial-card flex min-h-0 flex-col overflow-hidden">
      <div className="flex h-8 shrink-0 items-center justify-between border-b border-border px-2.5">
        <span className="section-label">Sources</span>
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground/70">
          {hasCitations ? `${citations.length} passages` : "—"}
        </span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {pinned && (
          <div className="mb-2 rounded border border-[var(--accent-steel)]/50 bg-[var(--surface-secondary)] p-2">
            <div className="flex items-center gap-1.5">
              <FileText
                className="size-3 shrink-0 text-[var(--accent-steel)]"
                strokeWidth={1.75}
              />
              <span className="min-w-0 flex-1 truncate text-[11px] font-medium text-foreground">
                {pinned.document_name}
              </span>
              <span className="shrink-0 font-mono text-[9px] tracking-wide text-muted-foreground uppercase">
                earlier turn
              </span>
              <button
                type="button"
                onClick={onClearPinned}
                className="shrink-0 text-muted-foreground transition-industrial hover:text-foreground"
                aria-label="Close pinned source"
              >
                <X className="size-3" strokeWidth={2} />
              </button>
            </div>
            <CitationBody citation={pinned} />
          </div>
        )}

        {hasCitations ? (
          <ul className="flex flex-col gap-1">
            {citations.map((citation, index) => (
              <CitationRow
                key={citation.chunk_id || index}
                citation={citation}
                index={index}
                expanded={expandedIndex === index}
                onToggle={() => onToggle(expandedIndex === index ? null : index)}
              />
            ))}
          </ul>
        ) : (
          !pinned && (
            <p className="px-0.5 py-1 text-[11px] leading-snug text-muted-foreground">
              Retrieved passages appear here the moment the search returns —
              before the answer is written.
            </p>
          )
        )}
      </div>

      {sources.length > 0 && (
        <div className="shrink-0 border-t border-border px-2.5 py-1.5">
          <div className="mb-1 flex items-baseline justify-between">
            <span className="section-label">Documents drawn on</span>
            <span className="font-mono text-[10px] tabular-nums text-muted-foreground/70">
              {sources.length}
            </span>
          </div>
          <ul className="flex max-h-24 flex-col gap-0.5 overflow-y-auto">
            {sources.map((source) => (
              <li key={source} className="flex items-center gap-1.5">
                <FileText
                  className="size-3 shrink-0 text-[var(--accent-steel-muted)]"
                  strokeWidth={1.75}
                />
                <span className="min-w-0 flex-1 truncate text-[11px] text-foreground/85">
                  {source}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
