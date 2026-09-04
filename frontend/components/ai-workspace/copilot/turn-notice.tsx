"use client";

import { AlertTriangle, RotateCw, SearchX, Square } from "lucide-react";

import { cn } from "@/lib/utils";

export type TurnNoticeKind = "error" | "cancelled" | "empty";

export type TurnNoticeState = {
  kind: TurnNoticeKind;
  text: string;
};

const STYLES: Record<
  TurnNoticeKind,
  { wrap: string; accent: string; label: string; Icon: typeof AlertTriangle }
> = {
  error: {
    wrap: "border-[var(--danger)]/30 bg-[var(--danger)]/8",
    accent: "text-[var(--danger)]",
    label: "Request failed",
    Icon: AlertTriangle,
  },
  cancelled: {
    wrap: "border-border bg-[var(--surface-secondary)]",
    accent: "text-muted-foreground",
    label: "Stopped",
    Icon: Square,
  },
  empty: {
    wrap: "border-[var(--warning)]/30 bg-[var(--warning)]/8",
    accent: "text-[var(--warning)]",
    label: "No matching passages",
    Icon: SearchX,
  },
};

export function TurnNotice({
  notice,
  onRetry,
  className,
}: {
  notice: TurnNoticeState;
  onRetry?: () => void;
  className?: string;
}) {
  const style = STYLES[notice.kind];
  const { Icon } = style;

  return (
    <div className={cn("rounded border px-2.5 py-2", style.wrap, className)}>
      <div className="flex items-start gap-1.5">
        <Icon
          className={cn("mt-[1px] size-3.5 shrink-0", style.accent)}
          strokeWidth={2}
        />
        <div className="min-w-0 flex-1">
          <p
            className={cn(
              "text-[11px] font-semibold tracking-wide uppercase",
              style.accent,
            )}
          >
            {style.label}
          </p>
          <p className="mt-0.5 text-[12px] leading-[1.5] text-foreground/85">
            {notice.text}
          </p>
        </div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className={cn(
              "inline-flex shrink-0 items-center gap-1 rounded border border-border bg-[var(--surface-secondary)] px-1.5 py-0.5 text-[11px] font-medium transition-industrial hover:text-foreground",
              style.accent,
            )}
          >
            <RotateCw className="size-3" strokeWidth={2} />
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
