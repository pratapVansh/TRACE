import { CheckCircle2, Loader2, RefreshCw, Trash2, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { UploadQueueItem } from "@/types/knowledge";

type UploadQueueProps = {
  items: UploadQueueItem[];
  onRetry?: (item: UploadQueueItem) => void;
  onRemove?: (id: string) => void;
};

const STATUS_LABEL = {
  queued: "Queued",
  uploading: "Uploading",
  processing: "Indexing…",
  complete: "Complete",
  failed: "Failed",
} as const;

export function UploadQueue({ items, onRetry, onRemove }: UploadQueueProps) {
  const activeCount = items.filter(
    (item) => item.status === "queued" || item.status === "uploading",
  ).length;

  return (
    <div className="industrial-card p-5 sm:p-6">
      <div className="mb-5 flex items-center justify-between gap-3">
        <div>
          <p className="section-label">Ingestion pipeline</p>
          <h3 className="mt-2 text-lg font-semibold text-white">Upload queue</h3>
        </div>
        <Badge variant="secondary">{activeCount} active</Badge>
      </div>

      {items.length === 0 ? (
        <p className="rounded-xl border border-border bg-[var(--surface-secondary)] p-6 text-center text-sm text-muted-foreground">
          No files in queue. Drop files above to begin ingestion.
        </p>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <li
              key={item.id}
              className="rounded-xl border border-border bg-[var(--surface-secondary)] p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 space-y-1">
                  <p className="truncate text-sm font-medium text-white">
                    {item.fileName}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {item.fileType.toUpperCase()} · {item.fileSize}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {item.status === "failed" && onRetry ? (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7 rounded-lg text-muted-foreground hover:text-white"
                      onClick={() => onRetry(item)}
                      aria-label={`Retry ${item.fileName}`}
                    >
                      <RefreshCw className="size-3.5" />
                    </Button>
                  ) : null}
                  {(item.status === "queued" || item.status === "failed") && onRemove ? (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7 rounded-lg text-muted-foreground hover:text-[var(--danger)]"
                      onClick={() => onRemove(item.id)}
                      aria-label={`Remove ${item.fileName}`}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  ) : null}
                  <Badge
                    variant={
                      item.status === "complete"
                        ? "success"
                        : item.status === "failed"
                          ? "warning"
                          : "secondary"
                    }
                  className={cn(
                    item.status === "failed" &&
                      "border-[var(--danger)]/25 bg-[var(--danger)]/10 text-[var(--danger)]",
                  )}
                >
                  {STATUS_LABEL[item.status]}
                </Badge>
              </div>
            </div>

              {item.status !== "failed" && item.status !== "complete" && item.status !== "processing" ? (
                <div className="mt-4 space-y-2">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="flex items-center gap-1.5">
                      <Loader2 className="size-3 animate-spin" />
                      {item.message ?? "Uploading…"}
                    </span>
                    <span>{item.progress}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-[var(--surface)]">
                    <div
                      className="h-full rounded-full bg-[var(--accent-steel)] transition-all duration-300"
                      style={{ width: `${item.progress}%` }}
                    />
                  </div>
                </div>
              ) : null}

              {item.status === "complete" ? (
                <p className="mt-3 flex items-center gap-1.5 text-xs text-[var(--success)]">
                  <CheckCircle2 className="size-3.5" />
                  {item.message ?? "Upload complete"}
                </p>
              ) : null}

              {item.status === "failed" ? (
                <p className="mt-3 flex items-center gap-1.5 text-xs text-[var(--danger)]">
                  <XCircle className="size-3.5" />
                  {item.message ?? "Upload failed"}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
