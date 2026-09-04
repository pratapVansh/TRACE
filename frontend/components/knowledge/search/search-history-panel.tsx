"use client";

import { Clock, Search } from "lucide-react";

import { formatRelativeTime } from "@/lib/dashboard/format";
import type { SearchHistoryItem } from "@/types/knowledge";

type SearchHistoryPanelProps = {
  history: SearchHistoryItem[];
  onSelect: (query: string) => void;
};

export function SearchHistoryPanel({ history, onSelect }: SearchHistoryPanelProps) {
  return (
    <div className="industrial-card p-2.5 sm:p-3">
      <p className="section-label">Query log</p>
      <h3 className="mt-2 text-[14px] font-semibold text-foreground">Search history</h3>
      <p className="mt-2 text-[12px] text-muted-foreground">
        Recent semantic queries across the knowledge base.
      </p>

      <ul className="mt-5 space-y-2">
        {history.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => onSelect(item.query)}
              className="flex w-full items-start gap-3 rounded-md border border-border bg-[var(--surface-secondary)] p-4 text-left transition-industrial hover:border-[var(--accent-steel)]/25 hover:bg-[var(--surface)]"
            >
              <Search className="mt-0.5 size-4 shrink-0 text-[var(--accent-steel-muted)]" />
              <div className="min-w-0 flex-1">
                <p className="text-[12px] text-foreground">&ldquo;{item.query}&rdquo;</p>
                <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  <span>{item.resultCount} results</span>
                  <span className="inline-flex items-center gap-1">
                    <Clock className="size-3" />
                    {formatRelativeTime(item.searchedAt)}
                  </span>
                </p>
              </div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
