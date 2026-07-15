import { apiClient } from "./client";
import type {
  SearchResponse,
  SearchResultItem,
  SearchFilter,
} from "@/types/knowledge";

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

export type { SearchFilter, SearchResultItem };
