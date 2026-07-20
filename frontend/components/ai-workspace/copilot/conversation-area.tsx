"use client";

import { useEffect, useRef } from "react";
import { SendHorizonal, X, Sparkles, FileText, FileClock, Bolt } from "lucide-react";

import { ChatMessage } from "@/components/ai-workspace/copilot/chat-message";
import { TypingIndicator } from "@/components/ai-workspace/copilot/typing-indicator";
import { SuggestedPrompts } from "@/components/ai-workspace/copilot/suggested-prompts";
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
    <div className="flex h-full flex-col bg-background/50 overflow-hidden relative">
      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl space-y-6 pb-24">
          {messages.length === 0 && !isWaiting && (
            <div className="flex h-full min-h-[500px] flex-col items-center justify-center pt-12">
              {restoreNotice === "not_found" ? (
                <>
                  <div className="mb-6 flex size-16 items-center justify-center rounded-2xl bg-[var(--surface-tertiary)] border border-[var(--accent-steel)]/20">
                    <FileClock className="size-8 text-muted-foreground" strokeWidth={1.5} />
                  </div>
                  <h2 className="mb-2 text-xl font-bold text-white tracking-tight">Conversation not found</h2>
                  <p className="mb-2 text-center text-sm text-muted-foreground max-w-[420px]">
                    The previous conversation was deleted or is no longer available.
                  </p>
                  <p className="text-center text-xs text-muted-foreground/60 max-w-[420px]">
                    Start a new conversation below.
                  </p>
                </>
              ) : restoreNotice === "incomplete" ? (
                <>
                  <div className="mb-6 flex size-16 items-center justify-center rounded-2xl bg-amber-500/10 border border-amber-500/20">
                    <span className="text-2xl text-amber-400">&#9888;</span>
                  </div>
                  <h2 className="mb-2 text-xl font-bold text-white tracking-tight">Response interrupted</h2>
                  <p className="mb-2 text-center text-sm text-muted-foreground max-w-[420px]">
                    The last response was cut off before it completed. You can ask your question again to continue.
                  </p>
                </>
              ) : (
                <>
                  <div className="mb-10 flex size-16 items-center justify-center rounded-2xl bg-gradient-to-br from-[var(--accent-steel)] to-[var(--surface-tertiary)] shadow-lg shadow-[var(--accent-steel)]/20">
                    <Sparkles className="size-8 text-white" strokeWidth={1.5} />
                  </div>
                  <h2 className="mb-2 text-2xl font-bold text-white tracking-tight">How can I help you today?</h2>
                  <p className="mb-12 text-center text-sm text-muted-foreground max-w-[400px]">
                    Ask me about procedures, compliance documents, or past incidents. I can search through our indexed knowledge base and provide cited answers.
                  </p>

                  <div className="w-full max-w-2xl grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-4">
                      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        <Bolt className="size-4" /> Quick Actions
                      </div>
                      <div className="flex flex-col gap-2">
                        {SUGGESTED_PROMPTS.map(p => (
                          <button 
                            key={p.id}
                            onClick={() => {
                              onDraftChange(p.prompt);
                              setTimeout(() => onSubmit(), 100);
                            }}
                            className="text-left p-4 rounded-xl border border-white/5 bg-[var(--surface-secondary)] hover:bg-[var(--surface-tertiary)] hover:border-[var(--accent-steel)]/30 transition-all group shadow-sm"
                          >
                            <p className="text-sm font-medium text-white/90 group-hover:text-white mb-1">{p.label}</p>
                            <p className="text-xs text-muted-foreground line-clamp-1">{p.prompt}</p>
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        <FileClock className="size-4" /> Recently Viewed
                      </div>
                      <div className="flex flex-col gap-2">
                        {[1, 2].map(i => (
                          <div key={i} className="flex items-center gap-3 p-4 rounded-xl border border-white/5 bg-[var(--surface-secondary)] hover:bg-[var(--surface-tertiary)] transition-all cursor-pointer shadow-sm">
                            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-[var(--accent-steel)]/10 text-[var(--accent-steel)]">
                              <FileText className="size-4" />
                            </div>
                            <div>
                              <p className="text-sm font-medium text-white/90">Safety Protocol V{i}.0</p>
                              <p className="text-xs text-muted-foreground">Updated {i} days ago</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
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
            <div className="py-4">
              <TypingIndicator />
            </div>
          )}

          <div ref={bottomRef} className="h-px w-full" />
        </div>
      </div>

      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-[var(--background)] via-[var(--background)]/90 to-transparent pt-10 pb-6 px-4">
        <div className="mx-auto max-w-4xl relative">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              onSubmit();
            }}
            className="relative flex items-end gap-2 bg-[var(--surface-secondary)] border border-[var(--accent-steel)]/20 rounded-2xl shadow-xl shadow-black/20 focus-within:border-[var(--accent-steel)]/50 focus-within:ring-1 focus-within:ring-[var(--accent-steel)]/30 transition-all p-2"
          >
            <textarea
              ref={inputRef}
              value={draft}
              onChange={(event) => onDraftChange(event.target.value)}
              placeholder="Ask about assets, procedures, compliance, or incidents… (Enter to send, Shift+Enter for new line)"
              disabled={disabled}
              rows={1}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  onSubmit();
                }
              }}
              className="max-h-48 min-h-[44px] w-full resize-none bg-transparent py-3 pl-4 pr-12 text-[15px] text-foreground placeholder:text-muted-foreground outline-none leading-relaxed"
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = "auto";
                el.style.height = `${Math.min(el.scrollHeight, 192)}px`;
              }}
            />
            <div className="absolute right-3 bottom-3 flex items-center">
              {isWaiting ? (
                <button
                  type="button"
                  onClick={onCancel}
                  className="flex size-9 items-center justify-center rounded-xl bg-[var(--surface-tertiary)] hover:bg-red-500/20 text-red-400 transition-colors"
                  title="Stop generating"
                >
                  <X className="size-4" strokeWidth={2} />
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={disabled || !draft.trim()}
                  className={cn(
                    "flex size-9 items-center justify-center rounded-xl transition-all shadow-sm",
                    draft.trim() && !disabled
                      ? "bg-[var(--accent-steel)] text-white hover:bg-[var(--accent-steel)]/90"
                      : "bg-[var(--surface-tertiary)] text-white/30"
                  )}
                  title="Send message"
                >
                  <SendHorizonal className="size-4" strokeWidth={1.75} />
                </button>
              )}
            </div>
          </form>
          <div className="text-center mt-3 text-[11px] text-muted-foreground/60">
            AI responses can be inaccurate. Please verify critical information.
          </div>
        </div>
      </div>
    </div>
  );
}
