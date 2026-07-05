"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useDocumentsContext } from "@/contexts/documents-context";
import { DEFAULT_PAGE_SIZE } from "@/lib/knowledge/constants";
import { getApiErrorMessage } from "@/lib/api/errors";
import type { KnowledgeDocument } from "@/types/knowledge";

export type DocumentQueryOptions = {
  search?: string;
  docType?: string;
  status?: string;
  department?: string;
  page?: number;
  pageSize?: number;
  enabled?: boolean;
};

export function useDocuments(options: DocumentQueryOptions = {}) {
  const {
    fetchDocuments,
    deleteDocument,
    updateDocument,
    fetchDocumentBlob,
    uploadDocument,
    queryVersion,
  } = useDocumentsContext();

  const page = options.page ?? 1;
  const pageSize = options.pageSize ?? DEFAULT_PAGE_SIZE;
  const enabled = options.enabled ?? true;

  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const skip = (page - 1) * pageSize;

  const queryKey = useMemo(
    () =>
      JSON.stringify({
        search: options.search ?? "",
        docType: options.docType ?? "",
        status: options.status ?? "",
        department: options.department ?? "",
        page,
        pageSize,
        queryVersion,
      }),
    [
      options.department,
      options.docType,
      options.search,
      options.status,
      page,
      pageSize,
      queryVersion,
    ],
  );

  useEffect(() => {
    if (!enabled) {
      setDocuments([]);
      setTotal(0);
      return;
    }

    let cancelled = false;

    const loadDocuments = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetchDocuments({
          skip,
          limit: pageSize,
          search: options.search,
          docType: options.docType,
          status: options.status,
          department: options.department,
        });

        if (cancelled) {
          return;
        }

        setDocuments(response.documents);
        setTotal(response.total);
      } catch (fetchError) {
        if (cancelled) {
          return;
        }

        setError(await getApiErrorMessage(fetchError, "Failed to load documents."));
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadDocuments();

    return () => {
      cancelled = true;
    };
  }, [
    enabled,
    fetchDocuments,
    options.department,
    options.docType,
    options.search,
    options.status,
    pageSize,
    queryKey,
    skip,
  ]);

  const refresh = useCallback(async () => {
    const response = await fetchDocuments({
      skip,
      limit: pageSize,
      search: options.search,
      docType: options.docType,
      status: options.status,
      department: options.department,
    });
    setDocuments(response.documents);
    setTotal(response.total);
  }, [
    fetchDocuments,
    options.department,
    options.docType,
    options.search,
    options.status,
    pageSize,
    skip,
  ]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return {
    documents,
    total,
    totalPages,
    page,
    pageSize,
    isLoading,
    error,
    refresh,
    removeDocument: deleteDocument,
    updateDocument,
    fetchDocumentBlob,
    uploadDocument,
  };
}

export function useRecentDocuments(limit = 5) {
  return useDocuments({ page: 1, pageSize: limit });
}

export function useUploadHistory(limit = 10) {
  return useDocuments({ page: 1, pageSize: limit });
}

export { useDocumentsContext };
