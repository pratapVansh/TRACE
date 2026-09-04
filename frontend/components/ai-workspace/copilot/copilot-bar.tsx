"use client";

import { Check, PanelLeft, PanelRight, Plus, Trash2, X } from "lucide-react";

import { cn } from "@/lib/utils";

type CopilotBarProps = {
  title: string | null;
  turnCount: number;
  sourceCount: number;
  hasConversation: boolean;
  deleteConfirmOpen: boolean;
  onNewConversation: () => void;
  onDeleteRequest: () => void;
  onDeleteCancel: () => void;
  onDeleteAll: () => void;
  onOpenRail: () => void;
  onOpenSources: () => void;
};

const barButton =
  "inline-flex h-7 items-center gap-1.5 rounded-md border border-border bg-[var(--surface-secondary)] px-2 text-[11px] font-medium text-muted-foreground transition-industrial hover:border-[var(--accent-steel)]/30 hover:text-foreground";

export function CopilotBar({
  title,
  turnCount,
  sourceCount,
  hasConversation,
  deleteConfirmOpen,
  onNewConversation,
  onDeleteRequest,
  onDeleteCancel,
  onDeleteAll,
  onOpenRail,
  onOpenSources,
}: CopilotBarProps) {
  return (
    <header className="flex h-9 shrink-0 items-center gap-2 border-b border-border px-1">
      <button
        type="button"
        onClick={onOpenRail}
        className={cn(barButton, "xl:hidden")}
        aria-label="Open conversations"
      >
        <PanelLeft className="size-3.5" strokeWidth={1.75} />
      </button>

      <div className="flex min-w-0 items-baseline gap-2">
        <h1 className="truncate text-[13px] font-medium text-foreground">
          {title?.trim() || (hasConversation ? "Untitled inquiry" : "New inquiry")}
        </h1>
        <span className="shrink-0 font-mono text-[10px] text-muted-foreground/70 tabular-nums">
          {turnCount > 0 ? `${turnCount} turn${turnCount === 1 ? "" : "s"}` : "no turns"}
          {sourceCount > 0 ? ` · ${sourceCount} src` : ""}
        </span>
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-1.5">
        {deleteConfirmOpen ? (
          <div className="flex items-center gap-1.5 rounded-md border border-[var(--danger)]/30 bg-[var(--danger)]/10 px-2 py-1">
            <span className="text-[11px] text-[var(--danger)]">
              Delete all conversations?
            </span>
            <button
              type="button"
              onClick={onDeleteAll}
              className="flex size-4 items-center justify-center rounded text-[var(--danger)] transition-industrial hover:text-red-300"
              aria-label="Confirm delete all conversations"
            >
              <Check className="size-3" strokeWidth={2.25} />
            </button>
            <button
              type="button"
              onClick={onDeleteCancel}
              className="flex size-4 items-center justify-center rounded text-muted-foreground transition-industrial hover:text-foreground"
              aria-label="Cancel delete"
            >
              <X className="size-3" strokeWidth={2} />
            </button>
          </div>
        ) : (
          <>
            <button type="button" onClick={onNewConversation} className={barButton}>
              <Plus className="size-3.5" strokeWidth={1.75} />
              New
            </button>
            {hasConversation && (
              <button
                type="button"
                onClick={onDeleteRequest}
                className={cn(
                  barButton,
                  "hover:border-[var(--danger)]/30 hover:text-[var(--danger)]",
                )}
              >
                <Trash2 className="size-3.5" strokeWidth={1.75} />
                Clear
              </button>
            )}
          </>
        )}

        <button
          type="button"
          onClick={onOpenSources}
          className={cn(barButton, "lg:hidden")}
          aria-label="Open sources"
        >
          <PanelRight className="size-3.5" strokeWidth={1.75} />
        </button>
      </div>
    </header>
  );
}
