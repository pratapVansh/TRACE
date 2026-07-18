"use client";

import { useEffect, useRef } from "react";
import { SendHorizonal, X } from "lucide-react";

import { ChatMessage } from "@/components/ai-workspace/copilot/chat-message";
import { TypingIndicator } from "@/components/ai-workspace/copilot/typing-indicator";
import { cn } from "@/lib/utils";
import type { Citation } from "@/types/chat";

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  confidence?: number;
  sources?: string[];
};

type ConversationAreaProps = {
  messages: Message[];
  isWaiting: boolean;
  draft: string;
  onDraftChange: (value: string) => void;
  onSubmit: () => void;
  onCancel?: () => void;
  disabled?: boolean;
  onCitationClick?: (citation: Citation) => void;
  streamingMessageId?: string | null;
};

export function ConversationArea({
  messages,
  isWaiting,
  draft,
  onDraftChange,
  onSubmit,
  onCancel,
  disabled,
  onCitationClick,
  streamingMessageId,
}: ConversationAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isWaiting]);

  useEffect(() => {
    if (!disabled && !isWaiting) {
      inputRef.current?.focus();
    }
  }, [disabled, isWaiting, messages.length]);

  return (
    <div className="industrial-card flex h-full min-h-[600px] flex-col overflow-hidden">
      <div className="border-b border-border px-5 py-4">
        <p className="section-label">Conversation</p>
        <h3 className="mt-1 text-lg font-semibold text-white">
          Industrial Copilot
        </h3>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
        {messages.length === 0 && !isWaiting && (
          <div className="flex h-full items-center justify-center">
            <div className="max-w-md text-center">
              <div className="mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl border border-[var(--accent-steel)]/20 bg-[var(--accent-steel)]/10">
                <svg
                  className="size-6 text-[var(--accent-steel-muted)]"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.5}
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"
                  />
                </svg>
              </div>
              <p className="text-sm text-muted-foreground">
                Ask a question about your documents. The AI will search indexed
                records and provide grounded answers with citations.
              </p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <ChatMessage
            key={msg.id}
            role={msg.role}
            content={msg.content}
            citations={msg.citations}
            onCitationClick={onCitationClick}
            confidence={msg.role === "assistant" ? msg.confidence : undefined}
            isStreaming={msg.id === streamingMessageId}
          />
        ))}

        {isWaiting && !streamingMessageId && <TypingIndicator />}

        <div ref={bottomRef} />
      </div>

      <div className="border-t border-border p-4">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
          className="flex gap-3"
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
            className="min-h-[48px] max-h-32 flex-1 rounded-xl border border-border bg-[var(--surface-secondary)] px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground outline-none transition-industrial focus:border-[var(--accent-steel)]/40 disabled:opacity-50 resize-none leading-5"
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = `${Math.min(el.scrollHeight, 128)}px`;
            }}
          />
          {isWaiting ? (
            <button
              type="button"
              onClick={onCancel}
              className="flex h-12 shrink-0 items-center gap-2 rounded-xl border border-[var(--danger)]/40 bg-[var(--danger)]/10 px-5 text-sm font-medium text-[var(--danger)] transition-industrial hover:bg-[var(--danger)]/20"
            >
              <X className="size-4" strokeWidth={1.75} />
              <span className="hidden sm:inline">Cancel</span>
            </button>
          ) : (
            <button
              type="submit"
              disabled={disabled || !draft.trim()}
              className={cn(
                "flex h-12 shrink-0 items-center gap-2 rounded-xl px-5 text-sm font-medium transition-industrial",
                draft.trim() && !disabled
                  ? "bg-[var(--accent-steel)] text-white hover:bg-[var(--accent-steel)]/80"
                  : "bg-[var(--accent-steel)]/30 text-white/40",
              )}
            >
              <SendHorizonal className="size-4" strokeWidth={1.75} />
              <span className="hidden sm:inline">Send</span>
            </button>
          )}
        </form>
      </div>
    </div>
  );
}
