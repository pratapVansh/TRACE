"use client";

import { useState } from "react";
import { Bot, Check, Copy, UserRound } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { Citation } from "@/types/chat";
import { cn } from "@/lib/utils";

type ChatMessageProps = {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
};

export function ChatMessage({ role, content, citations }: ChatMessageProps) {
  const [copied, setCopied] = useState(false);
  const isUser = role === "user";

  async function handleCopy() {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
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
          "max-w-[85%] space-y-3 rounded-xl border px-4 py-3",
          isUser
            ? "border-border bg-[var(--surface-secondary)]"
            : "border-[var(--accent-steel)]/20 bg-[var(--surface)]",
        )}
      >
        {isUser ? (
          <p className="break-words text-sm leading-relaxed text-foreground">
            {content}
          </p>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none overflow-x-auto break-words text-sm leading-relaxed text-foreground">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content}
            </ReactMarkdown>
          </div>
        )}

        {citations && citations.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {citations.map((citation, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 rounded-md border border-[var(--accent-steel)]/15 bg-[var(--accent-steel)]/5 px-2 py-0.5 text-[11px] text-[var(--accent-steel-muted)]"
              >
                <span className="font-medium text-white">
                  {citation.document_name}
                </span>
                {citation.page_number != null && (
                  <span>p.{citation.page_number}</span>
                )}
                <span className="opacity-60">
                  {Math.round(citation.score * 100)}%
                </span>
              </span>
            ))}
          </div>
        )}

        {!isUser && (
          <div className="flex items-center gap-2 pt-1">
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-muted-foreground transition-industrial hover:text-white"
              title="Copy answer"
            >
              {copied ? (
                <Check className="size-3" strokeWidth={2} />
              ) : (
                <Copy className="size-3" strokeWidth={1.75} />
              )}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
