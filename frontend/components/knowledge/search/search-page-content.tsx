"use client";

import { useMemo, useState } from "react";

import { DocumentTable } from "@/components/knowledge/documents/document-table";
import {
  DEFAULT_FILTERS,
  KnowledgeFilters,
} from "@/components/knowledge/knowledge-filters";
import { KnowledgePageHeader } from "@/components/knowledge/knowledge-page-header";
import { GlobalSearchBar } from "@/components/knowledge/search/global-search-bar";
import { SearchHistoryPanel } from "@/components/knowledge/search/search-history-panel";
import { SearchRecentDocuments } from "@/components/knowledge/search/search-recent-documents";
import {
  DEPARTMENTS,
  DOCUMENT_STATUSES,
  DOCUMENT_STATUS_LABELS,
  DOCUMENT_TYPES,
} from "@/lib/knowledge/constants";
import { KNOWLEDGE_DOCUMENTS, SEARCH_HISTORY } from "@/lib/knowledge/mock-data";
import { filterDocuments } from "@/lib/knowledge/utils";
import type { SearchHistoryItem } from "@/types/knowledge";

export function SearchPageContent() {
  const [query, setQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [history, setHistory] = useState<SearchHistoryItem[]>(SEARCH_HISTORY);

  const results = useMemo(
    () => filterDocuments(KNOWLEDGE_DOCUMENTS, activeQuery, filters),
    [activeQuery, filters],
  );

  const recentDocuments = useMemo(
    () =>
      [...KNOWLEDGE_DOCUMENTS]
        .sort(
          (a, b) =>
            new Date(b.lastUpdated).getTime() - new Date(a.lastUpdated).getTime(),
        )
        .slice(0, 5),
    [],
  );

  const handleSearch = () => {
    const trimmed = query.trim();
    if (!trimmed) return;

    setActiveQuery(trimmed);

    setHistory((current) => {
      const existing = current.find(
        (item) => item.query.toLowerCase() === trimmed.toLowerCase(),
      );
      const resultCount = filterDocuments(
        KNOWLEDGE_DOCUMENTS,
        trimmed,
        filters,
      ).length;

      if (existing) {
        return [
          {
            ...existing,
            resultCount,
            searchedAt: new Date().toISOString(),
          },
          ...current.filter((item) => item.id !== existing.id),
        ];
      }

      return [
        {
          id: `sh-${Date.now()}`,
          query: trimmed,
          resultCount,
          searchedAt: new Date().toISOString(),
        },
        ...current.slice(0, 9),
      ];
    });
  };

  const typeOptions = [
    { value: "all", label: "All types" },
    ...DOCUMENT_TYPES.map((type) => ({ value: type, label: type })),
  ];

  const statusOptions = [
    { value: "all", label: "All statuses" },
    ...DOCUMENT_STATUSES.map((status) => ({
      value: status,
      label: DOCUMENT_STATUS_LABELS[status],
    })),
  ];

  const departmentOptions = [
    { value: "all", label: "All departments" },
    ...DEPARTMENTS.map((department) => ({
      value: department,
      label: department,
    })),
  ];

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <KnowledgePageHeader
        sectionLabel="Knowledge Management"
        title="Search"
        description="Run semantic search across indexed documents, equipment tags, SOPs, and operational records at Northfield Refinery Complex."
      />

      <GlobalSearchBar
        value={query}
        onChange={setQuery}
        onSubmit={handleSearch}
        resultCount={activeQuery ? results.length : undefined}
      />

      <KnowledgeFilters
        filters={filters}
        onChange={setFilters}
        typeOptions={typeOptions}
        statusOptions={statusOptions}
        departmentOptions={departmentOptions}
      />

      {activeQuery ? (
        <DocumentTable documents={results} />
      ) : (
        <div className="grid gap-6 xl:grid-cols-12">
          <div className="xl:col-span-5">
            <SearchHistoryPanel
              history={history}
              onSelect={(selectedQuery) => {
                setQuery(selectedQuery);
                setActiveQuery(selectedQuery);
              }}
            />
          </div>
          <div className="xl:col-span-7">
            <SearchRecentDocuments documents={recentDocuments} />
          </div>
        </div>
      )}
    </div>
  );
}
