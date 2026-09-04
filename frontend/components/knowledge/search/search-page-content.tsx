"use client";

import { useEffect, useRef, useState } from "react";

import { KnowledgePageHeader } from "@/components/knowledge/knowledge-page-header";
import { GlobalSearchBar } from "@/components/knowledge/search/global-search-bar";
import { SearchFiltersPanel } from "@/components/knowledge/search/search-filters-panel";
import { SearchHistoryPanel } from "@/components/knowledge/search/search-history-panel";
import { SearchRecentDocuments } from "@/components/knowledge/search/search-recent-documents";
import { SearchResultCard } from "@/components/knowledge/search/search-result-card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSemanticSearch } from "@/hooks/use-semantic-search";
import { useRecentDocuments } from "@/hooks/use-documents";
import {
  loadSearchHistory,
  saveSearchHistory,
  upsertSearchHistoryEntry,
} from "@/lib/knowledge/search-history";
import type { SearchFilter, SearchHistoryItem } from "@/types/knowledge";

export function SearchPageContent() {
  const [query, setQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [filters, setFilters] = useState<SearchFilter>({});
  const [history, setHistory] = useState<SearchHistoryItem[]>([]);
  const [hasRecordedHistory, setHasRecordedHistory] = useState(false);

  const {
    results,
    isLoading,
    isLoadingMore,
    error,
    hasMore,
    loadMore,
  } = useSemanticSearch({
    query: activeQuery,
    filters,
    enabled: Boolean(activeQuery),
  });

  const { documents: recentDocuments, isLoading: isRecentLoading } =
    useRecentDocuments(5);

  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setHistory(loadSearchHistory());
  }, []);

  useEffect(() => {
    if (activeQuery && !isLoading && !hasRecordedHistory) {
      setHistory((current) => {
        const next = upsertSearchHistoryEntry(current, {
          query: activeQuery,
          resultCount: results.length,
          searchedAt: new Date().toISOString(),
        });
        saveSearchHistory(next);
        return next;
      });
      setHasRecordedHistory(true);
    }
    if (!activeQuery) {
      setHasRecordedHistory(false);
    }
  }, [activeQuery, isLoading, results.length, hasRecordedHistory]);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore || isLoading || isLoadingMore) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          loadMore();
        }
      },
      { rootMargin: "200px" },
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, isLoading, isLoadingMore, loadMore]);

  const handleSearch = () => {
    const trimmed = query.trim();
    if (!trimmed) return;
    setActiveQuery(trimmed);
    setHasRecordedHistory(false);
  };

  return (
    <div className="mx-auto flex w-full max-w-[1800px] flex-col gap-3">
      <KnowledgePageHeader
        sectionLabel="Knowledge Management"
        title="Search"
        description="Semantic search across all indexed documents. Uses hybrid ranking with vector similarity, keyword matching, and document freshness."
      />

      <GlobalSearchBar
        value={query}
        onChange={setQuery}
        onSubmit={handleSearch}
        resultCount={activeQuery ? results.length : undefined}
      />

      <SearchFiltersPanel filters={filters} onChange={setFilters} />

      {error ? (
        <div className="rounded-md border border-[var(--danger)]/25 bg-[var(--danger)]/10 px-4 py-3 text-[12px] text-[var(--danger)]">
          {error}
        </div>
      ) : null}

      {activeQuery ? (
        <>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="industrial-card p-3">
                  <div className="flex gap-4">
                    <Skeleton className="h-8 w-14 shrink-0 rounded-lg" />
                    <div className="flex-1 space-y-3">
                      <Skeleton className="h-5 w-3/5 rounded-lg" />
                      <Skeleton className="h-4 w-full rounded-lg" />
                      <Skeleton className="h-4 w-4/5 rounded-lg" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : results.length === 0 ? (
            <div className="industrial-card flex flex-col items-start gap-1 px-3 py-4">
              <div className="flex size-14 items-center justify-center rounded-full bg-[var(--surface-secondary)]">
                <svg
                  className="size-6 text-muted-foreground"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"
                  />
                </svg>
              </div>
              <p className="text-[13px] font-medium text-foreground">
                No results found
              </p>
              <p className="max-w-md text-[12px] text-muted-foreground">
                No matches for &ldquo;{activeQuery}&rdquo;. Try adjusting your
                search terms or removing filters.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-[12px] text-muted-foreground">
                Found{" "}
                <span className="font-medium text-foreground">
                  {results.length}
                </span>{" "}
                result{results.length === 1 ? "" : "s"} for &ldquo;
                {activeQuery}&rdquo;
              </p>
              <div className="space-y-2">
                {results.map((result, i) => (
                  <SearchResultCard
                    key={`${result.document_id}-${result.page ?? 0}-${i}`}
                    result={result}
                    query={activeQuery}
                  />
                ))}
              </div>

              {isLoadingMore ? (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={`more-skel-${i}`} className="industrial-card p-3">
                      <div className="flex gap-4">
                        <Skeleton className="h-8 w-14 shrink-0 rounded-lg" />
                        <div className="flex-1 space-y-3">
                          <Skeleton className="h-5 w-3/5 rounded-lg" />
                          <Skeleton className="h-4 w-full rounded-lg" />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}

              <div ref={sentinelRef} className="h-4" />
            </div>
          )}
        </>
      ) : (
        <div className="grid gap-3 xl:grid-cols-12">
          <div className="xl:col-span-5">
            <SearchHistoryPanel
              history={history}
              onSelect={(q) => {
                setQuery(q);
                setActiveQuery(q);
                setHasRecordedHistory(false);
              }}
            />
          </div>
          <div className="xl:col-span-7">
            {isRecentLoading ? (
              <div className="industrial-card space-y-3 p-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full rounded-md" />
                ))}
              </div>
            ) : (
              <SearchRecentDocuments documents={recentDocuments} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
