import { FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { ReferencedDocument } from "@/types/ai-workspace";

type ReferencedDocumentsProps = {
  documents: ReferencedDocument[];
  activeId?: string;
  onSelect?: (id: string) => void;
};

export function ReferencedDocuments({
  documents,
  activeId,
  onSelect,
}: ReferencedDocumentsProps) {
  return (
    <div className="industrial-card p-5">
      <p className="section-label">Context</p>
      <h3 className="mt-1 text-base font-semibold text-white">Referenced documents</h3>

      <ul className="mt-4 space-y-2">
        {documents.map((doc) => (
          <li key={doc.id}>
            <button
              type="button"
              onClick={() => onSelect?.(doc.id)}
              className={`flex w-full items-start gap-3 rounded-xl border p-3 text-left transition-industrial ${
                activeId === doc.id
                  ? "border-[var(--accent-steel)]/30 bg-[var(--accent-steel)]/5"
                  : "border-border bg-[var(--surface-secondary)] hover:border-[var(--accent-steel)]/20"
              }`}
            >
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-border bg-[var(--surface)] text-[var(--accent-steel-muted)]">
                <FileText className="size-3.5" strokeWidth={1.75} />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <p className="text-xs font-medium text-white">{doc.title}</p>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[11px] text-muted-foreground">{doc.type}</span>
                  {doc.page ? (
                    <span className="text-[11px] text-muted-foreground">{doc.page}</span>
                  ) : null}
                  <Badge variant="secondary">{doc.relevance}% match</Badge>
                </div>
              </div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
