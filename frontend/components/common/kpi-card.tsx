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
        "group rounded-md border border-border bg-[var(--surface)] p-2.5 transition-industrial hover:border-[var(--accent-steel)]/35",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="section-label truncate">{title}</p>
          <p className="mt-1 font-mono text-[20px] leading-none font-medium tracking-tight text-foreground tabular-nums">
            {value}
          </p>
          {change ? (
            <p
              className={cn(
                "mt-1 text-[11px] font-medium",
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
        <div className="flex size-6 shrink-0 items-center justify-center rounded border border-border bg-[var(--surface-secondary)] text-[var(--accent-steel-muted)] transition-industrial group-hover:border-[var(--accent-steel)]/35">
          <Icon className="size-3.5" strokeWidth={1.75} />
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
