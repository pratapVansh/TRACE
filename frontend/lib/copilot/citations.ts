/**
 * Resolving citations inside answer text.
 *
 * The backend's system prompt does not instruct the model to emit `[n]`
 * markers, so we cannot assume they exist. What we can do is resolve the two
 * things that are true by construction:
 *
 *   1. a `[n]` marker, when the model happens to echo the numbering it was
 *      shown, addresses the n-th retrieved passage;
 *   2. a literal document name in the prose names the citation carrying that
 *      document name.
 *
 * Anything we cannot resolve is left as plain text. We never guess which
 * passage supports a claim — an invented attribution is worse than none.
 */

/** Below this length a document name matches too much unrelated prose. */
const MIN_MENTION_LENGTH = 5;

/** Markers above two digits are not passage references. */
const MARKER_PATTERN = "\\[(\\d{1,2})\\]";

export type CitationSegment =
  | { kind: "text"; text: string }
  | { kind: "ref"; text: string; index: number; via: "marker" | "mention" };

export function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Split `text` into plain runs and resolved citation references.
 *
 * `documentNames` is positional: entry `i` is the document name of
 * `citations[i]`, so a returned `index` indexes straight back into the
 * citation array the caller holds.
 */
export function segmentText(
  text: string,
  documentNames: readonly string[],
): CitationSegment[] {
  if (!text) return [];

  const total = documentNames.length;
  if (total === 0) return [{ kind: "text", text }];

  const mentions = documentNames
    .map((name, index) => ({ name: (name ?? "").trim(), index }))
    .filter((entry) => entry.name.length >= MIN_MENTION_LENGTH)
    // Longest first: "Pump-Manual-v3.pdf" must win over "Pump-Manual".
    .sort((a, b) => b.name.length - a.name.length);

  const alternation = mentions.map((entry) => escapeRegExp(entry.name)).join("|");
  const pattern = alternation
    ? new RegExp(`${MARKER_PATTERN}|(${alternation})`, "gi")
    : new RegExp(MARKER_PATTERN, "g");

  const byName = new Map<string, number>();
  for (const entry of mentions) {
    // First wins, so the earliest citation owns a duplicated document name.
    if (!byName.has(entry.name.toLowerCase())) {
      byName.set(entry.name.toLowerCase(), entry.index);
    }
  }

  const segments: CitationSegment[] = [];
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    const matched = match[0];
    const markerDigits = match[1];
    const mentionText = match[2];

    let index: number | null = null;
    let via: "marker" | "mention" = "marker";

    if (markerDigits !== undefined) {
      const n = Number.parseInt(markerDigits, 10);
      // Only resolve markers that actually address a retrieved passage.
      if (n >= 1 && n <= total) index = n - 1;
    } else if (mentionText !== undefined) {
      const found = byName.get(mentionText.toLowerCase());
      if (found !== undefined) {
        index = found;
        via = "mention";
      }
    }

    // Unresolvable — leave it in the prose untouched rather than inventing a link.
    if (index === null) continue;

    if (match.index > cursor) {
      segments.push({ kind: "text", text: text.slice(cursor, match.index) });
    }
    segments.push({ kind: "ref", text: matched, index, via });
    cursor = match.index + matched.length;
  }

  if (cursor < text.length) {
    segments.push({ kind: "text", text: text.slice(cursor) });
  }

  return segments;
}

/** True when any citation reference can be resolved in the text. */
export function hasResolvableCitations(
  text: string,
  documentNames: readonly string[],
): boolean {
  return segmentText(text, documentNames).some((s) => s.kind === "ref");
}
