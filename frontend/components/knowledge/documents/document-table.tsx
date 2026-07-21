"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { DocumentStatusBadge } from "@/components/knowledge/document-status-badge";
import { Button } from "@/components/ui/button";
import { Download, Eye, Loader2, Pencil, Trash2 } from "lucide-react";
import { formatDateTime } from "@/lib/dashboard/format";
import type { KnowledgeDocument } from "@/types/knowledge";

type DocumentTableProps = {
  documents: KnowledgeDocument[];
  showDepartment?: boolean;
  canDelete?: boolean;
  canEdit?: boolean;
  selectedIds?: Set<string>;
  onSelectionChange?: (ids: Set<string>) => void;
  onPreview?: (document: KnowledgeDocument) => void;
  onDownload?: (document: KnowledgeDocument) => void;
  onDelete?: (document: KnowledgeDocument) => void;
  onEdit?: (document: KnowledgeDocument) => void;
  deletingId?: string | null;
};

export function DocumentTable({
  documents,
  showDepartment = true,
  canDelete = false,
  canEdit = false,
  selectedIds,
  onSelectionChange,
  onPreview,
  onDownload,
  onDelete,
  onEdit,
  deletingId,
}: DocumentTableProps) {
  const selectable = onSelectionChange !== undefined;

  const allSelected = selectable && documents.length > 0
    && documents.every((d) => selectedIds?.has(d.id));

  const toggleAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      onSelectionChange!(new Set(documents.map((d) => d.id)));
    } else {
      onSelectionChange!(new Set());
    }
  };

  const toggleOne = (id: string, checked: boolean) => {
    const next = new Set(selectedIds);
    if (checked) {
      next.add(id);
    } else {
      next.delete(id);
    }
    onSelectionChange!(next);
  };

  if (documents.length === 0) {
    return (
      <div className="industrial-card flex flex-col items-center justify-center p-12 text-center">
        <p className="text-sm font-medium text-white">No documents found</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Adjust your search or filters, or upload new technical records.
        </p>
      </div>
    );
  }

  return (
    <div className="industrial-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[960px] text-left text-sm">
          <thead>
            <tr className="border-b border-border bg-[var(--surface-secondary)]/60">
              {selectable ? (
                <th className="w-10 px-2 py-3.5 first:pl-4">
                  <Checkbox
                    checked={allSelected}
                    onChange={toggleAll}
                    aria-label="Select all documents"
                  />
                </th>
              ) : null}
              <th className="px-4 py-3.5 text-xs font-medium tracking-wide text-muted-foreground uppercase first:pl-6">
                Document
              </th>
              <th className="px-4 py-3.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Type
              </th>
              <th className="px-4 py-3.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Status
              </th>
              <th className="px-4 py-3.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Version
              </th>
              <th className="px-4 py-3.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Owner
              </th>
              {showDepartment ? (
                <th className="px-4 py-3.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  Department
                </th>
              ) : null}
              <th className="px-4 py-3.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Last Updated
              </th>
              <th className="px-4 py-3.5 text-xs font-medium tracking-wide text-muted-foreground uppercase last:pr-6">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => {
              const isSelected = selectedIds?.has(doc.id) ?? false;
              return (
                <tr
                  key={doc.id}
                  className={`border-b border-border/70 transition-industrial last:border-0 hover:bg-[var(--surface-secondary)]/40 ${
                    isSelected ? "bg-[var(--accent-muted)]" : ""
                  }`}
                >
                  {selectable ? (
                    <td className="px-2 py-4 first:pl-4">
                      <Checkbox
                        checked={isSelected}
                        onChange={(e) => toggleOne(doc.id, e.target.checked)}
                        aria-label={`Select ${doc.title}`}
                      />
                    </td>
                  ) : null}
                  <td className="px-4 py-4 first:pl-6">
                    <div className="max-w-xs space-y-1">
                      <p className="font-medium text-white">{doc.title}</p>
                      <p className="text-xs text-muted-foreground">
                        {doc.assetTag ? `${doc.assetTag} · ` : ""}
                        {doc.fileSize}
                      </p>
                    </div>
                  </td>
                  <td className="px-4 py-4 text-muted-foreground">{doc.type}</td>
                  <td className="px-4 py-4">
                    <DocumentStatusBadge status={doc.status} />
                  </td>
                  <td className="px-4 py-4 font-mono text-xs text-white">
                    {doc.version}
                  </td>
                  <td className="px-4 py-4 text-muted-foreground">{doc.owner}</td>
                  {showDepartment ? (
                    <td className="px-4 py-4 text-muted-foreground">
                      {doc.department}
                    </td>
                  ) : null}
                  <td className="px-4 py-4 text-muted-foreground">
                    {formatDateTime(doc.lastUpdated)}
                  </td>
                  <td className="px-4 py-4 last:pr-6">
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 rounded-lg text-muted-foreground hover:text-white"
                        aria-label={`View ${doc.title}`}
                        onClick={() => onPreview?.(doc)}
                      >
                        <Eye className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 rounded-lg text-muted-foreground hover:text-white"
                        aria-label={`Download ${doc.title}`}
                        onClick={() => onDownload?.(doc)}
                      >
                        <Download className="size-4" />
                      </Button>
                      {canEdit ? (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-8 rounded-lg text-muted-foreground hover:text-white"
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
                          className="size-8 rounded-lg text-muted-foreground hover:text-[var(--danger)] disabled:opacity-50"
                          aria-label={`Delete ${doc.title}`}
                          disabled={deletingId === doc.id}
                          onClick={() => onDelete?.(doc)}
                        >
                          {deletingId === doc.id ? (
                            <Loader2 className="size-4 animate-spin" />
                          ) : (
                            <Trash2 className="size-4" />
                          )}
                        </Button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
