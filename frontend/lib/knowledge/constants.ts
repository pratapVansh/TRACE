import type { DocumentStatus, SupportedFileType } from "@/types/knowledge";

export const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, string> = {
  queued: "Queued",
  indexed: "Indexed",
  processing: "Processing",
  review: "In Review",
  archived: "Archived",
  failed: "Failed",
};

export const DOCUMENT_STATUSES: DocumentStatus[] = [
  "queued",
  "indexed",
  "processing",
  "review",
  "archived",
  "failed",
];

/** Display labels used by legacy UI filters. */
export const DOCUMENT_TYPES = [
  "Engineering Drawing",
  "P&ID",
  "SOP",
  "Inspection Report",
  "OEM Manual",
  "Incident Report",
  "Maintenance Log",
  "Safety Manual",
] as const;

export const DOC_TYPE_FILTER_OPTIONS = [
  { value: "all", label: "All types" },
  { value: "manual", label: "Manual" },
  { value: "spreadsheet", label: "Spreadsheet" },
  { value: "document", label: "Document" },
  { value: "image", label: "Image" },
  { value: "unknown", label: "Unknown" },
] as const;

export const DEPARTMENTS = [
  "Operations",
  "Maintenance",
  "Engineering",
  "HSE",
  "Reliability",
  "Turnaround",
  "Unassigned",
] as const;

export const ALLOWED_UPLOAD_EXTENSIONS = [
  "pdf",
  "docx",
  "pptx",
  "xlsx",
  "txt",
  "png",
  "jpg",
  "jpeg",
] as const;

/** Matches backend `max_upload_size_mb` default (100). */
export const MAX_UPLOAD_SIZE_MB = 100;

export const MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024;

export const DEFAULT_PAGE_SIZE = 20;

const FILE_TYPE_LABELS: Record<(typeof ALLOWED_UPLOAD_EXTENSIONS)[number], string> = {
  pdf: "PDF Documents",
  docx: "Word Documents",
  pptx: "PowerPoint Presentations",
  xlsx: "Excel Spreadsheets",
  txt: "Plain Text",
  png: "PNG Images",
  jpg: "JPEG Images",
  jpeg: "JPEG Images",
};

export const SUPPORTED_FILE_TYPES: SupportedFileType[] = ALLOWED_UPLOAD_EXTENSIONS.map(
  (extension) => ({
    extension,
    label: FILE_TYPE_LABELS[extension],
  }),
);

export const ACCEPTED_FORMATS_LABEL = ALLOWED_UPLOAD_EXTENSIONS.map(
  (extension) => `.${extension}`,
).join(", ");

export const UPLOAD_ACCEPT_ATTRIBUTE = ACCEPTED_FORMATS_LABEL;

export function formatDocTypeLabel(docType: string): string {
  if (!docType || docType === "unknown") {
    return "Document";
  }

  return docType
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
