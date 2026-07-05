"use client";

import { Upload } from "lucide-react";
import { useCallback, useState } from "react";

import { cn } from "@/lib/utils";

type UploadDropZoneProps = {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
  accept?: string;
};

export function UploadDropZone({ onFilesSelected, disabled, accept }: UploadDropZoneProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleFiles = useCallback(
    (fileList: FileList | null) => {
      if (!fileList || disabled) return;
      onFilesSelected(Array.from(fileList));
    },
    [disabled, onFilesSelected],
  );

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setIsDragging(false);
        handleFiles(event.dataTransfer.files);
      }}
      className={cn(
        "industrial-card flex flex-col items-center justify-center border-2 border-dashed p-10 text-center transition-industrial sm:p-14",
        isDragging
          ? "border-[var(--accent-steel)] bg-[var(--accent-steel)]/5"
          : "border-border",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      <div className="flex size-14 items-center justify-center rounded-xl border border-border bg-[var(--surface-secondary)] text-[var(--accent-steel-muted)]">
        <Upload className="size-6" strokeWidth={1.75} />
      </div>
      <h3 className="mt-5 text-lg font-semibold text-white">
        Drag and drop files here
      </h3>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        Drop PDFs, drawings, spreadsheets, and scanned images. Files are validated
        locally before entering the upload queue.
      </p>
      <label className="mt-6">
        <span className="inline-flex h-10 cursor-pointer items-center rounded-xl bg-[var(--accent-steel)] px-5 text-sm font-medium text-white transition-industrial hover:bg-[#6a8eb5]">
          Browse files
        </span>
        <input
          type="file"
          multiple
          accept={accept}
          disabled={disabled}
          className="sr-only"
          onChange={(event) => {
            handleFiles(event.target.files);
            event.target.value = "";
          }}
        />
      </label>
    </div>
  );
}
