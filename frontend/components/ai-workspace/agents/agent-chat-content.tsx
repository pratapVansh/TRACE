"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, Loader2, SendHorizonal, X, UserRound, CheckCircle, AlertCircle, HelpCircle } from "lucide-react";

import { streamMultiAgent } from "@/lib/api/agents";
import { cn } from "@/lib/utils";
import type { MultiAgentResponse } from "@/types/ai-workspace";
import { EnterpriseReportRenderer } from "@/components/ai-workspace/copilot/enterprise-report-renderer";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  response?: MultiAgentResponse;
  agentProgress?: string;
  isStreaming?: boolean;
};

let msgCounter = 0;
function nextId(): string {
  msgCounter += 1;
  return `agent-msg-${Date.now()}-${msgCounter}`;
}

function StatementClassifications({ statements }: { statements: { text: string; classification: string; evidence_refs: string[] }[] }) {
  const facts = statements.filter((s) => s.classification === "FACT");
  const hypotheses = statements.filter((s) => s.classification === "HYPOTHESIS");
  const unknowns = statements.filter((s) => s.classification === "UNKNOWN");

  if (facts.length === 0 && hypotheses.length === 0 && unknowns.length === 0) return null;

  return (
    <div className="mt-3 space-y-1.5 border-t border-[var(--accent-steel)]/10 pt-2">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Evidence Classification
      </p>
      <div className="flex flex-wrap gap-1.5">
        {facts.length > 0 && (
          <span className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium text-green-400 bg-green-400/10">
            <CheckCircle className="size-3" strokeWidth={1.75} />
            {facts.length} Fact{facts.length !== 1 ? "s" : ""}
          </span>
        )}
        {hypotheses.length > 0 && (
          <span className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium text-yellow-400 bg-yellow-400/10">
            <AlertCircle className="size-3" strokeWidth={1.75} />
            {hypotheses.length} {hypotheses.length === 1 ? "Hypothesis" : "Hypotheses"}
          </span>
        )}
        {unknowns.length > 0 && (
          <span className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium text-[var(--text-secondary)] bg-[var(--bg-tertiary)]">
            <HelpCircle className="size-3" strokeWidth={1.75} />
            {unknowns.length} Unknown
          </span>
        )}
      </div>
    </div>
  );
}

export function AgentChatContent() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [isWaiting, setIsWaiting] = useState(false);

  const [conversationId, setConversationId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Load conversation on mount
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const savedId = localStorage.getItem("lastAgentConversationId");
        if (savedId) {
          const { fetchMessages } = await import("@/lib/api/chat");
          const msgData = await fetchMessages(savedId);
          if (cancelled) return;
          setConversationId(savedId);
          setMessages(
            msgData.messages.map((m: any) => ({
              id: m.id,
              role: m.role,
              content: m.content,
              response: undefined, 
            }))
          );
        }
      } catch (err) {}
    }
    load();
    return () => { cancelled = true; };
  }, []);

  // Save to localStorage when it changes
  useEffect(() => {
    if (conversationId) {
      localStorage.setItem("lastAgentConversationId", conversationId);
    }
  }, [conversationId]);

  const handleStop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsWaiting(false);
  }, []);

  const handleSubmit = useCallback(async () => {
    const question = draft.trim();
    if (!question || isWaiting) return;

    setDraft("");
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: "user", content: question },
    ]);
    setIsWaiting(true);

    const assistantId = nextId();
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", content: "", isStreaming: true, agentProgress: "Planning workflow..." },
    ]);

    abortControllerRef.current = new AbortController();

    try {
      await streamMultiAgent(
        {
          question,
          mode: "auto",
          conversation_id: conversationId,
        },
        (event, data) => {
          setMessages((prev) =>
            prev.map((msg) => {
              if (msg.id !== assistantId) return msg;

              if (event === "plan") {
                return { ...msg, agentProgress: "Executing plan..." };
              } else if (event === "agent_start") {
                return { ...msg, agentProgress: "Working on your request..." };
              } else if (event === "agent_end") {
                return { ...msg, agentProgress: "Consolidating findings..." };
              } else if (event === "agent_failed") {
                return { ...msg, agentProgress: "Agent failed, trying fallback..." };
              } else if (event === "token") {
                return { 
                  ...msg, 
                  content: msg.content + data,
                  agentProgress: "Generating report..."
                };
              } else if (event === "done") {
                const response = data as MultiAgentResponse;
                if (response.conversation_id) {
                  setConversationId(response.conversation_id);
                }
                return { 
                  ...msg, 
                  content: response.answer || msg.content, 
                  response, 
                  isStreaming: false, 
                  agentProgress: undefined 
                };
              } else if (event === "error") {
                return { ...msg, content: msg.content + "\n\n> [!WARNING]\n> Stream encountered an error.", isStreaming: false, agentProgress: undefined };
              }
              return msg;
            })
          );
            if (event === "done" || event === "error") {
              setIsWaiting(false);
            }
          },
          abortControllerRef.current.signal
        );
      } catch (error) {
      if ((error as any).name !== "AbortError") {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId
              ? { ...msg, content: "Sorry, a server error occurred. Please try again.", isStreaming: false, agentProgress: undefined }
              : msg,
          ),
        );
      }
      setIsWaiting(false);
    }
  }, [draft, isWaiting, conversationId]);



  return (
    <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-6 lg:gap-8">
      <div className="industrial-card flex h-full min-h-[600px] max-h-[calc(100vh-10rem)] flex-col overflow-hidden">
        <div className="border-b border-border px-5 py-4">
          <p className="section-label">AI Workspace</p>
          <h3 className="mt-1 text-lg font-semibold text-white">
            Industrial Copilot
          </h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Intelligent industrial assistant for procedures, compliance, incidents, and reports.
          </p>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
          {messages.length === 0 && !isWaiting && (
            <div className="flex h-full items-center justify-center">
              <div className="max-w-lg text-center">
                <div className="mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl border border-[var(--accent-steel)]/20 bg-[var(--accent-steel)]/10">
                  <Bot className="size-6 text-[var(--accent-steel-muted)]" strokeWidth={1.5} />
                </div>
                <p className="text-sm text-muted-foreground">
                  Ask a question about your industrial operations. For example:
                </p>
                <div className="mt-4 space-y-2 text-left text-xs text-muted-foreground">
                  <p>&bull; &ldquo;What is the root cause of pump P-101 failure?&rdquo;</p>
                  <p>&bull; &ldquo;Show me maintenance and compliance status for motor M-101&rdquo;</p>
                  <p>&bull; &ldquo;Generate a compliance report for the Q1 audit&rdquo;</p>
                  <p>&bull; &ldquo;Find the incident, analyse root cause, and generate a report&rdquo;</p>
                </div>
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={cn(
                "group flex gap-4 py-4 px-2 hover:bg-[var(--surface-tertiary)]/30 rounded-2xl transition-colors",
                msg.role === "user" ? "flex-row-reverse" : "flex-row",
              )}
            >
              <div
                className={cn(
                  "flex size-10 shrink-0 items-center justify-center rounded-full border shadow-sm",
                  msg.role === "user"
                    ? "border-[var(--accent-steel)]/20 bg-gradient-to-br from-[var(--surface-secondary)] to-[var(--surface-tertiary)] text-[var(--accent-steel)]"
                    : "border-[var(--accent-steel)]/40 bg-gradient-to-br from-[var(--accent-steel)]/20 to-transparent text-[var(--accent-steel-muted)]",
                )}
              >
                {msg.role === "user" ? <UserRound className="size-5" strokeWidth={1.5} /> : <Bot className="size-5" strokeWidth={1.5} />}
              </div>

              <div
                className={cn(
                  "flex flex-col gap-2 max-w-[85%]",
                  msg.role === "user" ? "items-end" : "items-start",
                )}
              >
                <div className="flex items-center justify-between px-1">
                  <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                    {msg.role === "user" ? "You" : "Industrial Copilot"}
                  </span>
                </div>
                <div
                  className={cn(
                    "relative space-y-3 rounded-2xl px-5 py-3.5",
                    msg.role === "user"
                      ? "bg-[var(--surface-secondary)] text-foreground border border-white/5"
                      : "bg-transparent",
                  )}
                >
                {msg.role === "user" ? (
                  <p className="break-words text-sm leading-relaxed text-foreground">
                    {msg.content}
                  </p>
                ) : (
                  <>
                    {msg.isStreaming && !msg.content ? (
                      <div className="flex items-center gap-2 text-[15px] text-muted-foreground">
                        <Loader2 className="size-4 animate-spin" />
                        {msg.agentProgress || "Thinking..."}
                      </div>
                    ) : (
                      <div className="prose prose-invert prose-p:leading-relaxed prose-pre:bg-[var(--surface-tertiary)] prose-pre:border prose-pre:border-white/10 prose-sm max-w-none break-words text-[15px] text-foreground/90">
                        <EnterpriseReportRenderer content={msg.content} />
                        {msg.isStreaming && (
                          <span className="ml-1 inline-block size-2 animate-pulse rounded-full bg-[var(--accent-steel)] align-middle" />
                        )}
                      </div>
                    )}
                    {msg.isStreaming && msg.content && (
                      <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
                        <Loader2 className="size-3 animate-spin" />
                        {msg.agentProgress}
                      </div>
                    )}

                    {msg.response && !msg.isStreaming && (
                      <div className="space-y-3 pt-2">
                        {/* Citations */}
                        {msg.response.citations.length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            {msg.response.citations.map((c, i) => (
                              <span
                                key={i}
                                className="inline-flex items-center gap-1 rounded-md border border-[var(--accent-steel)]/15 bg-[var(--accent-steel)]/5 px-2 py-0.5 text-[11px] text-[var(--accent-steel-muted)]"
                              >
                                <span className="font-medium text-white">
                                  {c.document_name}
                                </span>
                                {c.page_number != null && <span>p.{c.page_number}</span>}
                                <span className="opacity-60">
                                  {Math.round(c.similarity_score * 100)}%
                                </span>
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Evidence classification badges */}
                        {msg.response.agent_results?.some(
                          (r) => r.classified_statements && r.classified_statements.length > 0
                        ) && (
                          <StatementClassifications
                            statements={msg.response.agent_results.flatMap(
                              (r) => r.classified_statements || []
                            )}
                          />
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
          ))}

          {/* Removed old spinner, handled in streaming message now */}

          <div ref={bottomRef} />
        </div>

        <div className="border-t border-border p-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSubmit();
            }}
            className="flex gap-3"
          >
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask about assets, procedures, compliance, incidents, or generate reports…"
              disabled={isWaiting}
              rows={1}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit();
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
                onClick={handleStop}
                className="flex h-12 shrink-0 items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-5 text-sm font-medium text-red-400 hover:bg-red-500/20 transition-colors"
              >
                <X className="size-4" strokeWidth={1.75} />
                <span className="hidden sm:inline">Stop</span>
              </button>
            ) : (
              <button
                type="submit"
                disabled={!draft.trim()}
                className={cn(
                  "flex h-12 shrink-0 items-center gap-2 rounded-xl px-5 text-sm font-medium transition-industrial",
                  draft.trim()
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
    </div>
  );
}
