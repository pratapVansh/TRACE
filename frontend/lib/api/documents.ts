import type {
  DocumentDetailApiResponse,
  DocumentListApiResponse,
  DocumentUploadApiResponse,
} from "@/types/knowledge";

import { apiClient } from "./client";

export type DocumentListParams = {
  skip?: number;
  limit?: number;
  search?: string;
  docType?: string;
  status?: string;
  department?: string;
};

export type UpdateDocumentPayload = {
  title?: string;
  docType?: string;
  status?: string;
  source?: string;
  department?: string;
};

export async function uploadDocument(
  file: File,
  options?: {
    title?: string;
    docType?: string;
    source?: string;
    onUploadProgress?: (progress: number) => void;
  },
): Promise<DocumentUploadApiResponse> {
  const formData = new FormData();
  formData.append("file", file);

  if (options?.title) {
    formData.append("title", options.title);
  }
  if (options?.docType) {
    formData.append("doc_type", options.docType);
  }
  if (options?.source) {
    formData.append("source", options.source);
  }

  const { data } = await apiClient.post<DocumentUploadApiResponse>(
    "/api/documents",
    formData,
    {
      headers: {
        "Content-Type": undefined,
      },
      onUploadProgress: (event) => {
        if (!options?.onUploadProgress || !event.total) {
          return;
        }
        const progress = Math.min(
          100,
          Math.round((event.loaded * 100) / event.total),
        );
        options.onUploadProgress(progress);
      },
    },
  );

  return data;
}

export async function listDocuments(
  params: DocumentListParams = {},
): Promise<DocumentListApiResponse> {
  const { data } = await apiClient.get<DocumentListApiResponse>("/api/documents", {
    params: {
      skip: params.skip ?? 0,
      limit: params.limit ?? 20,
      search: params.search || undefined,
      doc_type: params.docType || undefined,
      status: params.status || undefined,
      department: params.department || undefined,
    },
  });
  return data;
}

export async function updateDocument(
  documentId: string,
  payload: UpdateDocumentPayload,
): Promise<DocumentDetailApiResponse> {
  const body: Record<string, string> = {};

  if (payload.title !== undefined) {
    body.title = payload.title;
  }
  if (payload.docType !== undefined) {
    body.doc_type = payload.docType;
  }
  if (payload.status !== undefined) {
    body.status = payload.status;
  }
  if (payload.source !== undefined) {
    body.source = payload.source;
  }
  if (payload.department !== undefined) {
    body.department = payload.department;
  }

  const { data } = await apiClient.patch<DocumentDetailApiResponse>(
    `/api/documents/${documentId}`,
    body,
  );
  return data;
}

export async function downloadDocument(
  documentId: string,
  options?: { download?: boolean },
): Promise<Blob> {
  const { data } = await apiClient.get<Blob>(`/api/documents/${documentId}/download`, {
    params: {
      download: options?.download ?? false,
    },
    responseType: "blob",
  });
  return data;
}

export async function deleteDocument(documentId: string): Promise<void> {
  await apiClient.delete(`/api/documents/${documentId}`);
}

export async function bulkDeleteDocuments(
  documentIds: string[],
): Promise<{ deleted: number; errors: string[] }> {
  const { data } = await apiClient.post<{ deleted: number; errors: string[] }>(
    "/api/documents/bulk-delete",
    { document_ids: documentIds },
  );
  return data;
}
