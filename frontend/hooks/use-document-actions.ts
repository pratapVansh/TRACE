"use client";

import { useCallback, useState } from "react";

import { useDocumentsContext } from "@/contexts/documents-context";
import {
  createPreviewObjectUrl,
  getPreviewKind,
  isOfficePreviewKind,
  revokePreviewObjectUrl,
  resolvePreviewMimeType,
} from "@/lib/knowledge/preview";
import type { KnowledgeDocument } from "@/types/knowledge";

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function useDocumentActions() {
  const { deleteDocument, fetchDocument, fetchDocumentBlob } = useDocumentsContext();
  const [actionError, setActionError] = useState<string | null>(null);
  const [previewDocument, setPreviewDocument] = useState<KnowledgeDocument | null>(
    null,
  );
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);

  const closePreview = useCallback(() => {
    revokePreviewObjectUrl(previewUrl);
    setPreviewUrl(null);
    setPreviewText(null);
    setPreviewDocument(null);
  }, [previewUrl]);

  const handlePreview = useCallback(
    async (document: KnowledgeDocument) => {
      setActionError(null);
      setPreviewDocument(document);
      setPreviewText(null);
      setPreviewUrl((currentUrl) => {
        revokePreviewObjectUrl(currentUrl);
        return null;
      });

      const previewKind = getPreviewKind(document);
      if (isOfficePreviewKind(previewKind)) {
        setIsPreviewLoading(false);
        return;
      }

      if (previewKind === "unsupported") {
        setIsPreviewLoading(false);
        return;
      }

      setIsPreviewLoading(true);

      try {
        const blob = await fetchDocumentBlob(document.id, false);
        const mimeType = resolvePreviewMimeType(document);

        if (previewKind === "text") {
          setPreviewText(await blob.text());
          return;
        }

        setPreviewUrl(createPreviewObjectUrl(blob, mimeType));
      } catch (previewError) {
        setActionError(
          previewError instanceof Error
            ? previewError.message
            : "Failed to preview document.",
        );
        closePreview();
      } finally {
        setIsPreviewLoading(false);
      }
    },
    [closePreview, fetchDocumentBlob],
  );

  /**
   * Open the preview for a document known only by id — the case for a Copilot
   * citation, which carries `document_id` but not the document record.
   */
  const handlePreviewById = useCallback(
    async (documentId: string) => {
      setActionError(null);
      setIsPreviewLoading(true);
      try {
        await handlePreview(await fetchDocument(documentId));
      } catch (lookupError) {
        setIsPreviewLoading(false);
        setActionError(
          lookupError instanceof Error
            ? lookupError.message
            : "Failed to open the source document.",
        );
      }
    },
    [fetchDocument, handlePreview],
  );

  const handleDownload = useCallback(
    async (document: KnowledgeDocument) => {
      setActionError(null);

      try {
        const blob = await fetchDocumentBlob(document.id, true);
        triggerBlobDownload(blob, document.originalFilename ?? document.title);
      } catch (downloadError) {
        setActionError(
          downloadError instanceof Error
            ? downloadError.message
            : "Failed to download document.",
        );
      }
    },
    [fetchDocumentBlob],
  );

  const handleDelete = useCallback(
    async (document: KnowledgeDocument) => {
      if (
        !window.confirm(
          `Delete "${document.title}"? This removes the document from the repository.`,
        )
      ) {
        return;
      }

      setActionError(null);

      try {
        await deleteDocument(document.id);
      } catch (deleteError) {
        setActionError(
          deleteError instanceof Error
            ? deleteError.message
            : "Failed to delete document.",
        );
        throw deleteError;
      }
    },
    [deleteDocument],
  );

  return {
    actionError,
    setActionError,
    previewDocument,
    previewUrl,
    previewText,
    isPreviewLoading,
    closePreview,
    handlePreview,
    handlePreviewById,
    handleDownload,
    handleDelete,
  };
}
