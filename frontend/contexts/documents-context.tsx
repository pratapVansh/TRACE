"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { useAuth } from "@/hooks/use-auth";
import { usePermissions } from "@/hooks/use-permissions";
import {
  deleteDocument as deleteDocumentRequest,
  downloadDocument,
  listDocuments,
  updateDocument as updateDocumentRequest,
  uploadDocument as uploadDocumentRequest,
  bulkDeleteDocuments as bulkDeleteDocumentsRequest,
  type DocumentListParams,
  type UpdateDocumentPayload,
} from "@/lib/api/documents";
import { mapDocumentFromApi } from "@/lib/knowledge/mappers";
import { PERMISSIONS } from "@/types/permissions";
import type {
  DocumentListApiResponse,
  DocumentUploadApiResponse,
  KnowledgeDocument,
} from "@/types/knowledge";

type UploadDocumentOptions = {
  title?: string;
  docType?: string;
  source?: string;
  onUploadProgress?: (progress: number) => void;
};

type DocumentsContextValue = {
  fetchDocuments: (params?: DocumentListParams) => Promise<{
    documents: KnowledgeDocument[];
    total: number;
    page: number;
    pageSize: number;
    totalPages: number;
    hasNext: boolean;
    hasPrevious: boolean;
  }>;
  uploadDocument: (
    file: File,
    options?: UploadDocumentOptions,
  ) => Promise<DocumentUploadApiResponse>;
  updateDocument: (
    documentId: string,
    payload: UpdateDocumentPayload,
  ) => Promise<KnowledgeDocument>;
  deleteDocument: (documentId: string) => Promise<void>;
  bulkDeleteDocuments: (documentIds: string[]) => Promise<{ deleted: number; errors: string[] }>;
  fetchDocumentBlob: (documentId: string, download?: boolean) => Promise<Blob>;
  queryVersion: number;
  invalidateQueries: () => void;
};

const DocumentsContext = createContext<DocumentsContextValue | undefined>(undefined);

export function DocumentsProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const { canAccess } = usePermissions();
  const canReadDocuments = canAccess(PERMISSIONS.DOCUMENTS_READ);
  const [queryVersion, setQueryVersion] = useState(0);

  const invalidateQueries = useCallback(() => {
    setQueryVersion((current) => current + 1);
  }, []);

  const fetchDocuments = useCallback(
    async (params: DocumentListParams = {}) => {
      if (!isAuthenticated || !canReadDocuments) {
        return { documents: [], total: 0, page: 0, pageSize: 0, totalPages: 0, hasNext: false, hasPrevious: false };
      }

      const response: DocumentListApiResponse = await listDocuments(params);
      return {
        documents: response.items.map(mapDocumentFromApi),
        total: response.total,
        page: response.page,
        pageSize: response.page_size,
        totalPages: response.total_pages,
        hasNext: response.has_next,
        hasPrevious: response.has_previous,
      };
    },
    [canReadDocuments, isAuthenticated],
  );

  const uploadDocument = useCallback(
    async (file: File, options?: UploadDocumentOptions) => {
      const response = await uploadDocumentRequest(file, options);
      invalidateQueries();
      return response;
    },
    [invalidateQueries],
  );

  const updateDocument = useCallback(
    async (documentId: string, payload: UpdateDocumentPayload) => {
      const response = await updateDocumentRequest(documentId, payload);
      invalidateQueries();
      return mapDocumentFromApi(response);
    },
    [invalidateQueries],
  );

  const deleteDocument = useCallback(
    async (documentId: string) => {
      await deleteDocumentRequest(documentId);
      invalidateQueries();
    },
    [invalidateQueries],
  );

  const bulkDeleteDocuments = useCallback(
    async (documentIds: string[]) => {
      const result = await bulkDeleteDocumentsRequest(documentIds);
      invalidateQueries();
      return result;
    },
    [invalidateQueries],
  );

  const fetchDocumentBlob = useCallback(
    async (documentId: string, download = false) => {
      return downloadDocument(documentId, { download });
    },
    [],
  );

  const value = useMemo(
    () => ({
      fetchDocuments,
      uploadDocument,
      updateDocument,
      deleteDocument,
      bulkDeleteDocuments,
      fetchDocumentBlob,
      queryVersion,
      invalidateQueries,
    }),
    [
      bulkDeleteDocuments,
      deleteDocument,
      fetchDocumentBlob,
      fetchDocuments,
      invalidateQueries,
      queryVersion,
      updateDocument,
      uploadDocument,
    ],
  );

  return (
    <DocumentsContext.Provider value={value}>{children}</DocumentsContext.Provider>
  );
}

export function useDocumentsContext(): DocumentsContextValue {
  const context = useContext(DocumentsContext);
  if (!context) {
    throw new Error("useDocumentsContext must be used within a DocumentsProvider");
  }
  return context;
}
