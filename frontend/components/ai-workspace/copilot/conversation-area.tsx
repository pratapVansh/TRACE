"use client";

import { useEffect, useRef } from "react";
import { SendHorizonal, Sparkles, Loader2 } from "lucide-react";

import { ChatMessage } from "@/components/ai-workspace/copilot/chat-message";
import { TypingIndicator } from "@/components/ai-workspace/copilot/typing-indicator";
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
  onEditMessage?: (id: string, newContent: string) => void;
  onRegenerateMessage?: (id: string) => void;
  restoreNotice?: "not_found" | "incomplete" | null;
};

const SUGGESTED_PROMPTS = [
  { id: "1", label: "Summarize recent incidents", prompt: "Summarize all safety incidents from the past 30 days." },
  { id: "2", label: "Find maintenance guides", prompt: "Find maintenance procedures for the hydraulic press." },
  { id: "3", label: "Check compliance", prompt: "What are the latest compliance requirements for handling hazardous waste?" },
  { id: "4", label: "Analyze asset", prompt: "Give me an overview of pump P-101 and its maintenance history." },
];

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
  onEditMessage,
  onRegenerateMessage,
  restoreNotice,
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
    <div className="flex h-full flex-col relative">
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-6 px-4 pt-8 pb-36 sm:px-6">
          {messages.length === 0 && !isWaiting && (
            <div className="flex min-h-[60vh] flex-col items-center justify-center">
              {restoreNotice === "not_found" ? (
                <div className="text-center">
                  <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-xl bg-[var(--bg-tertiary)]">
                    <Sparkles className="size-6 text-[var(--text-muted)]" strokeWidth={1.5} />
                  </div>
                  <h2 className="mb-1 text-lg font-semibold">Conversation not found</h2>
                  <p className="mb-4 text-sm text-[var(--text-secondary)]">
                    The previous conversation was deleted or is no longer available.
                  </p>
                </div>
              ) : restoreNotice === "incomplete" ? (
                <div className="text-center">
                  <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-xl bg-amber-500/10">
                    <span className="text-xl text-amber-400">!</span>
                  </div>
                  <h2 className="mb-1 text-lg font-semibold">Response interrupted</h2>
                  <p className="mb-4 text-sm text-[var(--text-secondary)]">
                    The last response was cut off. Ask your question again to continue.
                  </p>
                </div>
              ) : (
                <>
                  <div className="mx-auto mb-6 flex size-14 items-center justify-center rounded-2xl bg-[var(--accent-muted)]">
                    <Sparkles className="size-7 text-[var(--accent)]" strokeWidth={1.5} />
                  </div>
                  <h2 className="mb-2 text-xl font-semibold tracking-tight">
                    Ask TRACE anything
                  </h2>
                  <p className="mb-8 text-center text-sm text-[var(--text-secondary)] max-w-sm">
                    Search documents, explore assets, analyze operations, and get AI-powered insights.
                  </p>

                  <div className="flex w-full max-w-lg flex-wrap justify-center gap-2">
                    {SUGGESTED_PROMPTS.map(p => (
                      <button
                        key={p.id}
                        onClick={() => {
                          onDraftChange(p.prompt);
                          setTimeout(() => onSubmit(), 100);
                        }}
                        className="rounded-full border border-[var(--border)] bg-[var(--bg-secondary)] px-4 py-2 text-sm text-[var(--text-secondary)] transition-all hover:border-[var(--accent)]/30 hover:bg-[var(--accent-muted)] hover:text-[var(--accent)]"
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {messages.map((msg, index) => (
            <ChatMessage
              key={msg.id}
              role={msg.role}
              content={msg.content}
              citations={msg.citations}
              onCitationClick={onCitationClick}
              isStreaming={msg.id === streamingMessageId}
              timestamp={msg.timestamp}
              isError={msg.isError}
              onEdit={msg.role === "user" ? (newContent) => onEditMessage?.(msg.id, newContent) : undefined}
              onRegenerate={msg.role === "assistant" && index === messages.length - 1 ? () => onRegenerateMessage?.(msg.id) : undefined}
              onStop={isWaiting && msg.id === streamingMessageId ? onCancel : undefined}
            />
          ))}

          {isWaiting && !streamingMessageId && (
            <div className="flex items-center gap-2 py-2">
              <Loader2 className="size-4 animate-spin text-[var(--accent)]" />
              <span className="text-sm text-[var(--text-muted)]">Thinking...</span>
            </div>
          )}

          <div ref={bottomRef} className="h-px" />
        </div>
      </div>

      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-[var(--bg)] via-[var(--bg)]/95 to-transparent pt-12 pb-4">
        <div className="mx-auto max-w-3xl px-4 sm:px-6">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              onSubmit();
            }}
            className="relative flex items-end gap-2 rounded-2xl border border-[var(--border)] bg-[var(--bg-secondary)] shadow-lg shadow-black/10 transition-all focus-within:border-[var(--accent)]/40 focus-within:ring-1 focus-within:ring-[var(--accent)]/20"
          >
            <textarea
              ref={inputRef}
              value={draft}
              onChange={(event) => onDraftChange(event.target.value)}
              placeholder="Ask TRACE about your documents, assets, and operations..."
              disabled={disabled}
              rows={1}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  onSubmit();
                }
              }}
              className="max-h-48 min-h-[52px] w-full resize-none bg-transparent py-4 pl-5 pr-14 text-[15px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none leading-relaxed"
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = "auto";
                el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
              }}
            />
            <div className="absolute right-2 bottom-2">
              {isWaiting ? (
                <button
                  type="button"
                  onClick={onCancel}
                  className="flex size-9 items-center justify-center rounded-xl bg-[var(--bg-tertiary)] hover:bg-[var(--danger)]/15 text-[var(--text-secondary)] hover:text-[var(--danger)] transition-colors"
                  title="Stop generating"
                >
                  <Loader2 className="size-4 animate-spin" strokeWidth={2} />
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={disabled || !draft.trim()}
                  className={cn(
                    "flex size-9 items-center justify-center rounded-xl transition-all",
                    draft.trim() && !disabled
                      ? "bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] shadow-sm"
                      : "bg-[var(--bg-tertiary)] text-[var(--text-muted)]",
                  )}
                  title="Send message"
                >
                  <SendHorizonal className="size-4" strokeWidth={1.5} />
                </button>
              )}
            </div>
          </form>
          <p className="mt-2.5 text-center text-[11px] text-[var(--text-muted)]/60">
            AI responses can be inaccurate. Please verify critical information.
          </p>
        </div>
      </div>
    </div>
  );
}
