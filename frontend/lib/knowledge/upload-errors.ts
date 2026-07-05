import { isAxiosError } from "axios";

import { MAX_UPLOAD_SIZE_MB } from "@/lib/knowledge/constants";

const BACKEND_UPLOAD_ERRORS: Record<string, string> = {
  "Uploaded file is empty": "The selected file is empty and cannot be uploaded.",
  "Unsupported file type":
    "This file is not supported. Check the extension is allowed and that the file content matches its type (for example, a valid PDF or image).",
  "File exceeds the maximum upload size": `This file exceeds the ${MAX_UPLOAD_SIZE_MB} MB upload limit.`,
  "A document with the same content already exists":
    "This file has already been uploaded. Remove the existing copy first, or upload a different file.",
  "Failed to store uploaded file":
    "The file could not be saved. Please try again or contact an administrator.",
};

export function mapUploadErrorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;

    if (typeof detail === "string") {
      const mapped = BACKEND_UPLOAD_ERRORS[detail];
      if (mapped) {
        return mapped;
      }
      return detail;
    }

    if (Array.isArray(detail)) {
      const firstMessage = detail.find(
        (entry) =>
          typeof entry === "object" &&
          entry !== null &&
          "msg" in entry &&
          typeof (entry as { msg: unknown }).msg === "string",
      ) as { msg: string } | undefined;

      if (firstMessage?.msg) {
        return firstMessage.msg;
      }
    }

    if (status === 413) {
      return `This file exceeds the ${MAX_UPLOAD_SIZE_MB} MB upload limit.`;
    }

    if (status === 409) {
      return BACKEND_UPLOAD_ERRORS[
        "A document with the same content already exists"
      ];
    }

    if (status === 403) {
      return "You do not have permission to upload documents.";
    }

    if (status === 401) {
      return "Your session has expired. Please sign in and try again.";
    }
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Upload failed. Please try again.";
}
