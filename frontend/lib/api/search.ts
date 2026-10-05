import { apiClient } from "./client";
import type {
  SearchResponse,
  SearchResultItem,
  SearchFilter,
} from "@/types/knowledge";
import type { SearchHistoryItem } from "@/types/knowledge";

export interface SemanticSearchParams {
  query: string;
  top_k?: number;
  offset?: number;
  filters?: SearchFilter;
  mode?: "hybrid" | "semantic" | "keyword" | "ranked";
}

function toIsoDate(dateStr: string | undefined): string | undefined {
  if (!dateStr) return undefined;
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    return `${dateStr}T00:00:00Z`;
  }
  return dateStr;
}

export async function semanticSearch(
  params: SemanticSearchParams,
): Promise<SearchResultItem[]> {
  const filters = params.filters
    ? {
        ...params.filters,
        uploaded_after: toIsoDate(params.filters.uploaded_after),
        uploaded_before: toIsoDate(params.filters.uploaded_before),
      }
    : undefined;

  const { data } = await apiClient.post<SearchResponse>("/api/search", {
    query: params.query,
    top_k: params.top_k ?? 30,
    offset: params.offset ?? 0,
    filters,
    mode: params.mode ?? "ranked",
  });
  return data.results;
}

type SearchHistoryApiItem = {
  id: string;
  query: string;
  result_count: number;
  searched_at: string;
};

function mapHistory(item: SearchHistoryApiItem): SearchHistoryItem {
  return {
    id: item.id,
    query: item.query,
    resultCount: item.result_count,
    searchedAt: item.searched_at,
  };
}

export async function fetchSearchHistory(): Promise<SearchHistoryItem[]> {
  const { data } = await apiClient.get<SearchHistoryApiItem[]>("/api/search/history");
  return data.map(mapHistory);
}

export async function recordSearchHistory(params: {
  query: string;
  resultCount: number;
  filters?: SearchFilter;
}): Promise<SearchHistoryItem> {
  const { data } = await apiClient.post<SearchHistoryApiItem>("/api/search/history", {
    query: params.query,
    result_count: params.resultCount,
    filters: params.filters,
  });
  return mapHistory(data);
}

export async function deleteSearchHistory(id: string): Promise<void> {
  await apiClient.delete(`/api/search/history/${id}`);
}

export async function clearSearchHistory(): Promise<void> {
  await apiClient.delete("/api/search/history");
}

export type { SearchFilter, SearchResultItem };
