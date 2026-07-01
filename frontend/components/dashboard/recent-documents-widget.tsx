import { FileText } from "lucide-react";

import { WidgetCard } from "@/components/dashboard/widget-card";
import { WidgetHeader } from "@/components/dashboard/widget-header";
import { Badge } from "@/components/ui/badge";
import { formatRelativeTime } from "@/lib/dashboard/format";
import type { RecentDocument } from "@/types/dashboard";

const STATUS_VARIANT = {
  indexed: "success",
  review: "warning",
  processing: "secondary",
} as const;

const STATUS_LABEL = {
  indexed: "Indexed",
  review: "In review",
  processing: "Processing",
} as const;

type RecentDocumentsWidgetProps = {
  documents: RecentDocument[];
};

export function RecentDocumentsWidget({ documents }: RecentDocumentsWidgetProps) {
  return (
    <WidgetCard>
      <WidgetHeader
        sectionLabel="Document Intelligence"
        title="Recent Documents"
        description="Latest technical records ingested across production units."
      />

      <ul className="flex flex-1 flex-col gap-3">
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
                <Badge variant={STATUS_VARIANT[doc.status]}>
                  {STATUS_LABEL[doc.status]}
                </Badge>
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <span>{doc.type}</span>
                <span>{doc.unit}</span>
                <span>{formatRelativeTime(doc.updatedAt)}</span>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </WidgetCard>
  );
}
