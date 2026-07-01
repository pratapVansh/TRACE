"use client";

import { Download, Eye, MoreHorizontal } from "lucide-react";

import { DocumentStatusBadge } from "@/components/knowledge/document-status-badge";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/dashboard/format";
import type { KnowledgeDocument } from "@/types/knowledge";

type DocumentTableProps = {
  documents: KnowledgeDocument[];
};

export function DocumentTable({ documents }: DocumentTableProps) {
  if (documents.length === 0) {
    return (
      <div className="industrial-card flex flex-col items-center justify-center p-12 text-center">
        <p className="text-sm font-medium text-white">No documents found</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Adjust your search or filters to find technical records.
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
              {[
                "Document",
                "Type",
                "Status",
                "Version",
                "Owner",
                "Department",
                "Last Updated",
                "Actions",
              ].map((header) => (
                <th
                  key={header}
                  className="px-4 py-3.5 text-xs font-medium tracking-wide text-muted-foreground uppercase first:pl-6 last:pr-6"
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
                className="border-b border-border/70 transition-industrial last:border-0 hover:bg-[var(--surface-secondary)]/40"
              >
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
                <td className="px-4 py-4 text-muted-foreground">
                  {doc.department}
                </td>
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
                    >
                      <Eye className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8 rounded-lg text-muted-foreground hover:text-white"
                      aria-label={`Download ${doc.title}`}
                    >
                      <Download className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8 rounded-lg text-muted-foreground hover:text-white"
                      aria-label={`More actions for ${doc.title}`}
                    >
                      <MoreHorizontal className="size-4" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-border px-6 py-3 text-xs text-muted-foreground">
        Showing {documents.length} document{documents.length === 1 ? "" : "s"}
      </div>
    </div>
  );
}
