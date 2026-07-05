import type {
  DocumentListItemApiResponse,
  DocumentStatus,
  KnowledgeDocument,
  UploadHistoryItem,
} from "@/types/knowledge";

import { formatDocTypeLabel } from "@/lib/knowledge/constants";
import { formatFileSize } from "@/lib/knowledge/utils";

export function mapDocumentStatus(status: string): DocumentStatus {
  if (
    status === "queued" ||
    status === "indexed" ||
    status === "processing" ||
    status === "review" ||
    status === "archived" ||
    status === "failed"
  ) {
    return status;
  }

  return "processing";
}

export function mapDocumentFromApi(
  document: DocumentListItemApiResponse,
): KnowledgeDocument {
  const department =
    typeof document.metadata?.department === "string"
      ? document.metadata.department
      : "Unassigned";

  return {
    id: document.id,
    title: document.title,
    originalFilename: document.original_filename,
    docType: document.doc_type,
    type: formatDocTypeLabel(document.doc_type),
    status: mapDocumentStatus(document.status),
    version: document.version_no ? `v${document.version_no}` : "v1",
    owner: document.uploaded_by_name ?? "Unknown",
    department,
    lastUpdated: document.updated_at,
    createdAt: document.created_at,
    fileSize: formatFileSize(document.file_size_bytes),
    mimeType: document.mime_type,
    fileExtension: document.file_extension,
  };
}

export function mapUploadHistoryFromDocument(
  document: KnowledgeDocument,
): UploadHistoryItem {
  return {
    id: document.id,
    fileName: document.originalFilename ?? document.title,
    fileType: document.fileExtension ?? "",
    uploadedBy: document.owner,
    uploadedAt: document.createdAt,
    status: document.status,
    documentsCreated: 1,
  };
}

export function mapUploadHistoryFromApi(
  document: DocumentListItemApiResponse,
): UploadHistoryItem {
  return {
    id: document.id,
    fileName: document.original_filename,
    fileType: document.file_extension,
    uploadedBy: document.uploaded_by_name ?? "Unknown",
    uploadedAt: document.created_at,
    status: mapDocumentStatus(document.status),
    documentsCreated: 1,
  };
}
