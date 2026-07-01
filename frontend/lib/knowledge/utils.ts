import type { DocumentStatus } from "@/types/knowledge";

export function filterDocuments<
  T extends {
    title: string;
    type: string;
    status: DocumentStatus;
    department: string;
    owner: string;
    assetTag?: string;
  },
>(
  documents: T[],
  query: string,
  filters: {
    type: string;
    status: string;
    department: string;
  },
): T[] {
  const normalizedQuery = query.trim().toLowerCase();

  return documents.filter((doc) => {
    if (filters.type !== "all" && doc.type !== filters.type) return false;
    if (filters.status !== "all" && doc.status !== filters.status) return false;
    if (filters.department !== "all" && doc.department !== filters.department) {
      return false;
    }

    if (!normalizedQuery) return true;

    const haystack = [
      doc.title,
      doc.type,
      doc.department,
      doc.owner,
      doc.assetTag ?? "",
    ]
      .join(" ")
      .toLowerCase();

    return haystack.includes(normalizedQuery);
  });
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function getFileExtension(fileName: string): string {
  const parts = fileName.split(".");
  return parts.length > 1 ? (parts.pop()?.toLowerCase() ?? "") : "";
}
