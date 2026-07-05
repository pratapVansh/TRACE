import { Badge } from "@/components/ui/badge";
import { DOCUMENT_STATUS_LABELS } from "@/lib/knowledge/constants";
import type { DocumentStatus } from "@/types/knowledge";

const STATUS_VARIANT: Record<
  DocumentStatus,
  "success" | "warning" | "secondary" | "default"
> = {
  queued: "secondary",
  indexed: "success",
  processing: "default",
  review: "warning",
  archived: "secondary",
  failed: "default",
};

type DocumentStatusBadgeProps = {
  status: DocumentStatus;
};

export function DocumentStatusBadge({ status }: DocumentStatusBadgeProps) {
  return (
    <Badge
      variant={STATUS_VARIANT[status]}
      className={status === "failed" ? "border-[var(--danger)]/25 bg-[var(--danger)]/10 text-[var(--danger)]" : undefined}
    >
      {DOCUMENT_STATUS_LABELS[status]}
    </Badge>
  );
}
