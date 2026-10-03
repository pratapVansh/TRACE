"use client";

import { useEffect, useRef } from "react";
import { ChevronRight, ExternalLink, FileText, X } from "lucide-react";

import type { Citation } from "@/types/chat";
import { cn } from "@/lib/utils";

type SourcesPanelProps = {
  /** Citations for the turn currently in view. */
  citations: Citation[];
  /** Index into `citations` that is expanded, or null. */
  expandedIndex: number | null;
  onToggle: (index: number | null) => void;
  /**
   * A citation opened from an earlier turn, which is therefore not in
   * `citations`. Pinned above the list so the click still shows the passage.
   */
  pinned: Citation | null;
  onClearPinned: () => void;
  /**
   * Open the source document a citation came from. Given the citation's
   * `document_id`, not its retrieved text — the passage below is what the
   * model was shown, and checking it against itself proves nothing.
   */
  onOpenDocument?: (documentId: string) => void;
};

/** The "open the source" control, shown only when the passage can be traced. */
function OpenSourceButton({
  citation,
  onOpenDocument,
}: {
  citation: Citation;
  onOpenDocument?: (documentId: string) => void;
}) {
  const documentId = citation.document_id;
  if (!documentId || !onOpenDocument) return null;

  return (
    <button
      type="button"
      onClick={() => onOpenDocument(documentId)}
      className="mt-1.5 inline-flex items-center gap-1 rounded border border-border px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground transition-industrial hover:border-[var(--accent-steel)]/40 hover:text-foreground"
    >
      <ExternalLink className="size-2.5" strokeWidth={2} />
      Open document
    </button>
  );
}

function scorePercent(citation: Citation): number {
  return Math.round(citation.similarity_score * 100);
}

function CitationBody({
  citation,
  onOpenDocument,
}: {
  citation: Citation;
  onOpenDocument?: (documentId: string) => void;
}) {
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
      <OpenSourceButton citation={citation} onOpenDocument={onOpenDocument} />
    </div>
  );
}

function CitationRow({
  citation,
  index,
  expanded,
  onToggle,
  onOpenDocument,
}: {
  citation: Citation;
  index: number;
  expanded: boolean;
  onToggle: () => void;
  onOpenDocument?: (documentId: string) => void;
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
          Match {scorePercent(citation)}%
        </span>
      </button>

      {expanded ? (
        <div className="px-2 pb-2">
          <CitationBody citation={citation} onOpenDocument={onOpenDocument} />
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
  expandedIndex,
  onToggle,
  pinned,
  onClearPinned,
  onOpenDocument,
}: SourcesPanelProps) {
  const hasCitations = citations.length > 0;
  const documentCount = new Set(citations.map((citation) => citation.document_name)).size;

  return (
    <div className="industrial-card flex min-h-0 flex-col overflow-hidden">
      <div className="flex h-8 shrink-0 items-center justify-between border-b border-border px-2.5">
        <span className="section-label">Evidence</span>
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground/70">
          {hasCitations
            ? `${citations.length} passage${citations.length === 1 ? "" : "s"} · ${documentCount} document${documentCount === 1 ? "" : "s"}`
            : "—"}
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
                Earlier answer
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
            <CitationBody citation={pinned} onOpenDocument={onOpenDocument} />
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
                onOpenDocument={onOpenDocument}
              />
            ))}
          </ul>
        ) : (
          !pinned && (
            <p className="px-0.5 py-1 text-[11px] leading-snug text-muted-foreground">
              Supporting passages will appear here when Copilot finds relevant
              information in your documents.
            </p>
          )
        )}
      </div>

    </div>
  );
}
