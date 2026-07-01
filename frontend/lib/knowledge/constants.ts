import type { DocumentStatus, DocumentType, Department } from "@/types/knowledge";

export const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, string> = {
  indexed: "Indexed",
  processing: "Processing",
  review: "In Review",
  archived: "Archived",
  failed: "Failed",
};

export const DOCUMENT_TYPES: DocumentType[] = [
  "Engineering Drawing",
  "P&ID",
  "SOP",
  "Inspection Report",
  "OEM Manual",
  "Incident Report",
  "Maintenance Log",
  "Safety Manual",
];

export const DEPARTMENTS: Department[] = [
  "Operations",
  "Maintenance",
  "Engineering",
  "HSE",
  "Reliability",
  "Turnaround",
];

export const DOCUMENT_STATUSES: DocumentStatus[] = [
  "indexed",
  "processing",
  "review",
  "archived",
  "failed",
];
