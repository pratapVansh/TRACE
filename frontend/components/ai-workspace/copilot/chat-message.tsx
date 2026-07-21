"use client";

import { useState } from "react";
import { Bot, Check, Copy, Loader2, UserRound, Edit2, RotateCw, AlertTriangle, PlaySquare } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { Citation } from "@/types/chat";
import { cn } from "@/lib/utils";
import { EnterpriseReportRenderer } from "./enterprise-report-renderer";

type ChatMessageProps = {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  onCitationClick?: (citation: Citation) => void;
  isStreaming?: boolean;
  timestamp?: number;
  onEdit?: (newContent: string) => void;
  onRegenerate?: () => void;
  onStop?: () => void;
  isError?: boolean;
};

export function ChatMessage({
  role,
  content,
  citations,
  onCitationClick,
  isStreaming,
  timestamp = Date.now() / 1000,
  onEdit,
  onRegenerate,
  onStop,
  isError,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(content);
  const isUser = role === "user";

  const timeString = new Date(timestamp * 1000).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });

  async function handleCopy() {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleSaveEdit() {
    if (editValue.trim() !== content && editValue.trim() !== "") {
      onEdit?.(editValue);
    }
    setIsEditing(false);
  }

  return (
    <div className={cn("group flex gap-4 py-4 px-2 hover:bg-[var(--surface-tertiary)]/30 rounded-2xl transition-colors", isUser ? "flex-row-reverse" : "flex-row")}>
      <div
        className={cn(
          "flex size-10 shrink-0 items-center justify-center rounded-full border shadow-sm",
          isUser
            ? "border-[var(--accent-steel)]/20 bg-gradient-to-br from-[var(--surface-secondary)] to-[var(--surface-tertiary)] text-[var(--accent-steel)]"
            : "border-[var(--accent-steel)]/40 bg-gradient-to-br from-[var(--accent-steel)]/20 to-transparent text-[var(--accent-steel-muted)]",
          isError && !isUser && "border-red-500/40 text-red-400 bg-red-500/10"
        )}
      >
        {isUser ? (
          <UserRound className="size-5" strokeWidth={1.5} />
        ) : isError ? (
          <AlertTriangle className="size-5" strokeWidth={1.5} />
        ) : (
          <Bot className="size-5" strokeWidth={1.5} />
        )}
      </div>

      <div className={cn("flex flex-col gap-2 max-w-[85%]", isUser ? "items-end" : "items-start")}>
        <div className="flex items-center gap-2 px-1">
          <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
            {isUser ? "You" : "Industrial Copilot"}
          </span>
          <span className="text-[10px] text-muted-foreground/60">{timeString}</span>
        </div>

        {isEditing && isUser ? (
          <div className="flex w-full min-w-[300px] flex-col gap-2 rounded-2xl border border-[var(--accent-steel)]/40 bg-[var(--surface-secondary)] p-3 shadow-lg">
            <textarea
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              className="w-full resize-none bg-transparent text-sm text-foreground outline-none leading-relaxed"
              rows={3}
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setIsEditing(false)}
                className="rounded-lg px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-white/5 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveEdit}
                className="rounded-lg bg-[var(--accent-steel)] px-3 py-1.5 text-xs font-medium text-[var(--accent-foreground)] hover:bg-[var(--accent-steel)]/80 transition-colors"
              >
                Save & Submit
              </button>
            </div>
          </div>
        ) : (
          <div
            className={cn(
              "relative space-y-3 rounded-2xl px-5 py-3.5",
              isUser
                ? "bg-[var(--surface-secondary)] text-foreground border border-white/5"
                : "bg-transparent",
              isError && "border border-red-500/20 bg-red-500/5"
            )}
          >
            {isUser ? (
              <p className="break-words text-[15px] leading-relaxed text-foreground/90">
                {content}
              </p>
            ) : (
              <div className="prose prose-invert prose-p:leading-relaxed prose-pre:bg-[var(--surface-tertiary)] prose-pre:border prose-pre:border-white/10 prose-sm max-w-none break-words text-[15px] text-foreground/90">
                {content ? (
                  <EnterpriseReportRenderer content={content} />
                ) : isStreaming ? (
                  <span className="animate-pulse text-muted-foreground">Thinking...</span>
                ) : (
                  ""
                )}
              </div>
            )}

            {citations && citations.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-2">
                {citations.map((citation, i) => (
                  <span
                    key={i}
                    className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--accent-steel)]/20 bg-[var(--accent-steel)]/10 px-2.5 py-1 text-xs text-[var(--accent-steel-muted)] transition-all hover:border-[var(--accent-steel)]/40 hover:bg-[var(--accent-steel)]/20 shadow-sm"
                    onClick={() => onCitationClick?.(citation)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onCitationClick?.(citation);
                      }
                    }}
                  >
                    <PlaySquare className="size-3" strokeWidth={2} />
                    <span className="font-medium text-white/90">
                      {citation.document_name}
                    </span>
                    {citation.page_number != null && (
                      <span className="text-white/60">p.{citation.page_number}</span>
                    )}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Message Actions */}
        {!isEditing && (
          <div className={cn("flex items-center gap-2 pt-1 opacity-0 group-hover:opacity-100 transition-opacity px-2", isUser && "justify-end")}>
            {isUser && onEdit && (
              <button
                onClick={() => setIsEditing(true)}
                className="inline-flex items-center gap-1.5 rounded-lg p-1.5 text-xs text-muted-foreground transition-colors hover:bg-[var(--surface-tertiary)] hover:text-white"
                title="Edit prompt"
              >
                <Edit2 className="size-3.5" strokeWidth={2} />
              </button>
            )}
            
                {!isUser && (
                  <>
                    <button
                  type="button"
                  onClick={handleCopy}
                  className="inline-flex items-center gap-1.5 rounded-lg p-1.5 text-xs text-muted-foreground transition-colors hover:bg-[var(--surface-tertiary)] hover:text-white"
                  title="Copy message"
                >
                  {copied ? <Check className="size-3.5 text-green-400" strokeWidth={2} /> : <Copy className="size-3.5" strokeWidth={2} />}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    const blob = new Blob([content], { type: "text/markdown" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `TRACE_Export_${new Date().toISOString().slice(0, 10)}.md`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-lg p-1.5 text-xs text-muted-foreground transition-colors hover:bg-[var(--surface-tertiary)] hover:text-white"
                  title="Export Markdown"
                >
                  <svg className="size-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>
                </button>
                
                {onRegenerate && !isStreaming && (
                  <button
                    onClick={onRegenerate}
                    className="inline-flex items-center gap-1.5 rounded-lg p-1.5 text-xs text-muted-foreground transition-colors hover:bg-[var(--surface-tertiary)] hover:text-white"
                    title={isError ? "Retry" : "Regenerate"}
                  >
                    <RotateCw className="size-3.5" strokeWidth={2} />
                  </button>
                )}
                
                {isStreaming && onStop && (
                  <button
                    onClick={onStop}
                    className="inline-flex items-center gap-1.5 rounded-lg p-1.5 text-xs text-red-400 transition-colors hover:bg-red-400/10"
                    title="Stop generating"
                  >
                    <div className="size-3 bg-red-400 rounded-sm" />
                    <span className="font-medium">Stop</span>
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
