"""Evaluation metrics - pure, deterministic functions.

Retrieval metrics score the ordered chunks the answer pipeline passes to the
LLM. Answer metrics score the generated text. Nothing here calls a model or a
store, except ``grounding_summary`` which reuses TRACE's own lexical grounding
classifier (itself deterministic).
"""

import math
import re
from collections.abc import Iterable, Sequence
from pathlib import PurePath

from eval.text import contains_any, contains_evidence, normalize


# ── retrieval ────────────────────────────────────────────────────────────────


def unique_in_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def doc_recall_at_k(ranked_docs: Sequence[str], expected: Sequence[str], k: int = 5) -> float | None:
    """Share of expected documents present in the top-k distinct documents."""
    if not expected:
        return None
    top = set(unique_in_order(ranked_docs)[:k])
    return sum(1 for doc in set(expected) if doc in top) / len(set(expected))


def reciprocal_rank(ranked_docs: Sequence[str], expected: Sequence[str]) -> float | None:
    """1 / rank of the first expected document; 0 when none was retrieved."""
    if not expected:
        return None
    for rank, doc in enumerate(unique_in_order(ranked_docs), start=1):
        if doc in expected:
            return 1.0 / rank
    return 0.0


def passage_recall(
    ranked_chunks: Sequence[tuple[str, str]],
    evidence: Sequence[tuple[str, str]],
    k: int | None = 5,
) -> float | None:
    """Share of evidence snippets found in the top-k chunks of the right document.

    *ranked_chunks* and *evidence* are ``(document_name, text)`` pairs. A snippet
    only counts when it appears in a chunk from the document it was taken from.
    ``k=None`` checks every chunk passed to the LLM ("evidence in context").
    """
    if not evidence:
        return None
    pool = ranked_chunks if k is None else ranked_chunks[:k]
    found = sum(
        1
        for doc, snippet in evidence
        if any(chunk_doc == doc and contains_evidence(text, snippet) for chunk_doc, text in pool)
    )
    return found / len(evidence)


def follow_up_resolved(search_query: str, targets: Sequence[str]) -> bool | None:
    """Did query understanding carry the referent into the retrieval query?"""
    if not targets:
        return None
    query = search_query.casefold()
    return any(target.casefold() in query for target in targets)


# ── answers ──────────────────────────────────────────────────────────────────

_REFUSAL_PATTERNS = [
    r"could not find (this|that|the|any)? ?information",
    r"(do|does) not (contain|include|provide|mention|specify|record)",
    r"no supporting evidence",
    r"not (mentioned|found|recorded|documented|specified|available|provided|included|stated|listed|given)"
    r" (in|within|anywhere in) (the |any of the )?(provided |uploaded |retrieved |available |supplied )?"
    r"(documents?|context|records?|sources?|excerpts?|material)",
    r"there (is|are|was|were) no (record|records|information|mention|data|details|evidence|documentation|entry)",
    r"no (record|records|information|mention|data|details|documentation|entry) (of|about|on|regarding|for|exists)",
    r"(cannot|can't|unable to|could not|couldn't) (find|locate|determine|answer|confirm|identify|provide)",
    r"(don't|do not|does not|doesn't) have (any )?(information|details|data|records?)",
    r"(isn't|is not|wasn't|was not|aren't|are not) (mentioned|recorded|documented|specified|available|provided|stated|listed)",
    r"insufficient (context|information|evidence)",
    r"no (such|matching) (record|incident|event|document|information)",
    # Premise corrections: "no internal visual findings ... were recorded".
    r"\bno\b[^.]{0,60}\b(findings|results|readings|values|details|data|records?)\b[^.]{0,40}"
    r"\b(were|was|have been|has been) (recorded|found|documented|reported|made|given)",
]
_REFUSAL = re.compile("|".join(f"(?:{p})" for p in _REFUSAL_PATTERNS))


def is_refusal(answer: str) -> bool:
    """True when the answer states the information is not in the documents."""
    return bool(_REFUSAL.search(normalize(answer)))


def fact_coverage(answer: str, facts: Sequence[dict]) -> tuple[float | None, list[bool]]:
    """Share of expected facts stated in the answer (any accepted phrasing)."""
    if not facts:
        return None, []
    text = normalize(answer)
    hits = [contains_any(text, fact["any_of"]) for fact in facts]
    return sum(hits) / len(hits), hits


def refusal_outcome(answer: str, must_refuse: bool, coverage: float | None) -> str:
    """Classify an answer's refusal behaviour.

    - ``correct_refusal``  negative item, answer refuses
    - ``missed_refusal``   negative item, answer does not refuse (likely hallucinated)
    - ``false_refusal``    answerable item, answer refuses and states no expected fact
    - ``answered``         answerable item otherwise (a refusal of one sub-part
                           alongside correct facts is not a false refusal)
    """
    refused = is_refusal(answer)
    if must_refuse:
        return "correct_refusal" if refused else "missed_refusal"
    if refused and not coverage:
        return "false_refusal"
    return "answered"


def doc_codes(filename: str) -> list[str]:
    """Names a document is referred to by in an answer: 'SOP-003', 'Equipment Register'."""
    stem = PurePath(filename).stem
    match = re.match(r"^([A-Z]{2,4}-\d{3})", stem)
    if match:
        return [match.group(1)]
    return [stem, stem.replace("_", " ")]


def cited_documents(answer: str, filenames: Iterable[str]) -> set[str]:
    """Corpus documents the answer text names (by code or spaced stem)."""
    text = normalize(answer)
    cited = set()
    for filename in filenames:
        if any(contains_any(text, [code]) for code in doc_codes(filename)):
            cited.add(filename)
    return cited


def citation_precision_recall(
    cited: set[str], expected: Sequence[str]
) -> tuple[float | None, float | None]:
    """Precision over documents the answer named; recall over expected documents."""
    if not expected:
        return None, None
    hits = len(cited & set(expected))
    precision = hits / len(cited) if cited else None
    recall = hits / len(set(expected))
    return precision, recall


def grounding_summary(answer: str, citations: list) -> dict:
    """Counts from TRACE's per-sentence grounding classifier (lexical overlap)."""
    from app.services.evidence_classification import classify_statements, summarize_statements

    statements = classify_statements(answer, citations)
    summary = summarize_statements(statements)
    total = summary.fact_count + summary.hypothesis_count + summary.unknown_count
    return {
        "grounded": summary.fact_count,
        "hedged": summary.hypothesis_count,
        "unsupported": summary.unknown_count,
        "grounded_share": (summary.fact_count / total) if total else None,
    }


# ── aggregation ──────────────────────────────────────────────────────────────


def mean(values: Iterable[float | bool | None]) -> float | None:
    present = [float(v) for v in values if v is not None]
    return sum(present) / len(present) if present else None


def percentile(values: Sequence[float], pct: float) -> float | None:
    """Linear-interpolated percentile (pct in 0..100)."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct / 100
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
