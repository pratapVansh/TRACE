"use client";

import { useEffect, useRef } from "react";
import { AlertTriangle, SendHorizonal, X } from "lucide-react";

import type { AnswerGroundingState } from "@/components/ai-workspace/copilot/answer-grounding";
import { ChatMessage } from "@/components/ai-workspace/copilot/chat-message";
import type { RetrievalTraceState } from "@/components/ai-workspace/copilot/retrieval-trace";
import {
  ThreadEmptyState,
  type Suggestion,
} from "@/components/ai-workspace/copilot/thread-empty-state";
import type { TurnNoticeState } from "@/components/ai-workspace/copilot/turn-notice";
import { cn } from "@/lib/utils";
import type { Citation } from "@/types/chat";

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  sources?: string[];
  timestamp?: number;
  isError?: boolean;
  /** Retrieval progress for an assistant turn, from the SSE stream. */
  trace?: RetrievalTraceState;
  /**
   * A failure, timeout or cancellation for this turn. Kept out of `content`
   * so any partial answer already streamed stays clean, readable markdown.
   */
  notice?: TurnNoticeState;
  /** How much of the finished answer the cited passages actually carry. */
  grounding?: AnswerGroundingState;
};

type ConversationAreaProps = {
  messages: Message[];
  isWaiting: boolean;
  draft: string;
  onDraftChange: (value: string) => void;
  onSubmit: (overrideQuestion?: string) => void;
  onCancel?: () => void;
  disabled?: boolean;
  onCitationSelect?: (messageId: string, index: number, citation?: Citation) => void;
  activeCitation?: { messageId: string; index: number } | null;
  streamingMessageId?: string | null;
  onEditMessage?: (id: string, newContent: string) => void;
  onRegenerateMessage?: (id: string) => void;
  restoreNotice?: "not_found" | "incomplete" | null;
  onDismissRestoreNotice?: () => void;
  suggestions?: Suggestion[];
  onRetryMessage?: (id: string) => void;
};

export function ConversationArea({
  messages,
  isWaiting,
  draft,
  onDraftChange,
  onSubmit,
  onCancel,
  disabled,
  onCitationSelect,
  activeCitation = null,
  streamingMessageId,
  onEditMessage,
  onRegenerateMessage,
  restoreNotice,
  onDismissRestoreNotice,
  suggestions = [],
  onRetryMessage,
}: ConversationAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const initialScrollDone = useRef(false);

  useEffect(() => {
    const behavior = initialScrollDone.current ? "smooth" : "auto";
    bottomRef.current?.scrollIntoView({ behavior });
    initialScrollDone.current = true;
  }, [messages, isWaiting]);

  useEffect(() => {
    if (!disabled && !isWaiting) {
      inputRef.current?.focus();
    }
  }, [disabled, isWaiting, messages.length]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3 sm:px-4">
        <div className="mx-auto max-w-3xl space-y-1">
          {messages.length === 0 && !isWaiting && (
            <ThreadEmptyState
              variant={restoreNotice === "not_found" ? "not_found" : "default"}
              suggestions={suggestions}
              onSelect={(prompt) => onSubmit(prompt)}
            />
          )}

          {/* A restored thread whose last answer was cut off still has
              messages, so this cannot live in the empty state. */}
          {restoreNotice === "incomplete" && messages.length > 0 && (
            <div className="mb-2 flex items-start gap-1.5 rounded border border-[var(--warning)]/30 bg-[var(--warning)]/8 px-2.5 py-2">
              <AlertTriangle
                className="mt-[1px] size-3.5 shrink-0 text-[var(--warning)]"
                strokeWidth={2}
              />
              <p className="min-w-0 flex-1 text-[12px] leading-[1.5] text-foreground/85">
                The last answer was cut off before it finished. Ask again to
                continue.
              </p>
              {onDismissRestoreNotice && (
                <button
                  type="button"
                  onClick={onDismissRestoreNotice}
                  className="shrink-0 text-[var(--warning)]/70 transition-industrial hover:text-[var(--warning)]"
                  aria-label="Dismiss"
                >
                  <X className="size-3" strokeWidth={2} />
                </button>
              )}
            </div>
          )}

          {messages.map((msg, index) => (
            <ChatMessage
              key={msg.id}
              role={msg.role}
              content={msg.content}
              citations={msg.citations}
              onCitationSelect={(index) =>
                onCitationSelect?.(msg.id, index, msg.citations?.[index])
              }
              activeCitationIndex={
                activeCitation?.messageId === msg.id ? activeCitation.index : null
              }
              trace={msg.trace}
              notice={msg.notice}
              grounding={msg.grounding}
              onRetry={
                msg.notice?.kind === "error" && onRetryMessage
                  ? () => onRetryMessage(msg.id)
                  : undefined
              }
              isStreaming={msg.id === streamingMessageId}
              timestamp={msg.timestamp}
              isError={msg.isError}
              onEdit={msg.role === "user" ? (newContent) => onEditMessage?.(msg.id, newContent) : undefined}
              onRegenerate={msg.role === "assistant" && index === messages.length - 1 ? () => onRegenerateMessage?.(msg.id) : undefined}
              onStop={isWaiting && msg.id === streamingMessageId ? onCancel : undefined}
            />
          ))}

          <div ref={bottomRef} className="h-px w-full" />
        </div>
      </div>

      <div className="shrink-0 border-t border-border bg-[var(--surface)] px-3 py-2.5">
        <div className="relative mx-auto max-w-3xl">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              onSubmit();
            }}
            className="relative flex items-end gap-2 rounded-lg border border-border bg-[var(--surface-secondary)] p-1 transition-industrial focus-within:border-[var(--accent-steel)]/45"
          >
            <textarea
              ref={inputRef}
              value={draft}
              onChange={(event) => onDraftChange(event.target.value)}
              placeholder="Ask about assets, procedures, compliance, or incidents…"
              disabled={disabled}
              rows={1}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  onSubmit();
                }
              }}
              className="max-h-40 min-h-[34px] w-full resize-none bg-transparent py-2 pl-2.5 pr-11 text-[13px] leading-[1.55] text-foreground outline-none placeholder:text-muted-foreground"
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = "auto";
                el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
              }}
            />
            <div className="absolute bottom-1.5 right-1.5 flex items-center">
              {isWaiting ? (
                <button
                  type="button"
                  onClick={onCancel}
                  className="flex size-7 items-center justify-center rounded-md bg-[var(--surface-tertiary)] text-[var(--danger)] transition-industrial hover:bg-[var(--danger)]/20"
                  title="Stop generating"
                >
                  <X className="size-3.5" strokeWidth={2} />
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={disabled || !draft.trim()}
                  className={cn(
                    "flex size-7 items-center justify-center rounded-md transition-industrial",
                    draft.trim() && !disabled
                      ? "bg-[var(--accent-steel)] text-white hover:bg-[var(--accent-steel)]/90"
                      : "bg-[var(--surface-tertiary)] text-foreground/30"
                  )}
                  title="Send message"
                >
                  <SendHorizonal className="size-3.5" strokeWidth={1.75} />
                </button>
              )}
            </div>
          </form>
          <p className="mt-1.5 text-[10px] leading-none text-muted-foreground/60">
            Enter to send · Shift+Enter for newline · verify critical values against the cited source
          </p>
        </div>
      </div>
    </div>
  );
}
