"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { DocumentEditDialog } from "@/components/knowledge/documents/document-edit-dialog";
import { DocumentPagination } from "@/components/knowledge/documents/document-pagination";
import { DocumentPreviewDialog } from "@/components/knowledge/documents/document-preview-dialog";
import { DocumentTable } from "@/components/knowledge/documents/document-table";
import {
  DEFAULT_FILTERS,
  KnowledgeFilters,
} from "@/components/knowledge/knowledge-filters";
import { KnowledgePageHeader } from "@/components/knowledge/knowledge-page-header";
import { KnowledgeSearchBar } from "@/components/knowledge/knowledge-search-bar";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocumentActions } from "@/hooks/use-document-actions";
import { useDocuments } from "@/hooks/use-documents";
import { usePermissions } from "@/hooks/use-permissions";
import { APP_ROUTES } from "@/lib/auth/routes";
import { DEFAULT_PAGE_SIZE } from "@/lib/knowledge/constants";
import {
  DOC_TYPE_FILTER_OPTIONS,
  DOCUMENT_STATUSES,
  DOCUMENT_STATUS_LABELS,
} from "@/lib/knowledge/constants";
import { PERMISSIONS } from "@/types/permissions";
import type { KnowledgeDocument } from "@/types/knowledge";

export function DocumentsPageContent() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const [editingDocument, setEditingDocument] = useState<KnowledgeDocument | null>(
    null,
  );
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  const { canAccess } = usePermissions();
  const canModify = canAccess(PERMISSIONS.DOCUMENTS_UPLOAD);

  const {
    documents,
    total,
    totalPages,
    isLoading,
    error,
    updateDocument,
  } = useDocuments({
    search: debouncedQuery || undefined,
    docType: filters.type !== "all" ? filters.type : undefined,
    status: filters.status !== "all" ? filters.status : undefined,
    page,
    pageSize: DEFAULT_PAGE_SIZE,
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
    const timer = window.setTimeout(() => {
      setDebouncedQuery(query);
      setPage(1);
    }, 300);

    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    setPage(1);
  }, [filters.type, filters.status]);

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

  const handleSaveEdit = useCallback(
    async (values: {
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
    },
    [editingDocument, updateDocument],
  );

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-3 lg:gap-8">
      <KnowledgePageHeader
        sectionLabel="Knowledge Management"
        title="Documents"
        description="Browse, filter, and manage technical records, SOPs, inspection reports, and engineering documentation across the facility."
        action={
          <Link
            href={APP_ROUTES.documentsUpload}
            className="inline-flex h-7 items-center rounded-md bg-[var(--accent-steel)] px-4 text-[12px] font-medium text-white transition-industrial hover:bg-[#6a8eb5]"
          >
            Upload Documents
          </Link>
        }
      />

      <KnowledgeSearchBar
        value={query}
        onChange={setQuery}
        placeholder="Search by title or filename…"
      />

      <KnowledgeFilters
        filters={filters}
        onChange={setFilters}
        typeOptions={typeOptions}
        statusOptions={statusOptions}
      />

      {error ? (
        <div className="rounded-md border border-[var(--danger)]/25 bg-[var(--danger)]/10 px-4 py-3 text-[12px] text-[var(--danger)]">
          {error}
        </div>
      ) : null}

      {actionError ? (
        <div className="rounded-md border border-[var(--danger)]/25 bg-[var(--danger)]/10 px-4 py-3 text-[12px] text-[var(--danger)]">
          {actionError}
        </div>
      ) : null}

      {isLoading ? (
        <div className="industrial-card space-y-3 p-3">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-12 w-full rounded-md" />
          ))}
        </div>
      ) : (
        <div className="industrial-card overflow-hidden">
          <DocumentTable
            documents={documents}
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
