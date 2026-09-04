import { FileText } from "lucide-react";

import { DocumentStatusBadge } from "@/components/knowledge/document-status-badge";
import { WidgetCard } from "@/components/dashboard/widget-card";
import { WidgetHeader } from "@/components/dashboard/widget-header";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRelativeTime } from "@/lib/dashboard/format";
import type { KnowledgeDocument } from "@/types/knowledge";

type RecentDocumentsWidgetProps = {
  documents: KnowledgeDocument[];
  isLoading?: boolean;
};

export function RecentDocumentsWidget({
  documents,
  isLoading = false,
}: RecentDocumentsWidgetProps) {
  return (
    <WidgetCard>
      <WidgetHeader
        sectionLabel="Document Intelligence"
        title="Recent Documents"
        description="Latest technical records ingested across production units."
      />

      {isLoading ? (
        <ul className="flex flex-1 flex-col gap-3">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-20 w-full rounded-md" />
          ))}
        </ul>
      ) : documents.length === 0 ? (
        <p className="text-[12px] text-muted-foreground">
          No documents uploaded yet. Upload documents to see them here.
        </p>
      ) : (
        <ul className="flex flex-1 flex-col gap-3">
          {documents.map((doc) => (
            <li
              key={doc.id}
              className="flex gap-4 rounded-md border border-border bg-[var(--surface-secondary)] p-4 transition-industrial hover:border-[var(--accent-steel)]/20"
            >
              <div className="flex size-7 shrink-0 items-center justify-center rounded-lg border border-border bg-[var(--surface)] text-[var(--accent-steel-muted)]">
                <FileText className="size-4.5" strokeWidth={1.75} />
              </div>
              <div className="min-w-0 flex-1 space-y-2">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="text-[12px] font-medium text-foreground">{doc.title}</p>
                  <DocumentStatusBadge status={doc.status} />
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span>{doc.type}</span>
                  <span>{doc.department}</span>
                  <span>{formatRelativeTime(doc.lastUpdated)}</span>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </WidgetCard>
  );
}
