export type DocumentStatus =
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
  | "Turnaround";

export interface KnowledgeDocument {
  id: string;
  title: string;
  type: DocumentType;
  status: DocumentStatus;
  version: string;
  owner: string;
  department: Department;
  lastUpdated: string;
  assetTag?: string;
  fileSize: string;
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
}

export interface UploadHistoryItem {
  id: string;
  fileName: string;
  fileType: string;
  uploadedBy: string;
  uploadedAt: string;
  status: "indexed" | "failed";
  documentsCreated: number;
}

export interface SupportedFileType {
  extension: string;
  label: string;
  maxSizeMb: number;
}

export interface SearchHistoryItem {
  id: string;
  query: string;
  resultCount: number;
  searchedAt: string;
}

export interface ValidationMessage {
  id: string;
  type: "error" | "warning" | "info";
  message: string;
}
