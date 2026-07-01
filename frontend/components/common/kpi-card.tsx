import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

type KpiCardProps = {
  title: string;
  value: string;
  change?: string;
  changeType?: "neutral" | "positive" | "warning" | "negative";
  icon: LucideIcon;
  className?: string;
};

export function KpiCard({
  title,
  value,
  change,
  changeType = "neutral",
  icon: Icon,
  className,
}: KpiCardProps) {
  return (
    <article
      className={cn(
        "group rounded-xl border border-border bg-[var(--surface)] p-6 shadow-[0_4px_24px_rgba(0,0,0,0.18)] transition-all duration-200 hover:border-[var(--accent-steel)]/20 hover:shadow-[0_8px_32px_rgba(0,0,0,0.22)]",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-4">
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <p className="text-3xl font-semibold tracking-tight text-white">
            {value}
          </p>
          {change ? (
            <p
              className={cn(
                "text-xs font-medium",
                changeType === "positive" && "text-[var(--success)]",
                changeType === "warning" && "text-[var(--warning)]",
                changeType === "negative" && "text-[var(--danger)]",
                changeType === "neutral" && "text-muted-foreground",
              )}
            >
              {change}
            </p>
          ) : null}
        </div>
        <div className="flex size-11 shrink-0 items-center justify-center rounded-xl border border-border bg-[var(--surface-secondary)] text-[var(--accent-steel-muted)] transition-colors duration-200 group-hover:border-[var(--accent-steel)]/25 group-hover:text-[var(--accent-steel-muted)]">
          <Icon className="size-5" strokeWidth={1.75} />
        </div>
      </div>
    </article>
  );
}

export function KpiCardSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-[var(--surface)] p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-4">
          <div className="h-4 w-24 animate-pulse rounded-md bg-[var(--surface-secondary)]" />
          <div className="h-9 w-28 animate-pulse rounded-md bg-[var(--surface-secondary)]" />
          <div className="h-3 w-32 animate-pulse rounded-md bg-[var(--surface-secondary)]" />
        </div>
        <div className="size-11 animate-pulse rounded-xl bg-[var(--surface-secondary)]" />
      </div>
    </div>
  );
}
