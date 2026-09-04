/**
 * Reading the backend's per-sentence grounding for one answer.
 *
 * The classifier behind these counts is lexical overlap against the cited
 * chunk — 78.8% of a grounded answer's sentences match its own citations
 * versus 30.1% against unrelated ones. That separation is real, but a ~30%
 * floor means no individual sentence can be called verified, which is why
 * the UI reports counts and never a per-sentence verdict.
 */

import type { ClassifiedStatement, EvidenceSummary } from "@/types/chat";

/** Total classifiable statements. Derived on the backend, not serialised. */
export function totalStatements(summary: EvidenceSummary): number {
  return (
    summary.fact_count + summary.hypothesis_count + summary.unknown_count
  );
}

/**
 * An answer with no classifiable statements — a refusal, or prose carrying
 * no checkable claim. Absence of claims is not a measurement, so the caller
 * renders nothing rather than a row of zeroes.
 */
export function hasGrounding(summary: EvidenceSummary): boolean {
  return totalStatements(summary) > 0;
}

/**
 * Document names backing the grounded statements, most-cited first.
 *
 * Used for the hover text, so duplicates collapse and order is stable.
 */
export function groundedIn(statements: ClassifiedStatement[]): string[] {
  const counts = new Map<string, number>();
  for (const statement of statements) {
    if (statement.classification !== "FACT") continue;
    for (const ref of statement.evidence_refs) {
      counts.set(ref, (counts.get(ref) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([name]) => name);
}
