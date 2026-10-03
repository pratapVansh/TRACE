import { describe, expect, it } from "vitest";

import { cleanAnswerContent } from "./answer-content";

describe("cleanAnswerContent", () => {
  it("removes model-authored document cards and their duplicate heading", () => {
    const content = [
      "## Pump 101",
      "Pump 101 supplies cooling water.",
      "",
      "**Evidence**",
      '> [!DOCUMENT] {"document_name":"Pump-Manual.pdf","confidence":0.9}',
      "> More details available.",
    ].join("\n");

    expect(cleanAnswerContent(content)).toBe(
      "## Pump 101\nPump 101 supplies cooling water.",
    );
  });

  it("removes malformed object output from legacy saved answers", () => {
    const content = [
      "The boiler must be warmed gradually.",
      "",
      "### Sources",
      "> [!EVIDENCE]",
      '> [object Object] {"document_name":"SOP-003_Boiler_Start-Up_Procedure.docx","confidence":0.9,"score":95,"preview":"Click to preview document"}',
    ].join("\n");

    expect(cleanAnswerContent(content)).toBe(
      "The boiler must be warmed gradually.",
    );
  });

  it("removes a standalone malformed document record", () => {
    const content =
      'Answer text\n\n[object Object] {"document_name":"SOP.docx","score":95}';

    expect(cleanAnswerContent(content)).toBe("Answer text");
  });

  it("preserves normal warnings and ordinary evidence prose", () => {
    const content = [
      "## Evidence-based decision",
      "Evidence in the inspection log supports the answer.",
      "",
      "> [!WARNING] Isolate the pump before maintenance.",
    ].join("\n");

    expect(cleanAnswerContent(content)).toBe(content);
  });
});
