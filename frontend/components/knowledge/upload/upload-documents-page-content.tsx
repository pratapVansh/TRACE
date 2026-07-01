"use client";

import { useCallback, useId, useState } from "react";

import { KnowledgePageHeader } from "@/components/knowledge/knowledge-page-header";
import { SupportedFileTypes } from "@/components/knowledge/upload/supported-file-types";
import { UploadDropZone } from "@/components/knowledge/upload/upload-drop-zone";
import { UploadHistory } from "@/components/knowledge/upload/upload-history";
import { UploadQueue } from "@/components/knowledge/upload/upload-queue";
import { ValidationMessages } from "@/components/knowledge/upload/validation-messages";
import {
  INITIAL_UPLOAD_QUEUE,
  MAX_UPLOAD_SIZE_MB,
  SUPPORTED_FILE_TYPES,
  UPLOAD_HISTORY,
} from "@/lib/knowledge/mock-data";
import { formatFileSize, getFileExtension } from "@/lib/knowledge/utils";
import type { UploadQueueItem, ValidationMessage } from "@/types/knowledge";

function validateFile(file: File): ValidationMessage | null {
  const extension = getFileExtension(file.name);
  const supported = SUPPORTED_FILE_TYPES.find(
    (type) => type.extension === extension,
  );

  if (!supported) {
    return {
      id: `err-${file.name}-${file.lastModified}`,
      type: "error",
      message: `"${file.name}" is not supported. Accepted formats: ${SUPPORTED_FILE_TYPES.map((t) => `.${t.extension}`).join(", ")}.`,
    };
  }

  const sizeMb = file.size / (1024 * 1024);
  if (sizeMb > supported.maxSizeMb) {
    return {
      id: `size-${file.name}-${file.lastModified}`,
      type: "error",
      message: `"${file.name}" exceeds the ${supported.maxSizeMb} MB limit for .${extension} files (${formatFileSize(file.size)}).`,
    };
  }

  if (sizeMb > MAX_UPLOAD_SIZE_MB) {
    return {
      id: `max-${file.name}-${file.lastModified}`,
      type: "error",
      message: `"${file.name}" exceeds the global ${MAX_UPLOAD_SIZE_MB} MB upload limit.`,
    };
  }

  return null;
}

export function UploadDocumentsPageContent() {
  const baseId = useId();
  const [queue, setQueue] = useState<UploadQueueItem[]>(INITIAL_UPLOAD_QUEUE);
  const [validationMessages, setValidationMessages] = useState<
    ValidationMessage[]
  >([]);

  const handleFilesSelected = useCallback(
    (files: File[]) => {
      const errors: ValidationMessage[] = [];
      const validFiles: UploadQueueItem[] = [];

      files.forEach((file, index) => {
        const error = validateFile(file);
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
        });
      });

      setValidationMessages(errors);

      if (validFiles.length > 0) {
        setQueue((current) => [...validFiles, ...current]);
      }
    },
    [baseId],
  );

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <KnowledgePageHeader
        sectionLabel="Knowledge Management"
        title="Upload Documents"
        description="Ingest drawings, manuals, inspection reports, and operational records into the Northfield Refinery knowledge repository."
      />

      <ValidationMessages messages={validationMessages} />

      <UploadDropZone onFilesSelected={handleFilesSelected} />

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="xl:col-span-7">
          <UploadQueue items={queue} />
        </div>
        <div className="xl:col-span-5">
          <SupportedFileTypes fileTypes={SUPPORTED_FILE_TYPES} />
        </div>
      </div>

      <UploadHistory items={UPLOAD_HISTORY} />
    </div>
  );
}
