"use client";

import { useCallback, useId, useMemo, useRef, useState } from "react";

import { KnowledgePageHeader } from "@/components/knowledge/knowledge-page-header";
import { SupportedFileTypes } from "@/components/knowledge/upload/supported-file-types";
import { UploadDropZone } from "@/components/knowledge/upload/upload-drop-zone";
import { UploadHistory } from "@/components/knowledge/upload/upload-history";
import { UploadQueue } from "@/components/knowledge/upload/upload-queue";
import { ValidationMessages } from "@/components/knowledge/upload/validation-messages";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocumentsContext, useUploadHistory } from "@/hooks/use-documents";
import {
  MAX_UPLOAD_SIZE_MB,
  SUPPORTED_FILE_TYPES,
  UPLOAD_ACCEPT_ATTRIBUTE,
} from "@/lib/knowledge/constants";
import { mapUploadHistoryFromDocument } from "@/lib/knowledge/mappers";
import { mapUploadErrorMessage } from "@/lib/knowledge/upload-errors";
import { validateUploadFile } from "@/lib/knowledge/upload-validation";
import { formatFileSize, getFileExtension } from "@/lib/knowledge/utils";
import type { UploadQueueItem, ValidationMessage } from "@/types/knowledge";

export function UploadDocumentsPageContent() {
  const baseId = useId();
  const { uploadDocument } = useDocumentsContext();
  const { documents: recentUploads, isLoading: isHistoryLoading, error: historyError } =
    useUploadHistory(10);

  const [queue, setQueue] = useState<UploadQueueItem[]>([]);
  const [validationMessages, setValidationMessages] = useState<ValidationMessage[]>(
    [],
  );
  const pendingUploadsRef = useRef<UploadQueueItem[]>([]);
  const isProcessingRef = useRef(false);

  const history = useMemo(
    () => recentUploads.map(mapUploadHistoryFromDocument),
    [recentUploads],
  );

  const uploadOne = useCallback(
    async (item: UploadQueueItem) => {
      if (!item.file) {
        return;
      }

      setQueue((current) =>
        current.map((entry) =>
          entry.id === item.id
            ? { ...entry, status: "uploading", progress: 0, message: "Uploading…" }
            : entry,
        ),
      );

      try {
        await uploadDocument(item.file, {
          onUploadProgress: (progress) => {
            setQueue((current) =>
              current.map((entry) =>
                entry.id === item.id ? { ...entry, progress } : entry,
              ),
            );
          },
        });

        setQueue((current) =>
          current.map((entry) =>
            entry.id === item.id
              ? {
                  ...entry,
                  status: "processing",
                  progress: 100,
                  message: "Upload complete — queued for ingestion",
                }
              : entry,
          ),
        );

        window.setTimeout(() => {
          setQueue((current) =>
            current.map((entry) =>
              entry.id === item.id
                ? { ...entry, status: "complete" as const, message: "Upload complete — queued for ingestion" }
                : entry,
            ),
          );
        }, 1500);
      } catch (error) {
        setQueue((current) =>
          current.map((entry) =>
            entry.id === item.id
              ? {
                  ...entry,
                  status: "failed",
                  message: mapUploadErrorMessage(error),
                }
              : entry,
          ),
        );
      }
    },
    [uploadDocument],
  );

  const processPendingUploads = useCallback(async () => {
    if (isProcessingRef.current) {
      return;
    }

    isProcessingRef.current = true;

    try {
      while (pendingUploadsRef.current.length > 0) {
        const nextItem = pendingUploadsRef.current.shift();
        if (nextItem) {
          await uploadOne(nextItem);
        }
      }
    } finally {
      isProcessingRef.current = false;
    }
  }, [uploadOne]);

  const handleFilesSelected = useCallback(
    (files: File[]) => {
      const errors: ValidationMessage[] = [];
      const validFiles: UploadQueueItem[] = [];

      files.forEach((file, index) => {
        const error = validateUploadFile(file);
        if (error) {
          errors.push(error);
          return;
        }

        validFiles.push({
          id: `${baseId}-${Date.now()}-${index}`,
          fileName: file.name,
          fileSize: formatFileSize(file.size),
          fileType: getFileExtension(file.name),
          status: "queued",
          progress: 0,
          message: "Waiting for upload slot",
          file,
        });
      });

      setValidationMessages(errors);

      if (validFiles.length > 0) {
        pendingUploadsRef.current.push(...validFiles);
        setQueue((current) => [...validFiles, ...current]);
        void processPendingUploads();
      }
    },
    [baseId, processPendingUploads],
  );

  const queued = queue.filter((i) => i.status === "queued").length;
  const uploading = queue.filter((i) => i.status === "uploading").length;
  const completed = queue.filter((i) => i.status === "complete").length;
  const failed = queue.filter((i) => i.status === "failed").length;
  const totalFiles = queue.length;
  const overallProgress = totalFiles > 0
    ? Math.round(((completed + failed) / totalFiles) * 100)
    : 0;

  const retryUpload = useCallback(
    async (item: UploadQueueItem) => {
      pendingUploadsRef.current.push({ ...item, status: "queued", progress: 0, message: "Waiting for upload slot" });
      setQueue((current) =>
        current.map((entry) =>
          entry.id === item.id
            ? { ...entry, status: "queued", progress: 0, message: "Waiting for upload slot" }
            : entry,
        ),
      );
      void processPendingUploads();
    },
    [processPendingUploads],
  );

  const removeFromQueue = useCallback((id: string) => {
    setQueue((current) => current.filter((entry) => entry.id !== id));
  }, []);

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <KnowledgePageHeader
        sectionLabel="Knowledge Management"
        title="Upload Documents"
        description="Ingest drawings, manuals, inspection reports, and operational records into the knowledge repository."
      />

      <ValidationMessages messages={validationMessages} />

      <UploadDropZone
        onFilesSelected={handleFilesSelected}
        accept={UPLOAD_ACCEPT_ATTRIBUTE}
      />

      {totalFiles > 0 ? (
        <div className="rounded-xl border border-border bg-[var(--surface-secondary)]/60 p-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              {uploading > 0 ? (
                <span className="flex items-center gap-1.5">
                  <span className="size-2 animate-pulse rounded-full bg-[var(--accent-steel)]" />
                  Uploading {uploading} file{uploading > 1 ? "s" : ""}…
                </span>
              ) : completed > 0 ? (
                <span className="flex items-center gap-1.5 text-[var(--success)]">
                  Completed {completed} of {totalFiles}
                </span>
              ) : (
                <span>{totalFiles} file{totalFiles > 1 ? "s" : ""} in queue</span>
              )}
            </div>
            <span className="text-xs text-muted-foreground">
              {completed + failed}/{totalFiles}
            </span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--surface)]">
            <div
              className="h-full rounded-full bg-[var(--accent-steel)] transition-all duration-500"
              style={{ width: `${overallProgress}%` }}
            />
          </div>
          {failed > 0 ? (
            <p className="mt-1.5 text-xs text-[var(--danger)]">
              {failed} file{failed > 1 ? "s" : ""} failed
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="xl:col-span-7">
          <UploadQueue
            items={queue}
            onRetry={retryUpload}
            onRemove={removeFromQueue}
          />
        </div>
        <div className="xl:col-span-5">
          <SupportedFileTypes fileTypes={SUPPORTED_FILE_TYPES} />
          <p className="mt-3 text-xs text-muted-foreground">
            Maximum file size: {MAX_UPLOAD_SIZE_MB} MB per file.
          </p>
        </div>
      </div>

      {historyError ? (
        <div className="rounded-xl border border-[var(--danger)]/25 bg-[var(--danger)]/10 px-4 py-3 text-sm text-[var(--danger)]">
          {historyError}
        </div>
      ) : null}

      {isHistoryLoading ? (
        <div className="industrial-card space-y-3 p-6">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      ) : (
        <UploadHistory items={history} />
      )}
    </div>
  );
}
