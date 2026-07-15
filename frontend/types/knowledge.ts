export type DocumentStatus =
  | "queued"
  | "indexed"
  | "processing"
  | "review"
  | "archived"
  | "failed";

export type DocumentType =
  | "Engineering Drawing"
  | "P&ID"
  | "SOP"
  | "Inspection Report"
  | "OEM Manual"
  | "Incident Report"
  | "Maintenance Log"
  | "Safety Manual";

export type Department =
  | "Operations"
  | "Maintenance"
  | "Engineering"
  | "HSE"
  | "Reliability"
  | "Turnaround"
  | "Unassigned";

export interface KnowledgeDocument {
  id: string;
  title: string;
  /** Present for API-backed documents; mock search data may omit this. */
  originalFilename?: string;
  /** Raw backend doc_type used for filtering (manual, spreadsheet, etc.). */
  docType: string;
  type: string;
  status: DocumentStatus;
  version: string;
  owner: string;
  department: Department | string;
  lastUpdated: string;
  createdAt: string;
  assetTag?: string;
  fileSize: string;
  mimeType?: string;
  fileExtension?: string;
}

export type UploadQueueStatus = "queued" | "uploading" | "processing" | "complete" | "failed";

export interface UploadQueueItem {
  id: string;
  fileName: string;
  fileSize: string;
  fileType: string;
  status: UploadQueueStatus;
  progress: number;
  message?: string;
  file?: File;
}

export interface UploadHistoryItem {
  id: string;
  fileName: string;
  fileType: string;
  uploadedBy: string;
  uploadedAt: string;
  status: DocumentStatus;
  documentsCreated: number;
}

export interface SupportedFileType {
  extension: string;
  label: string;
}

export interface SearchHistoryItem {
  id: string;
  query: string;
  resultCount: number;
  searchedAt: string;
}

export interface SearchFilter {
  document_id?: string;
  filename?: string;
  language?: string;
  document_type?: string;
  uploaded_by?: string;
  uploaded_after?: string;
  uploaded_before?: string;
}

export interface RankingWeights {
  semantic: number;
  keyword: number;
  metadata_boost: number;
  freshness: number;
}

export interface SearchResultItem {
  score: number;
  document_id: string;
  chunk: string;
  page: number | null;
  filename: string;
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  results: SearchResultItem[];
}

export interface ValidationMessage {
  id: string;
  type: "error" | "warning" | "info";
  message: string;
}

export interface DocumentListItemApiResponse {
  id: string;
  title: string;
  original_filename: string;
  doc_type: string;
  status: string;
  mime_type: string;
  file_extension: string;
  file_size_bytes: number;
  version_no: number;
  uploaded_by: string | null;
  uploaded_by_name: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DocumentListApiResponse {
  items: DocumentListItemApiResponse[];
  total: number;
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface DocumentDetailApiResponse extends DocumentListItemApiResponse {}

export interface DocumentUploadApiResponse {
  id: string;
  title: string;
  original_filename: string;
  doc_type: string;
  status: string;
  mime_type: string;
  file_extension: string;
  file_size_bytes: number;
  uploaded_by: string | null;
  job_id: string;
  created_at: string;
  updated_at: string;
}
