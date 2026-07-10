"use client";

import { useEffect, useState } from "react";

import { DocumentEditDialog } from "@/components/knowledge/documents/document-edit-dialog";
import { DocumentPagination } from "@/components/knowledge/documents/document-pagination";
import { DocumentPreviewDialog } from "@/components/knowledge/documents/document-preview-dialog";
import { DocumentTable } from "@/components/knowledge/documents/document-table";
import {
  DEFAULT_FILTERS,
  KnowledgeFilters,
} from "@/components/knowledge/knowledge-filters";
import { KnowledgePageHeader } from "@/components/knowledge/knowledge-page-header";
import { GlobalSearchBar } from "@/components/knowledge/search/global-search-bar";
import { SearchHistoryPanel } from "@/components/knowledge/search/search-history-panel";
import { SearchRecentDocuments } from "@/components/knowledge/search/search-recent-documents";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocumentActions } from "@/hooks/use-document-actions";
import { useDocuments, useRecentDocuments } from "@/hooks/use-documents";
import { usePermissions } from "@/hooks/use-permissions";
import {
  DEPARTMENTS,
  DEFAULT_PAGE_SIZE,
  DOC_TYPE_FILTER_OPTIONS,
  DOCUMENT_STATUSES,
  DOCUMENT_STATUS_LABELS,
} from "@/lib/knowledge/constants";
import {
  loadSearchHistory,
  saveSearchHistory,
  upsertSearchHistoryEntry,
} from "@/lib/knowledge/search-history";
import { PERMISSIONS } from "@/types/permissions";
import type { KnowledgeDocument, SearchHistoryItem } from "@/types/knowledge";

export function SearchPageContent() {
  const [query, setQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const [history, setHistory] = useState<SearchHistoryItem[]>([]);
  const [editingDocument, setEditingDocument] = useState<KnowledgeDocument | null>(
    null,
  );
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  const { canAccess } = usePermissions();
  const canModify = canAccess(PERMISSIONS.DOCUMENTS_UPLOAD);

  const { documents: recentDocuments, isLoading: isRecentLoading } =
    useRecentDocuments(5);

  const {
    documents: results,
    total,
    totalPages,
    isLoading,
    error,
    updateDocument,
  } = useDocuments({
    search: activeQuery || undefined,
    docType: filters.type !== "all" ? filters.type : undefined,
    status: filters.status !== "all" ? filters.status : undefined,
    department: filters.department !== "all" ? filters.department : undefined,
    page,
    pageSize: DEFAULT_PAGE_SIZE,
    enabled: Boolean(activeQuery),
  });

  const {
    actionError,
    previewDocument,
    previewUrl,
    previewText,
    isPreviewLoading,
    closePreview,
    handlePreview,
    handleDownload,
    handleDelete,
  } = useDocumentActions();

  useEffect(() => {
    setHistory(loadSearchHistory());
  }, []);

  useEffect(() => {
    setPage(1);
  }, [activeQuery, filters.type, filters.status, filters.department]);

  const handleSearch = () => {
    const trimmed = query.trim();
    if (!trimmed) {
      return;
    }

    setActiveQuery(trimmed);
    setPage(1);
  };

  useEffect(() => {
    if (!activeQuery || isLoading) {
      return;
    }

    setHistory((current) => {
      const next = upsertSearchHistoryEntry(current, {
        query: activeQuery,
        resultCount: total,
        searchedAt: new Date().toISOString(),
      });
      saveSearchHistory(next);
      return next;
    });
  }, [activeQuery, isLoading, total]);

  const typeOptions = DOC_TYPE_FILTER_OPTIONS.map((option) => ({
    value: option.value,
    label: option.label,
  }));

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

  const handleSaveEdit = async (values: {
    title: string;
    docType: string;
    status: KnowledgeDocument["status"];
    department: string;
  }) => {
    if (!editingDocument) {
      return;
    }

    setIsSavingEdit(true);
    try {
      await updateDocument(editingDocument.id, {
        title: values.title,
        docType: values.docType,
        status: values.status,
        department: values.department,
      });
    } catch (error) {
      setIsSavingEdit(false);
      throw error;
    }
    setIsSavingEdit(false);
  };

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <KnowledgePageHeader
        sectionLabel="Knowledge Management"
        title="Search"
        description="Search indexed documents by title or filename across the knowledge repository."
      />

      <GlobalSearchBar
        value={query}
        onChange={setQuery}
        onSubmit={handleSearch}
        resultCount={activeQuery ? total : undefined}
      />

      <KnowledgeFilters
        filters={filters}
        onChange={setFilters}
        typeOptions={typeOptions}
        statusOptions={statusOptions}
        departmentOptions={departmentOptions}
      />

      {error ? (
        <div className="rounded-xl border border-[var(--danger)]/25 bg-[var(--danger)]/10 px-4 py-3 text-sm text-[var(--danger)]">
          {error}
        </div>
      ) : null}

      {actionError ? (
        <div className="rounded-xl border border-[var(--danger)]/25 bg-[var(--danger)]/10 px-4 py-3 text-sm text-[var(--danger)]">
          {actionError}
        </div>
      ) : null}

      {activeQuery ? (
        isLoading ? (
          <div className="industrial-card space-y-3 p-6">
            {Array.from({ length: 5 }).map((_, index) => (
              <Skeleton key={index} className="h-12 w-full rounded-xl" />
            ))}
          </div>
        ) : (
          <div className="industrial-card overflow-hidden">
            <DocumentTable
              documents={results}
              showDepartment={false}
              canDelete={canModify}
              canEdit={canModify}
              onPreview={handlePreview}
              onDownload={handleDownload}
              onDelete={handleDelete}
              onEdit={setEditingDocument}
            />
            <DocumentPagination
              page={page}
              totalPages={totalPages}
              total={total}
              pageSize={DEFAULT_PAGE_SIZE}
              onPageChange={setPage}
            />
          </div>
        )
      ) : (
        <div className="grid gap-6 xl:grid-cols-12">
          <div className="xl:col-span-5">
            <SearchHistoryPanel
              history={history}
              onSelect={(selectedQuery) => {
                setQuery(selectedQuery);
                setActiveQuery(selectedQuery);
                setPage(1);
              }}
            />
          </div>
          <div className="xl:col-span-7">
            {isRecentLoading ? (
              <div className="industrial-card space-y-3 p-6">
                {Array.from({ length: 3 }).map((_, index) => (
                  <Skeleton key={index} className="h-16 w-full rounded-xl" />
                ))}
              </div>
            ) : (
              <SearchRecentDocuments documents={recentDocuments} />
            )}
          </div>
        </div>
      )}

      <DocumentPreviewDialog
        open={previewDocument !== null}
        document={previewDocument}
        previewUrl={previewUrl}
        previewText={previewText}
        isLoading={isPreviewLoading}
        onClose={closePreview}
        onDownload={handleDownload}
      />

      <DocumentEditDialog
        open={editingDocument !== null}
        document={editingDocument}
        isSaving={isSavingEdit}
        onClose={() => setEditingDocument(null)}
        onSave={handleSaveEdit}
      />
    </div>
  );
}
