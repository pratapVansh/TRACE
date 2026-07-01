"use client";

import { Bot, UserRound } from "lucide-react";

import { formatDateTime } from "@/lib/dashboard/format";
import { cn } from "@/lib/utils";
import type { CopilotMessage } from "@/types/ai-workspace";

type ConversationAreaProps = {
  messages: CopilotMessage[];
  draft?: string;
  onDraftChange?: (value: string) => void;
  onSubmit?: () => void;
};

export function ConversationArea({
  messages,
  draft = "",
  onDraftChange,
  onSubmit,
}: ConversationAreaProps) {
  return (
    <div className="industrial-card flex h-full min-h-[520px] flex-col">
      <div className="border-b border-border px-5 py-4">
        <p className="section-label">Conversation</p>
        <h3 className="mt-1 text-lg font-semibold text-white">Industrial Copilot</h3>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5">
        {messages.map((message) => {
          const isUser = message.role === "user";

          return (
            <div
              key={message.id}
              className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}
            >
              <div
                className={cn(
                  "flex size-9 shrink-0 items-center justify-center rounded-lg border",
                  isUser
                    ? "border-border bg-[var(--surface-secondary)] text-[var(--accent-steel-muted)]"
                    : "border-[var(--accent-steel)]/25 bg-[var(--accent-steel)]/10 text-[var(--accent-steel-muted)]",
                )}
              >
                {isUser ? (
                  <UserRound className="size-4" strokeWidth={1.75} />
                ) : (
                  <Bot className="size-4" strokeWidth={1.75} />
                )}
              </div>

              <div
                className={cn(
                  "max-w-[85%] space-y-2 rounded-xl border px-4 py-3",
                  isUser
                    ? "border-border bg-[var(--surface-secondary)]"
                    : "border-[var(--accent-steel)]/20 bg-[var(--surface)]",
                )}
              >
                <p className="text-sm leading-relaxed text-foreground">{message.content}</p>
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>{formatDateTime(message.timestamp)}</span>
                  {message.citationIds?.length ? (
                    <span>· {message.citationIds.length} sources cited</span>
                  ) : null}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="border-t border-border p-4">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit?.();
          }}
          className="flex flex-col gap-3 sm:flex-row"
        >
          <input
            type="text"
            value={draft}
            onChange={(event) => onDraftChange?.(event.target.value)}
            placeholder="Ask about assets, procedures, compliance, or incidents…"
            disabled
            className="h-12 flex-1 rounded-xl border border-border bg-[var(--surface-secondary)] px-4 text-sm text-muted-foreground placeholder:text-muted-foreground"
          />
          <button
            type="submit"
            disabled
            className="h-12 shrink-0 rounded-xl bg-[var(--accent-steel)]/50 px-6 text-sm font-medium text-white/60"
          >
            Send
          </button>
        </form>
        <p className="mt-2 text-xs text-muted-foreground">
          Input disabled — AI responses are preview-only in this milestone.
        </p>
      </div>
    </div>
  );
}
