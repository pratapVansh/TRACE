import type { ValidationMessage } from "@/types/knowledge";

import {
  ACCEPTED_FORMATS_LABEL,
  ALLOWED_UPLOAD_EXTENSIONS,
  MAX_UPLOAD_SIZE_BYTES,
  MAX_UPLOAD_SIZE_MB,
} from "@/lib/knowledge/constants";
import { formatFileSize, getFileExtension } from "@/lib/knowledge/utils";

export function validateUploadFile(file: File): ValidationMessage | null {
  if (file.size === 0) {
    return {
      id: `empty-${file.name}-${file.lastModified}`,
      type: "error",
      message: `"${file.name}" is empty and cannot be uploaded.`,
    };
  }

  const extension = getFileExtension(file.name);
  const isAllowedExtension = ALLOWED_UPLOAD_EXTENSIONS.includes(
    extension as (typeof ALLOWED_UPLOAD_EXTENSIONS)[number],
  );

  if (!extension || !isAllowedExtension) {
    return {
      id: `err-${file.name}-${file.lastModified}`,
      type: "error",
      message: `"${file.name}" is not supported. Accepted formats: ${ACCEPTED_FORMATS_LABEL}.`,
    };
  }

  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return {
      id: `max-${file.name}-${file.lastModified}`,
      type: "error",
      message: `"${file.name}" exceeds the ${MAX_UPLOAD_SIZE_MB} MB upload limit (${formatFileSize(file.size)}).`,
    };
  }

  return null;
}
