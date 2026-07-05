import type { KnowledgeDocument } from "@/types/knowledge";

export type PreviewKind = "pdf" | "image" | "text" | "office" | "unsupported";

const OFFICE_EXTENSIONS = new Set(["docx", "pptx", "xlsx"]);
const IMAGE_EXTENSIONS = new Set(["png", "jpg", "jpeg"]);

const EXTENSION_MIME_TYPES: Record<string, string> = {
  pdf: "application/pdf",
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  txt: "text/plain",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
};

export function getPreviewKind(
  document: Pick<KnowledgeDocument, "mimeType" | "fileExtension">,
): PreviewKind {
  const mime = document.mimeType?.toLowerCase() ?? "";
  const extension = document.fileExtension?.toLowerCase() ?? "";

  if (mime === "application/pdf" || extension === "pdf") {
    return "pdf";
  }

  if (mime.startsWith("image/") || IMAGE_EXTENSIONS.has(extension)) {
    return "image";
  }

  if (mime === "text/plain" || extension === "txt") {
    return "text";
  }

  if (
    OFFICE_EXTENSIONS.has(extension) ||
    mime.includes("wordprocessingml") ||
    mime.includes("presentationml") ||
    mime.includes("spreadsheetml")
  ) {
    return "office";
  }

  return "unsupported";
}

export function isOfficePreviewKind(kind: PreviewKind): boolean {
  return kind === "office";
}

export function getPreviewUnavailableMessage(
  document: Pick<KnowledgeDocument, "fileExtension">,
): string {
  const extension = document.fileExtension?.toLowerCase();

  if (extension && OFFICE_EXTENSIONS.has(extension)) {
    return `.${extension.toUpperCase()} files cannot be previewed in the browser. Download the file to open it in Word, PowerPoint, or Excel.`;
  }

  return "Inline preview is not available for this file type. Use the download action to open it locally.";
}

export function resolvePreviewMimeType(
  document: Pick<KnowledgeDocument, "mimeType" | "fileExtension">,
): string {
  if (document.mimeType) {
    return document.mimeType;
  }

  const extension = document.fileExtension?.toLowerCase() ?? "";
  return EXTENSION_MIME_TYPES[extension] ?? "application/octet-stream";
}

export function createPreviewObjectUrl(blob: Blob, mimeType: string): string {
  const typedBlob =
    blob.type === mimeType ? blob : new Blob([blob], { type: mimeType });
  return URL.createObjectURL(typedBlob);
}

export function revokePreviewObjectUrl(url: string | null): void {
  if (url) {
    URL.revokeObjectURL(url);
  }
}
