"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  DEPARTMENTS,
  DOC_TYPE_FILTER_OPTIONS,
  DOCUMENT_STATUSES,
  DOCUMENT_STATUS_LABELS,
} from "@/lib/knowledge/constants";
import type { KnowledgeDocument } from "@/types/knowledge";

type DocumentEditDialogProps = {
  open: boolean;
  document: KnowledgeDocument | null;
  isSaving?: boolean;
  onClose: () => void;
  onSave: (values: {
    title: string;
    docType: string;
    status: KnowledgeDocument["status"];
    department: string;
  }) => Promise<void>;
};

export function DocumentEditDialog({
  open,
  document,
  isSaving = false,
  onClose,
  onSave,
}: DocumentEditDialogProps) {
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState("");
  const [status, setStatus] = useState<KnowledgeDocument["status"]>("queued");
  const [department, setDepartment] = useState("Unassigned");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!document) {
      return;
    }

    setTitle(document.title);
    setDocType(document.docType);
    setStatus(document.status);
    setDepartment(String(document.department || "Unassigned"));
    setError(null);
  }, [document]);

  if (!open || !document) {
    return null;
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    try {
      await onSave({
        title: title.trim(),
        docType,
        status,
        department,
      });
      onClose();
    } catch (saveError) {
      setError(
        saveError instanceof Error ? saveError.message : "Failed to update document.",
      );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-lg rounded-md border border-border bg-[var(--surface)] shadow-2xl">
        <form onSubmit={handleSubmit} className="space-y-5 p-3">
          <div>
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Edit document
            </p>
            <h3 className="mt-1 text-[14px] font-semibold text-foreground">{document.title}</h3>
          </div>

          <label className="block space-y-2">
            <span className="text-[12px] text-muted-foreground">Title</span>
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="h-7 w-full rounded-md border border-border bg-[var(--surface-secondary)] px-3 text-[12px] text-foreground"
              required
            />
          </label>

          <label className="block space-y-2">
            <span className="text-[12px] text-muted-foreground">Document type</span>
            <select
              value={docType}
              onChange={(event) => setDocType(event.target.value)}
              className="h-7 w-full rounded-md border border-border bg-[var(--surface-secondary)] px-3 text-[12px] text-foreground"
            >
              {DOC_TYPE_FILTER_OPTIONS.filter((option) => option.value !== "all").map(
                (option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ),
              )}
            </select>
          </label>

          <label className="block space-y-2">
            <span className="text-[12px] text-muted-foreground">Status</span>
            <select
              value={status}
              onChange={(event) =>
                setStatus(event.target.value as KnowledgeDocument["status"])
              }
              className="h-7 w-full rounded-md border border-border bg-[var(--surface-secondary)] px-3 text-[12px] text-foreground"
            >
              {DOCUMENT_STATUSES.map((value) => (
                <option key={value} value={value}>
                  {DOCUMENT_STATUS_LABELS[value]}
                </option>
              ))}
            </select>
          </label>

          <label className="block space-y-2">
            <span className="text-[12px] text-muted-foreground">Department</span>
            <select
              value={department}
              onChange={(event) => setDepartment(event.target.value)}
              className="h-7 w-full rounded-md border border-border bg-[var(--surface-secondary)] px-3 text-[12px] text-foreground"
            >
              {DEPARTMENTS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>

          {error ? <p className="text-[12px] text-[var(--danger)]">{error}</p> : null}

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={isSaving}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
