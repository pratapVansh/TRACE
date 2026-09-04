import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

type StatCardProps = {
  label: string;
  value: string;
  hint?: string;
  icon: LucideIcon;
  tone?: "default" | "success" | "warning" | "danger";
  className?: string;
};

const TONE_STYLES = {
  default: "text-[var(--accent-steel-muted)]",
  success: "text-[var(--success)]",
  warning: "text-[var(--warning)]",
  danger: "text-[var(--danger)]",
};

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "default",
  className,
}: StatCardProps) {
  return (
    <article
      className={cn(
        "industrial-card flex items-start justify-between gap-4 p-5 sm:p-6",
        className,
      )}
    >
      <div className="space-y-2">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        <p className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
          {value}
        </p>
        {hint ? <p className={cn("text-xs font-medium", TONE_STYLES[tone])}>{hint}</p> : null}
      </div>
      <div className="flex size-11 shrink-0 items-center justify-center rounded-xl border border-border bg-[var(--surface-secondary)] text-[var(--accent-steel-muted)]">
        <Icon className="size-5" strokeWidth={1.75} />
      </div>
    </article>
  );
}
