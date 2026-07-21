"use client";

import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Citation } from "@/types/chat";

type SourcePreviewModalProps = {
  citation: Citation | null;
  open: boolean;
  onClose: () => void;
};

export function SourcePreviewModal({
  citation,
  open,
  onClose,
}: SourcePreviewModalProps) {
  if (!open || !citation) {
    return null;
  }

  return (
    <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--bg)]/80 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="flex max-h-[80vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-border bg-[var(--surface)] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Source preview
            </p>
            <h3 className="mt-1 truncate text-lg font-semibold text-[var(--text-primary)]">
              {citation.document_name}
            </h3>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="ml-4 size-9 shrink-0 rounded-lg"
            onClick={onClose}
            aria-label="Close preview"
          >
            <X className="size-4" />
          </Button>
        </div>

        <div className="flex flex-col gap-4 overflow-y-auto p-5">
          <div className="flex flex-wrap gap-3">
            {citation.page_number != null && (
              <span className="text-xs text-muted-foreground">
                Page {citation.page_number}
              </span>
            )}
            <span className="rounded-md border border-[var(--accent-steel)]/15 bg-[var(--accent-steel)]/5 px-2 py-0.5 text-xs text-[var(--accent-steel-muted)]">
              {Math.round(citation.similarity_score * 100)}% match
            </span>
            {citation.chunk_id && (
              <span className="text-xs text-muted-foreground">
                ID: {citation.chunk_id.slice(0, 8)}…
              </span>
            )}
          </div>

          {citation.highlighted_excerpt && (
            <div>
              <p className="mb-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Highlighted excerpt
              </p>
              <div
                className="rounded-xl border border-border bg-[var(--bg-secondary)] p-4 text-sm leading-relaxed text-[var(--text-primary)]"
                dangerouslySetInnerHTML={{
                  __html: citation.highlighted_excerpt,
                }}
              />
            </div>
          )}

          <div>
            <p className="mb-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Full chunk content
            </p>
            <p className="rounded-xl border border-border bg-[var(--surface-secondary)] p-4 text-sm leading-relaxed text-foreground break-words whitespace-pre-wrap">
              {citation.chunk_content}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
