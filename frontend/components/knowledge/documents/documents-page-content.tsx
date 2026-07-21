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
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

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
    setActionError,
    previewDocument,
    previewUrl,
    previewText,
    isPreviewLoading,
    closePreview,
    handlePreview,
    handleDownload,
    handleDelete,
    handleBulkDelete,
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
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <KnowledgePageHeader
        sectionLabel="Knowledge Management"
        title="Documents"
        description="Browse, filter, and manage technical records, SOPs, inspection reports, and engineering documentation across the facility."
        action={
          <Link
            href={APP_ROUTES.documentsUpload}
            className="inline-flex h-10 items-center rounded-xl bg-[var(--accent-steel)] px-4 text-sm font-medium text-white transition-industrial hover:bg-[#6a8eb5]"
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
        <div className="rounded-xl border border-[var(--danger)]/25 bg-[var(--danger)]/10 px-4 py-3 text-sm text-[var(--danger)]">
          {error}
        </div>
      ) : null}

      {actionError ? (
        <div className="rounded-xl border border-[var(--danger)]/25 bg-[var(--danger)]/10 px-4 py-3 text-sm text-[var(--danger)]">
          {actionError}
        </div>
      ) : null}

      {isLoading ? (
        <div className="industrial-card space-y-3 p-6">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-12 w-full rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="industrial-card overflow-hidden">
          <DocumentTable
            documents={documents}
            showDepartment={false}
            canDelete={canModify}
            canEdit={canModify}
            selectedIds={selectedIds}
            onSelectionChange={canModify ? setSelectedIds : undefined}
            onPreview={handlePreview}
            onDownload={handleDownload}
            onDelete={async (doc) => {
              setDeletingId(doc.id);
              try {
                await handleDelete(doc);
              } finally {
                setDeletingId(null);
              }
            }}
            deletingId={deletingId}
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

      {canModify && selectedIds.size > 0 ? (
        <div className="fixed inset-x-0 bottom-0 z-50 flex items-center justify-center px-4 pb-4 pointer-events-none">
          <div className="flex items-center gap-4 rounded-2xl border border-border bg-[var(--surface-primary)]/95 px-6 py-3 shadow-2xl backdrop-blur-lg pointer-events-auto">
            <span className="text-sm text-muted-foreground">
              <strong className="text-white">{selectedIds.size}</strong> document(s) selected
            </span>
            <div className="h-6 w-px bg-border" />
            <button
              disabled={isBulkDeleting}
              onClick={async () => {
                setIsBulkDeleting(true);
                const ids = [...selectedIds];
                setSelectedIds(new Set());
                try {
                  await handleBulkDelete(ids);
                } finally {
                  setIsBulkDeleting(false);
                }
              }}
              className="inline-flex h-9 items-center gap-2 rounded-xl bg-[var(--danger)]/15 px-4 text-sm font-medium text-[var(--danger)] transition-industrial hover:bg-[var(--danger)]/25 disabled:opacity-50"
            >
              {isBulkDeleting ? "Deleting…" : <>Delete selected ({selectedIds.size})</>}
            </button>
            <button
              onClick={() => setSelectedIds(new Set())}
              className="inline-flex h-9 items-center rounded-xl px-3 text-sm text-muted-foreground transition-industrial hover:text-white"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}

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
