import { describe, expect, it } from "vitest";

import { groundedIn, hasGrounding, totalStatements } from "./grounding";
import type { ClassifiedStatement, EvidenceSummary } from "@/types/chat";

const summary = (f: number, h: number, u: number): EvidenceSummary => ({
  fact_count: f,
  hypothesis_count: h,
  unknown_count: u,
});

const stmt = (
  classification: ClassifiedStatement["classification"],
  evidence_refs: string[] = [],
): ClassifiedStatement => ({ text: "s", classification, evidence_refs });

describe("totalStatements", () => {
  it("sums the three counts", () => {
    expect(totalStatements(summary(12, 1, 3))).toBe(16);
  });
});

describe("hasGrounding", () => {
  it("is false when nothing was classifiable", () => {
    expect(hasGrounding(summary(0, 0, 0))).toBe(false);
  });

  it("is true when any statement was classified, including all-unsupported", () => {
    expect(hasGrounding(summary(0, 0, 2))).toBe(true);
  });
});

describe("groundedIn", () => {
  it("returns nothing when no statement is grounded", () => {
    expect(groundedIn([stmt("UNKNOWN"), stmt("HYPOTHESIS")])).toEqual([]);
  });

  it("ignores refs on hedged and unsupported statements", () => {
    expect(groundedIn([stmt("HYPOTHESIS", ["A.docx"])])).toEqual([]);
  });

  it("collapses duplicates and orders by how often each document backs a claim", () => {
    expect(
      groundedIn([
        stmt("FACT", ["SOP-001.docx"]),
        stmt("FACT", ["MAN-001.docx", "SOP-001.docx"]),
        stmt("FACT", ["SOP-001.docx"]),
      ]),
    ).toEqual(["SOP-001.docx", "MAN-001.docx"]);
  });

  it("breaks ties by name so hover text is stable between renders", () => {
    expect(
      groundedIn([stmt("FACT", ["B.docx"]), stmt("FACT", ["A.docx"])]),
    ).toEqual(["A.docx", "B.docx"]);
  });
});
