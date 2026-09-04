import { Search } from "lucide-react";

import { WidgetCard } from "@/components/dashboard/widget-card";
import { WidgetHeader } from "@/components/dashboard/widget-header";
import { formatRelativeTime } from "@/lib/dashboard/format";
import type { RecentSearch } from "@/types/dashboard";

type RecentSearchesWidgetProps = {
  searches: RecentSearch[];
};

export function RecentSearchesWidget({ searches }: RecentSearchesWidgetProps) {
  return (
    <WidgetCard>
      <WidgetHeader
        sectionLabel="Knowledge Retrieval"
        title="Recent Searches"
        description="Latest semantic queries across the industrial knowledge base."
      />

      <ul className="flex flex-1 flex-col gap-3">
        {searches.map((search) => (
          <li
            key={search.id}
            className="rounded-md border border-border bg-[var(--surface-secondary)] p-4 transition-industrial hover:border-[var(--accent-steel)]/20"
          >
            <div className="flex items-start gap-3">
              <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-[var(--surface)] text-[var(--accent-steel-muted)]">
                <Search className="size-4" strokeWidth={1.75} />
              </div>
              <div className="min-w-0 flex-1 space-y-2">
                <p className="text-[12px] font-medium text-foreground">&ldquo;{search.query}&rdquo;</p>
                <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  <span>{search.results} results</span>
                  <span>{search.user}</span>
                  <span>{formatRelativeTime(search.timestamp)}</span>
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </WidgetCard>
  );
}
