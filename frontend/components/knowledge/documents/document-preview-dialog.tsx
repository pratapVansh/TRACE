"use client";

import { Download, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  getPreviewKind,
  getPreviewUnavailableMessage,
  isOfficePreviewKind,
} from "@/lib/knowledge/preview";
import type { KnowledgeDocument } from "@/types/knowledge";

type DocumentPreviewDialogProps = {
  open: boolean;
  document: KnowledgeDocument | null;
  previewUrl: string | null;
  previewText: string | null;
  isLoading: boolean;
  onClose: () => void;
  onDownload?: (document: KnowledgeDocument) => void;
};

export function DocumentPreviewDialog({
  open,
  document,
  previewUrl,
  previewText,
  isLoading,
  onClose,
  onDownload,
}: DocumentPreviewDialogProps) {
  if (!open || !document) {
    return null;
  }

  const previewKind = getPreviewKind(document);
  const showDownloadOnly =
    !isLoading && (isOfficePreviewKind(previewKind) || previewKind === "unsupported");

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-border bg-[var(--surface)] shadow-2xl"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Document preview
            </p>
            <h3 className="mt-1 text-lg font-semibold text-white">{document.title}</h3>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="size-9 rounded-lg"
            onClick={onClose}
            aria-label="Close preview"
          >
            <X className="size-4" />
          </Button>
        </div>

        <div className="flex min-h-[420px] flex-1 items-center justify-center bg-[var(--surface-secondary)] p-4">
          {isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Loading preview…
            </div>
          ) : null}

          {!isLoading && previewKind === "pdf" && previewUrl ? (
            <iframe
              src={previewUrl}
              title={document.title}
              className="h-[70vh] w-full rounded-xl border border-border bg-white"
            />
          ) : null}

          {!isLoading && previewKind === "image" && previewUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={previewUrl}
              alt={document.title}
              className="max-h-[70vh] max-w-full rounded-xl border border-border object-contain"
            />
          ) : null}

          {!isLoading && previewKind === "text" && previewText !== null ? (
            <pre className="h-[70vh] w-full overflow-auto rounded-xl border border-border bg-[var(--surface)] p-4 text-left text-sm whitespace-pre-wrap text-white">
              {previewText}
            </pre>
          ) : null}

          {showDownloadOnly ? (
            <div className="max-w-md space-y-4 text-center">
              <p className="text-sm text-muted-foreground">
                {getPreviewUnavailableMessage(document)}
              </p>
              {onDownload ? (
                <Button
                  type="button"
                  onClick={() => onDownload(document)}
                  className="rounded-xl"
                >
                  <Download className="size-4" />
                  Download file
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
