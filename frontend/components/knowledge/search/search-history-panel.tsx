"use client";

import { Clock, Search, Trash2 } from "lucide-react";

import { formatRelativeTime } from "@/lib/dashboard/format";
import type { SearchHistoryItem } from "@/types/knowledge";

type SearchHistoryPanelProps = {
  history: SearchHistoryItem[];
  onSelect: (query: string) => void;
  onDelete: (id: string) => void;
  onClear: () => void;
};

export function SearchHistoryPanel({ history, onSelect, onDelete, onClear }: SearchHistoryPanelProps) {
  return (
    <div className="industrial-card p-2.5 sm:p-3">
      <p className="section-label">Query log</p>
      <div className="mt-2 flex items-center justify-between gap-3">
        <h3 className="text-[14px] font-semibold text-foreground">Search history</h3>
        {history.length > 0 ? (
          <button
            type="button"
            onClick={onClear}
            className="text-[11px] font-medium text-[var(--danger)] hover:underline"
          >
            Clear all
          </button>
        ) : null}
      </div>
      <p className="mt-2 text-[12px] text-muted-foreground">
        Recent semantic queries across the knowledge base.
      </p>

      <ul className="mt-5 space-y-2">
        {history.map((item) => (
          <li key={item.id}>
            <div className="flex items-start rounded-md border border-border bg-[var(--surface-secondary)] transition-industrial hover:border-[var(--accent-steel)]/25 hover:bg-[var(--surface)]">
              <button
                type="button"
                onClick={() => onSelect(item.query)}
                className="flex min-w-0 flex-1 items-start gap-3 p-4 text-left"
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
              <button
                type="button"
                onClick={() => onDelete(item.id)}
                className="m-2 inline-flex size-8 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-[var(--danger)]/10 hover:text-[var(--danger)]"
                aria-label={`Delete search ${item.query}`}
                title="Delete search"
              >
                <Trash2 className="size-3.5" />
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
