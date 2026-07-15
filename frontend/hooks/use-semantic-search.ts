"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { semanticSearch } from "@/lib/api/search";
import type {
  SearchFilter,
  SearchResultItem,
} from "@/types/knowledge";

const PAGE_SIZE = 20;

interface UseSemanticSearchOptions {
  query: string;
  filters?: SearchFilter;
  enabled?: boolean;
}

export function useSemanticSearch({
  query,
  filters,
  enabled = true,
}: UseSemanticSearchOptions) {
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [limit, setLimit] = useState(PAGE_SIZE);
  const abortRef = useRef<AbortController | null>(null);

  const trimmedQuery = query.trim();

  const fetchResults = useCallback(
    async (currentOffset: number, append: boolean) => {
      if (!trimmedQuery || !enabled) {
        setResults([]);
        setError(null);
        return;
      }

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      if (append) {
        setIsLoadingMore(true);
      } else {
        setIsLoading(true);
      }
      setError(null);

      try {
        const data = await semanticSearch({
          query: trimmedQuery,
          top_k: PAGE_SIZE,
          offset: currentOffset,
          filters,
        });

        if (controller.signal.aborted) {
          return;
        }

        setResults((prev) => (append ? [...prev, ...data] : data));
      } catch (err: unknown) {
        if (controller.signal.aborted) {
          return;
        }

        const message =
          err instanceof Error ? err.message : "Search failed. Please try again.";
        setError(message);
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
          setIsLoadingMore(false);
        }
      }
    },
    [trimmedQuery, filters, enabled],
  );

  useEffect(() => {
    setLimit(0);
    setResults([]);
    fetchResults(0, false);

    return () => {
      abortRef.current?.abort();
    };
  }, [fetchResults]);

  const loadMore = useCallback(() => {
    if (isLoadingMore || isLoading) {
      return;
    }
    const nextOffset = limit + PAGE_SIZE;
    setLimit(nextOffset);
    fetchResults(nextOffset, true);
  }, [limit, isLoadingMore, isLoading, fetchResults]);

  const hasMore = results.length >= limit + PAGE_SIZE;

  return {
    results,
    isLoading,
    isLoadingMore,
    error,
    hasMore,
    loadMore,
  };
}
