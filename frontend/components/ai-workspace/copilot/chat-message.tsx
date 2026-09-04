"use client";

import { useState } from "react";
import { Check, Copy, Download, Edit2, RotateCw, Square } from "lucide-react";

import type { Citation } from "@/types/chat";
import { cn } from "@/lib/utils";
import { AnswerGrounding, type AnswerGroundingState } from "./answer-grounding";
import { EnterpriseReportRenderer } from "./enterprise-report-renderer";
import { RetrievalTrace, type RetrievalTraceState } from "./retrieval-trace";
import { TurnNotice, type TurnNoticeState } from "./turn-notice";

type ChatMessageProps = {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  onCitationSelect?: (index: number) => void;
  activeCitationIndex?: number | null;
  trace?: RetrievalTraceState;
  notice?: TurnNoticeState;
  grounding?: AnswerGroundingState;
  onRetry?: () => void;
  isStreaming?: boolean;
  timestamp?: number;
  onEdit?: (newContent: string) => void;
  onRegenerate?: () => void;
  onStop?: () => void;
  isError?: boolean;
};

// Answers are documents, not chat bubbles. The renderer ships generous
// article spacing; these overrides tighten it to scanning density without
// forking the renderer itself.
const PROSE_DENSITY =
  "text-[13px] leading-[1.55] text-foreground/90 " +
  "[&_p]:mb-2 [&_p]:leading-[1.55] [&_ul]:mb-2 [&_ol]:mb-2 [&_li]:leading-[1.5] " +
  "[&_h1]:mt-4 [&_h1]:mb-1.5 [&_h1]:text-[14px] [&_h1]:pb-1 " +
  "[&_h2]:mt-3 [&_h2]:mb-1.5 [&_h2]:text-[13px] " +
  "[&_h3]:mt-2.5 [&_h3]:mb-1 [&_h3]:text-[13px] " +
  "[&_table]:mb-3 [&_th]:px-2 [&_th]:py-1.5 [&_td]:px-2 [&_td]:py-1.5 " +
  "[&_blockquote]:my-2 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0";

const iconButton =
  "inline-flex size-6 items-center justify-center rounded text-muted-foreground transition-industrial hover:bg-[var(--surface-tertiary)] hover:text-foreground";

export function ChatMessage({
  role,
  content,
  citations,
  onCitationSelect,
  activeCitationIndex = null,
  trace,
  notice,
  grounding,
  onRetry,
  isStreaming,
  timestamp,
  onEdit,
  onRegenerate,
  onStop,
  isError,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(content);
  const isUser = role === "user";
  // The backend signals "nothing retrieved" with an empty citations event
  // followed by its own message as a normal token.
  const noResults = trace?.phase === "empty" && content.trim().length > 0;

  const timeString =
    timestamp === undefined
      ? null
      : new Date(timestamp * 1000).toLocaleTimeString(undefined, {
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

  function handleExport() {
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `TRACE_Export_${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ── Question ────────────────────────────────────────────────
  if (isUser) {
    if (isEditing) {
      return (
        <div className="flex flex-col gap-1.5 rounded-md border border-[var(--accent-steel)]/40 bg-[var(--surface-secondary)] p-2">
          <textarea
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            className="w-full resize-none bg-transparent text-[13px] leading-[1.55] text-foreground outline-none"
            rows={3}
            autoFocus
          />
          <div className="flex justify-end gap-1.5">
            <button
              type="button"
              onClick={() => setIsEditing(false)}
              className="rounded px-2 py-1 text-[11px] font-medium text-muted-foreground transition-industrial hover:bg-[var(--surface)]/5"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSaveEdit}
              className="rounded bg-[var(--accent-steel)] px-2 py-1 text-[11px] font-medium text-white transition-industrial hover:bg-[var(--accent-steel)]/85"
            >
              Save &amp; submit
            </button>
          </div>
        </div>
      );
    }

    return (
      <div className="group flex items-start gap-2 pt-4 pb-1.5 first:pt-1">
        <span
          aria-hidden
          className="mt-[5px] h-3 w-[2px] shrink-0 rounded-full bg-[var(--accent-steel)]"
        />
        <p className="min-w-0 flex-1 text-[13px] font-medium leading-[1.5] text-foreground">
          {content}
        </p>
        {timeString && (
          <span className="mt-[3px] shrink-0 font-mono text-[10px] text-muted-foreground/60 tabular-nums">
            {timeString}
          </span>
        )}
        {onEdit && (
          <button
            type="button"
            onClick={() => setIsEditing(true)}
            className={cn(iconButton, "shrink-0 opacity-0 group-hover:opacity-100")}
            title="Edit question"
          >
            <Edit2 className="size-3" strokeWidth={2} />
          </button>
        )}
      </div>
    );
  }

  // ── Answer ──────────────────────────────────────────────────
  return (
    <div className="group pb-3">
      <div className="min-w-0">
        {trace && <RetrievalTrace state={trace} />}

        {/* Retrieval returned nothing: the backend's own wording, presented as
            a result rather than disguised as a normal answer. */}
        {noResults ? (
          <TurnNotice notice={{ kind: "empty", text: content.trim() }} />
        ) : (
          <>
            {notice && (
              <TurnNotice
                notice={notice}
                onRetry={onRetry}
                className={cn(content && "mb-2")}
              />
            )}

            {content ? (
              <div className={cn("max-w-none break-words", PROSE_DENSITY)}>
                <EnterpriseReportRenderer
                  content={content}
                  citations={citations}
                  activeCitationIndex={activeCitationIndex}
                  onCitationSelect={onCitationSelect}
                />
              </div>
            ) : null}

            {/* Only once the answer is settled — a partial answer would be
                measured against sentences the model has not finished. */}
            {grounding && !isStreaming ? (
              <AnswerGrounding state={grounding} />
            ) : null}
          </>
        )}
      </div>

      <div className="mt-1 flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
        <button type="button" onClick={handleCopy} className={iconButton} title="Copy answer">
          {copied ? (
            <Check className="size-3 text-[var(--success)]" strokeWidth={2.25} />
          ) : (
            <Copy className="size-3" strokeWidth={2} />
          )}
        </button>
        <button
          type="button"
          onClick={handleExport}
          className={iconButton}
          title="Export as Markdown"
        >
          <Download className="size-3" strokeWidth={2} />
        </button>
        {onRegenerate && !isStreaming && (
          <button
            type="button"
            onClick={onRegenerate}
            className={iconButton}
            title={isError ? "Retry" : "Regenerate"}
          >
            <RotateCw className="size-3" strokeWidth={2} />
          </button>
        )}
        {isStreaming && onStop && (
          <button
            type="button"
            onClick={onStop}
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium text-[var(--danger)] transition-industrial hover:bg-[var(--danger)]/10"
            title="Stop generating"
          >
            <Square className="size-2.5 fill-current" strokeWidth={0} />
            Stop
          </button>
        )}
      </div>
    </div>
  );
}
