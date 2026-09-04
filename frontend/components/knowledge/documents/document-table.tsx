"use client";

import { Download, Eye, Pencil, Trash2 } from "lucide-react";

import { DocumentStatusBadge } from "@/components/knowledge/document-status-badge";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/dashboard/format";
import type { KnowledgeDocument } from "@/types/knowledge";

type DocumentTableProps = {
  documents: KnowledgeDocument[];
  showDepartment?: boolean;
  canDelete?: boolean;
  canEdit?: boolean;
  onPreview?: (document: KnowledgeDocument) => void;
  onDownload?: (document: KnowledgeDocument) => void;
  onDelete?: (document: KnowledgeDocument) => void;
  onEdit?: (document: KnowledgeDocument) => void;
};

const TABLE_HEADERS = [
  "Document",
  "Type",
  "Status",
  "Version",
  "Owner",
  "Department",
  "Last Updated",
  "Actions",
] as const;

export function DocumentTable({
  documents,
  showDepartment = true,
  canDelete = false,
  canEdit = false,
  onPreview,
  onDownload,
  onDelete,
  onEdit,
}: DocumentTableProps) {
  const visibleHeaders = TABLE_HEADERS.filter(
    (header) => showDepartment || header !== "Department",
  );

  if (documents.length === 0) {
    return (
      <div className="industrial-card flex flex-col items-start px-3 py-4">
        <p className="text-[12px] font-medium text-foreground">No documents found</p>
        <p className="mt-1 text-[12px] text-muted-foreground">
          Adjust your search or filters, or upload new technical records.
        </p>
      </div>
    );
  }

  return (
    <div className="industrial-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="data-grid min-w-[900px]">
          <thead>
            <tr className="bg-[var(--surface-secondary)]/60">
              {visibleHeaders.map((header) => (
                <th
                  key={header}
                  className="first:pl-3 last:pr-3"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr
                key={doc.id}
                className="last:[&>td]:border-0"
              >
                <td className="first:pl-3">
                  <div className="max-w-[280px]">
                    <p className="font-medium text-foreground">{doc.title}</p>
                    <p className="truncate text-[11px] text-muted-foreground">
                      {doc.assetTag ? `${doc.assetTag} · ` : ""}
                      {doc.fileSize}
                    </p>
                  </div>
                </td>
                <td className="text-muted-foreground">{doc.type}</td>
                <td >
                  <DocumentStatusBadge status={doc.status} />
                </td>
                <td className="font-mono text-[11px] text-foreground">
                  {doc.version}
                </td>
                <td className="text-muted-foreground">{doc.owner}</td>
                {showDepartment ? (
                  <td className="text-muted-foreground">
                    {doc.department}
                  </td>
                ) : null}
                <td className="text-muted-foreground">
                  {formatDateTime(doc.lastUpdated)}
                </td>
                <td className="last:pr-3">
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8 rounded-lg text-muted-foreground hover:text-foreground"
                      aria-label={`View ${doc.title}`}
                      onClick={() => onPreview?.(doc)}
                    >
                      <Eye className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8 rounded-lg text-muted-foreground hover:text-foreground"
                      aria-label={`Download ${doc.title}`}
                      onClick={() => onDownload?.(doc)}
                    >
                      <Download className="size-4" />
                    </Button>
                    {canEdit ? (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 rounded-lg text-muted-foreground hover:text-foreground"
                        aria-label={`Edit ${doc.title}`}
                        onClick={() => onEdit?.(doc)}
                      >
                        <Pencil className="size-4" />
                      </Button>
                    ) : null}
                    {canDelete ? (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 rounded-lg text-muted-foreground hover:text-[var(--danger)]"
                        aria-label={`Delete ${doc.title}`}
                        onClick={() => onDelete?.(doc)}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
