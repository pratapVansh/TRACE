import { describe, expect, it } from "vitest";

import { mapDocumentFromApi } from "@/lib/knowledge/mappers";
import { getPreviewKind, isOfficePreviewKind } from "@/lib/knowledge/preview";
import { upsertSearchHistoryEntry } from "@/lib/knowledge/search-history";
import { validateUploadFile } from "@/lib/knowledge/upload-validation";

describe("mapDocumentFromApi", () => {
  it("maps version and department metadata from API payloads", () => {
    const mapped = mapDocumentFromApi({
      id: "doc-1",
      title: "Manual",
      original_filename: "manual.pdf",
      doc_type: "manual",
      status: "queued",
      mime_type: "application/pdf",
      file_extension: "pdf",
      file_size_bytes: 2048,
      version_no: 2,
      uploaded_by: null,
      uploaded_by_name: "Engineer",
      metadata: { department: "Engineering" },
      created_at: "2026-07-05T00:00:00.000Z",
      updated_at: "2026-07-05T01:00:00.000Z",
    });

    expect(mapped.version).toBe("v2");
    expect(mapped.department).toBe("Engineering");
  });
});

describe("preview helpers", () => {
  it("identifies office documents as download-only previews", () => {
    const kind = getPreviewKind({
      mimeType:
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      fileExtension: "docx",
    });

    expect(kind).toBe("office");
    expect(isOfficePreviewKind(kind)).toBe(true);
  });
});

describe("search history", () => {
  it("promotes the latest query and removes duplicates", () => {
    const next = upsertSearchHistoryEntry(
      [{ id: "1", query: "pump seal", resultCount: 2, searchedAt: "old" }],
      { query: "Pump Seal", resultCount: 5, searchedAt: "new" },
    );

    expect(next).toHaveLength(1);
    expect(next[0]?.query).toBe("Pump Seal");
    expect(next[0]?.resultCount).toBe(5);
  });
});

describe("validateUploadFile", () => {
  it("rejects unsupported extensions", () => {
    const file = new File(["hello"], "notes.exe", { type: "application/octet-stream" });
    const result = validateUploadFile(file);

    expect(result?.type).toBe("error");
  });
});
