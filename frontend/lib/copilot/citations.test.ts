import { describe, expect, it } from "vitest";

import { escapeRegExp, hasResolvableCitations, segmentText } from "./citations";

const DOCS = ["Pump-Manual-v3.pdf", "Maintenance-Log-2024.xlsx"];

describe("escapeRegExp", () => {
  it("neutralises regex metacharacters in document names", () => {
    expect(escapeRegExp("Report (final) [v2].pdf")).toBe(
      "Report \\(final\\) \\[v2\\]\\.pdf",
    );
  });
});

describe("segmentText", () => {
  it("returns nothing for empty text", () => {
    expect(segmentText("", DOCS)).toEqual([]);
  });

  it("passes text through untouched when there are no citations", () => {
    expect(segmentText("No sources here.", [])).toEqual([
      { kind: "text", text: "No sources here." },
    ]);
  });

  it("resolves a numeric marker to the matching passage", () => {
    expect(segmentText("Seal wear was noted [2].", DOCS)).toEqual([
      { kind: "text", text: "Seal wear was noted " },
      { kind: "ref", text: "[2]", index: 1, via: "marker" },
      { kind: "text", text: "." },
    ]);
  });

  it("leaves out-of-range markers as plain text", () => {
    // Only two passages were retrieved, so [7] addresses nothing.
    expect(segmentText("See [7].", DOCS)).toEqual([
      { kind: "text", text: "See [7]." },
    ]);
  });

  it("resolves a literal document name mentioned in the prose", () => {
    const segments = segmentText("Per Pump-Manual-v3.pdf, torque is 40 Nm.", DOCS);
    expect(segments).toEqual([
      { kind: "text", text: "Per " },
      { kind: "ref", text: "Pump-Manual-v3.pdf", index: 0, via: "mention" },
      { kind: "text", text: ", torque is 40 Nm." },
    ]);
  });

  it("matches document names case-insensitively", () => {
    const segments = segmentText("see pump-manual-v3.PDF", DOCS);
    expect(segments[1]).toMatchObject({ kind: "ref", index: 0, via: "mention" });
  });

  it("prefers the longest name when one is a prefix of another", () => {
    const docs = ["Pump-Manual", "Pump-Manual-v3.pdf"];
    const segments = segmentText("From Pump-Manual-v3.pdf here", docs);
    expect(segments[1]).toMatchObject({
      text: "Pump-Manual-v3.pdf",
      index: 1,
      via: "mention",
    });
  });

  it("ignores names too short to match reliably", () => {
    expect(segmentText("a b c", ["a.p"])).toEqual([{ kind: "text", text: "a b c" }]);
  });

  it("handles regex metacharacters in document names", () => {
    const docs = ["Report (final).pdf"];
    const segments = segmentText("See Report (final).pdf now", docs);
    expect(segments[1]).toMatchObject({ index: 0, via: "mention" });
  });

  it("resolves markers and mentions together, in order", () => {
    const segments = segmentText(
      "[1] confirms it; Maintenance-Log-2024.xlsx disagrees.",
      DOCS,
    );
    expect(segments.filter((s) => s.kind === "ref")).toEqual([
      { kind: "ref", text: "[1]", index: 0, via: "marker" },
      {
        kind: "ref",
        text: "Maintenance-Log-2024.xlsx",
        index: 1,
        via: "mention",
      },
    ]);
  });

  it("assigns a duplicated document name to its earliest citation", () => {
    const docs = ["Same-Doc.pdf", "Same-Doc.pdf"];
    const segments = segmentText("In Same-Doc.pdf", docs);
    expect(segments[1]).toMatchObject({ index: 0 });
  });

  it("reconstructs the original text exactly", () => {
    const input = "[1] and Pump-Manual-v3.pdf and [9] tail";
    const joined = segmentText(input, DOCS)
      .map((s) => s.text)
      .join("");
    expect(joined).toBe(input);
  });
});

describe("hasResolvableCitations", () => {
  it("is true when a reference resolves", () => {
    expect(hasResolvableCitations("see [1]", DOCS)).toBe(true);
  });

  it("is false when nothing resolves", () => {
    expect(hasResolvableCitations("see [9]", DOCS)).toBe(false);
  });
});
