import { FileText } from "lucide-react";

import type { Citation } from "@/types/chat";

type SourcePanelProps = {
  citations: Citation[];
};

export function SourcePanel({ citations }: SourcePanelProps) {
  if (citations.length === 0) {
    return (
      <div className="industrial-card flex h-full flex-col p-5">
        <p className="section-label">Citations</p>
        <h3 className="mt-1 text-base font-semibold text-white">
          Cited sources
        </h3>
        <div className="mt-6 flex flex-1 items-center justify-center">
          <p className="text-center text-xs text-muted-foreground">
            Citations will appear here after the AI responds.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="industrial-card flex h-full flex-col p-5">
      <p className="section-label">Citations</p>
      <h3 className="mt-1 text-base font-semibold text-white">
        Cited sources
      </h3>
      <p className="mt-2 text-xs text-muted-foreground">
        Grounded excerpts from indexed technical records.
      </p>

      <ul className="mt-4 flex-1 space-y-3 overflow-y-auto">
        {citations.map((citation, i) => (
          <li
            key={i}
            className="rounded-xl border border-border bg-[var(--surface-secondary)] p-3 sm:p-4"
          >
            <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
              <div className="flex min-w-0 items-center gap-2">
                <FileText
                  className="size-3.5 shrink-0 text-[var(--accent-steel-muted)]"
                  strokeWidth={1.75}
                />
                <p className="truncate text-xs font-medium text-white">
                  {citation.document_name}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {citation.page_number != null && (
                  <span className="whitespace-nowrap text-[11px] text-[var(--accent-steel-muted)]">
                    p.{citation.page_number}
                  </span>
                )}
                <span className="whitespace-nowrap rounded-md border border-[var(--accent-steel)]/15 bg-[var(--accent-steel)]/5 px-1.5 py-0.5 text-[11px] text-[var(--accent-steel-muted)]">
                  {Math.round(citation.score * 100)}% match
                </span>
              </div>
            </div>
            <p className="break-words text-xs leading-relaxed text-muted-foreground">
              {citation.chunk_content}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
