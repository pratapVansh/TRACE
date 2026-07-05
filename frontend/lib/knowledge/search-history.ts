import type { SearchHistoryItem } from "@/types/knowledge";

const SEARCH_HISTORY_KEY = "trace_search_history";
const MAX_SEARCH_HISTORY = 10;

export function loadSearchHistory(): SearchHistoryItem[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(SEARCH_HISTORY_KEY);
    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw) as SearchHistoryItem[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveSearchHistory(history: SearchHistoryItem[]): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(
    SEARCH_HISTORY_KEY,
    JSON.stringify(history.slice(0, MAX_SEARCH_HISTORY)),
  );
}

export function upsertSearchHistoryEntry(
  history: SearchHistoryItem[],
  entry: Omit<SearchHistoryItem, "id"> & { id?: string },
): SearchHistoryItem[] {
  const normalizedQuery = entry.query.trim();
  if (!normalizedQuery) {
    return history;
  }

  const nextEntry: SearchHistoryItem = {
    id: entry.id ?? `sh-${Date.now()}`,
    query: normalizedQuery,
    resultCount: entry.resultCount,
    searchedAt: entry.searchedAt,
  };

  const withoutDuplicate = history.filter(
    (item) => item.query.toLowerCase() !== normalizedQuery.toLowerCase(),
  );

  return [nextEntry, ...withoutDuplicate].slice(0, MAX_SEARCH_HISTORY);
}
