import { FileText } from "lucide-react";

type ReferencedDocumentsProps = {
  sources: string[];
};

export function ReferencedDocuments({ sources }: ReferencedDocumentsProps) {
  if (sources.length === 0) {
    return (
      <div className="industrial-card p-5">
        <p className="section-label">Context</p>
        <h3 className="mt-1 text-base font-semibold text-white">
          Referenced documents
        </h3>
        <div className="mt-6 flex items-center justify-center">
          <p className="text-center text-xs text-muted-foreground">
            Documents referenced by the AI will appear here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="industrial-card p-5">
      <p className="section-label">Context</p>
      <h3 className="mt-1 text-base font-semibold text-white">
        Referenced documents
      </h3>
      <p className="mt-1 text-xs text-muted-foreground">
        {sources.length} source{sources.length !== 1 ? "s" : ""} cited in this
        conversation.
      </p>

      <ul className="mt-4 space-y-2">
        {sources.map((source, i) => (
          <li key={i}>
            <div className="flex items-start gap-3 rounded-xl border border-border bg-[var(--surface-secondary)] p-3">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-border bg-[var(--surface)] text-[var(--accent-steel-muted)]">
                <FileText className="size-3.5" strokeWidth={1.75} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-white">{source}</p>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
