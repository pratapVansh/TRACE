"use client";

import { ExternalLink, FileText } from "lucide-react";
import { useMemo } from "react";

import { cn } from "@/lib/utils";
import type { SearchResultItem } from "@/types/knowledge";

function highlightSnippet(text: string, query: string, maxLen = 350): React.ReactNode {
  const terms = query.split(/\s+/).filter(Boolean);
  if (!terms.length || !text) {
    return text;
  }

  const lowerText = text.toLowerCase();
  const firstIdx = Math.min(
    ...terms.map((t) => {
      const idx = lowerText.indexOf(t.toLowerCase());
      return idx === -1 ? Infinity : idx;
    }),
  );

  if (firstIdx === Infinity) {
    return text.length > maxLen ? text.slice(0, maxLen) + "..." : text;
  }

  const start = Math.max(0, firstIdx - 100);
  const end = Math.min(text.length, firstIdx + 250);
  let snippet = text.slice(start, end);
  if (start > 0) snippet = "…" + snippet;
  if (end < text.length) snippet = snippet + "…";

  const escapedTerms = terms.map((t) =>
    t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
  );
  const pattern = new RegExp(`(${escapedTerms.join("|")})`, "gi");
  const parts = snippet.split(pattern);

  return parts.map((part, i) => {
    const isMatch = terms.some((t) => t.toLowerCase() === part.toLowerCase());
    return isMatch ? (
      <mark
        key={i}
        className="rounded-sm bg-[var(--accent-steel)]/20 text-[var(--accent-steel-muted)]"
      >
        {part}
      </mark>
    ) : (
      part
    );
  });
}

function scoreColor(score: number): string {
  if (score >= 0.7) return "bg-[var(--success)]";
  if (score >= 0.4) return "bg-[var(--warning)]";
  return "bg-[var(--danger)]";
}

type SearchResultCardProps = {
  result: SearchResultItem;
  query: string;
};

export function SearchResultCard({ result, query }: SearchResultCardProps) {
  const docUrl = `/documents${result.document_id ? `?id=${result.document_id}` : ""}`;

  const highlighted = useMemo(
    () => highlightSnippet(result.chunk, query),
    [result.chunk, query],
  );

  const language = result.metadata?.language as string | undefined;

  return (
    <div className="industrial-card group relative overflow-hidden transition-industrial hover:border-[var(--accent-steel)]/25">
      <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-start sm:p-6">
        <div className="flex shrink-0 items-center gap-3 sm:flex-col sm:items-start">
          <span
            className={cn(
              "inline-flex h-8 min-w-[3.25rem] items-center justify-center rounded-lg px-2 text-xs font-semibold text-white",
              scoreColor(result.score),
            )}
            title="Relevance score"
          >
            {(result.score * 100).toFixed(0)}
          </span>
        </div>

        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <FileText className="size-4 shrink-0 text-[var(--accent-steel-muted)]" />
            <span className="truncate text-sm font-medium text-white">
              {result.filename || "Unknown document"}
            </span>
            {result.page != null ? (
              <span className="inline-flex items-center gap-1 rounded-md border border-border bg-[var(--surface-secondary)] px-2 py-0.5 text-xs text-muted-foreground">
                p.{result.page}
              </span>
            ) : null}
            {language && language !== "unknown" ? (
              <span className="inline-flex items-center gap-1 rounded-md border border-border bg-[var(--surface-secondary)] px-2 py-0.5 text-xs text-muted-foreground">
                {language}
              </span>
            ) : null}
          </div>

          <div className="text-sm leading-relaxed text-muted-foreground [&>mark]:font-medium">
            {highlighted}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2 sm:flex-col">
          <a
            href={docUrl}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border px-3 text-xs font-medium text-muted-foreground transition-industrial hover:border-[var(--accent-steel)]/25 hover:text-white"
          >
            <ExternalLink className="size-3.5" />
            Open
          </a>
        </div>
      </div>
    </div>
  );
}
