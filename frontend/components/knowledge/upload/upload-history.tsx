import { DocumentStatusBadge } from "@/components/knowledge/document-status-badge";
import { formatDateTime } from "@/lib/dashboard/format";
import { Badge } from "@/components/ui/badge";
import type { UploadHistoryItem } from "@/types/knowledge";

type UploadHistoryProps = {
  items: UploadHistoryItem[];
};

export function UploadHistory({ items }: UploadHistoryProps) {
  return (
    <div className="industrial-card p-5 sm:p-6">
      <p className="section-label">Archive</p>
      <h3 className="mt-2 text-lg font-semibold text-white">Upload history</h3>
      <p className="mt-2 text-sm text-muted-foreground">
        Recent uploads and their current ingestion status.
      </p>

      <ul className="mt-5 space-y-3">
        {items.map((item) => (
          <li
            key={item.id}
            className="flex flex-col gap-3 rounded-xl border border-border bg-[var(--surface-secondary)] p-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0 space-y-1">
              <p className="truncate text-sm font-medium text-white">
                {item.fileName}
              </p>
              <p className="text-xs text-muted-foreground">
                {item.uploadedBy} · {formatDateTime(item.uploadedAt)}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">.{item.fileType}</Badge>
              <DocumentStatusBadge status={item.status} />
              <span className="text-xs text-muted-foreground">
                {item.documentsCreated} doc{item.documentsCreated === 1 ? "" : "s"}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
