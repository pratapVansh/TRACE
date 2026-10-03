const REDUNDANT_EVIDENCE_ALERT =
  /^\s*>?\s*\[!(?:DOCUMENT|SOURCE|EVIDENCE)\](?:\s|$)/i;

const REDUNDANT_EVIDENCE_HEADING =
  /^\s*(?:#{1,6}\s*)?\*{0,2}(?:evidence|sources|documents drawn on)\*{0,2}\s*:?\s*$/i;

function isDocumentMetadata(line: string): boolean {
  const value = line.replace(/^\s*>\s?/, "").trim();
  return (
    /"document_name"\s*:/.test(value) &&
    (/^\[object Object\]\s*\{/.test(value) ||
      (/^\{/.test(value) && /"(?:confidence|score|preview)"\s*:/.test(value)))
  );
}

/**
 * Remove model-authored evidence cards from an answer.
 *
 * Retrieved citations are rendered from the API's structured citation data in
 * the Evidence panel. Model-authored DOCUMENT/SOURCE blocks duplicate that
 * data and are not trustworthy JSON; older answers can even contain the React
 * string "[object Object]". Cleaning them here also repairs saved answers when
 * they are opened again.
 */
export function cleanAnswerContent(content: string): string {
  const lines = content.split(/\r?\n/);
  const kept: string[] = [];
  let removedEvidence = false;
  let skippingQuote = false;

  for (const line of lines) {
    if (REDUNDANT_EVIDENCE_ALERT.test(line)) {
      removedEvidence = true;
      skippingQuote = true;
      continue;
    }

    if (skippingQuote) {
      if (/^\s*>/.test(line) || /^\s*$/.test(line)) continue;
      skippingQuote = false;
    }

    if (isDocumentMetadata(line)) {
      removedEvidence = true;
      continue;
    }

    kept.push(line);
  }

  const withoutLabels = removedEvidence
    ? kept.filter(
        (line) =>
          !REDUNDANT_EVIDENCE_HEADING.test(line) &&
          !/^\s*More details available\.?\s*$/i.test(line),
      )
    : kept;

  return withoutLabels.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}
