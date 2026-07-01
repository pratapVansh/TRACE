import { FileText } from "lucide-react";

import { DocumentStatusBadge } from "@/components/knowledge/document-status-badge";
import { formatRelativeTime } from "@/lib/dashboard/format";
import type { KnowledgeDocument } from "@/types/knowledge";

type SearchRecentDocumentsProps = {
  documents: KnowledgeDocument[];
};

export function SearchRecentDocuments({ documents }: SearchRecentDocumentsProps) {
  return (
    <div className="industrial-card p-5 sm:p-6">
      <p className="section-label">Knowledge base</p>
      <h3 className="mt-2 text-lg font-semibold text-white">Recent documents</h3>
      <p className="mt-2 text-sm text-muted-foreground">
        Recently indexed and updated technical records.
      </p>

      <ul className="mt-5 space-y-3">
        {documents.map((doc) => (
          <li
            key={doc.id}
            className="flex gap-4 rounded-xl border border-border bg-[var(--surface-secondary)] p-4 transition-industrial hover:border-[var(--accent-steel)]/20"
          >
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-border bg-[var(--surface)] text-[var(--accent-steel-muted)]">
              <FileText className="size-4.5" strokeWidth={1.75} />
            </div>
            <div className="min-w-0 flex-1 space-y-2">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="text-sm font-medium text-white">{doc.title}</p>
                <DocumentStatusBadge status={doc.status} />
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <span>{doc.type}</span>
                <span>{doc.department}</span>
                <span>{doc.version}</span>
                <span>{formatRelativeTime(doc.lastUpdated)}</span>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
