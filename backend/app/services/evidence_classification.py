"""Classify each sentence of an answer against the passages that were retrieved.

Ported from the agent framework (``agents/framework/evidence_classifier.py``)
when the framework was removed. Two behaviours were deliberately changed:

1. **Stopword filtering and coverage.** The original counted a raw
   ``set(sentence.split()) & set(citation.split())`` overlap of 3 words as
   proof. With no stopword filter, "the", "of", "and", "is" all counted, so
   almost any sentence of ordinary length matched almost any passage and
   ``FACT`` was close to a constant. Matching now runs over content tokens
   only and is gated on the *fraction* of the sentence that is covered, so a
   long sentence has to earn its support rather than accumulate it.

2. **Hedged language is never promoted to FACT.** The original checked for
   support first and only fell through to the uncertainty markers, so
   "the seal may have failed" read as FACT whenever it happened to share
   words with a passage. Hedging is the model telling us it is inferring;
   that signal outranks lexical overlap.

Thresholds were chosen by measurement, not a priori. Over 18 real answers
from this corpus, scoring each answer against its own citations (positive)
and against another answer's citations (control):

    old heuristic          58.8% FACT / 43.3% control  -> 15.5pp gap
    overlap>=3, cov>=0.40  78.8% FACT / 30.1% control  -> 48.7pp gap

``overlap>=3, coverage>=0.40`` is the peak-discrimination point of that
sweep. Note the floor: ~30% of sentences still read as FACT against evidence
they have nothing to do with. This is lexical overlap, not entailment — it
is a usable signal, not a guarantee, and the UI must not imply otherwise.
"""

from __future__ import annotations

import re

from app.schemas.evidence import ClassifiedStatement, EvidenceSummary
from app.schemas.rag import Citation

# A sentence must share at least this many content tokens with a passage...
_MIN_OVERLAP_TOKENS = 3
# ...and they must account for at least this fraction of its content tokens.
_MIN_COVERAGE = 0.40
# Below this many content tokens a sentence carries no classifiable claim
# (markdown headings, "### Findings", bare list labels).
_MIN_SENTENCE_TOKENS = 3

# Tokens start alphanumeric and may carry the punctuation found in equipment
# tags and part numbers, so "P-101", "KBL Series-C" and "6205-2RS" survive.
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-/_.]*")

# Sentence terminator followed by whitespace, without splitting decimals
# ("0.85") or common abbreviations ("e.g.", "approx.").
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[*\-#]|$)")
_ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "approx.", "no.", "fig.", "vs.")

_STOPWORDS = frozenset("""
a about above after again against all also am an and any are as at be because been
before being below between both but by can cannot could did do does doing down during
each few for from further had has have having he her here hers him his how however i
if in into is it its itself just me more most must my no nor not of off on once only
or other our ours out over own same she should so some such than that the their theirs
them then there these they this those through to too under until up very was we were
what when where which while who whom why will with would you your yours
""".split())

# Boilerplate that appears in nearly every RAG answer *and* in the passages,
# so it inflates overlap without indicating that a claim is grounded.
_BOILERPLATE = frozenset("""
document documents documentation provided contain contains containing information
source sources according based reference references section page states state stated
following include includes including note noted shown shows given available data
""".split())

_IGNORED_TOKENS = _STOPWORDS | _BOILERPLATE

# Markers that the model is inferring rather than reporting.
_HEDGE_MARKERS = (
    "possibly", "likely", "unlikely", "may ", "may.", "might", "could",
    "perhaps", "probably", "presumably", "suggests", "suggesting", "indicates",
    "indicating", "appears", "appear to", "seems", "seem to", "not sure",
    "uncertain", "unclear", "assume", "assuming", "assumption", "hypothetical",
    "hypothesis", "estimated", "estimate", "approximately", "roughly",
    "should be", "would be", "is expected", "are expected", "potential",
    "potentially",
)


def _content_tokens(text: str) -> set[str]:
    """Lowercase content tokens, minus stopwords and RAG boilerplate."""
    tokens = set()
    for raw in _TOKEN_RE.findall(text.lower()):
        token = raw.strip("._-/")
        if len(token) < 2 or token in _IGNORED_TOKENS:
            continue
        tokens.add(token)
    return tokens


def _is_hedged(sentence_lower: str) -> bool:
    return any(marker in sentence_lower for marker in _HEDGE_MARKERS)


def split_sentences(answer: str) -> list[str]:
    """Split an answer into candidate statements.

    Markdown answers are line-oriented, so lines are split first (each bullet
    or heading is its own unit) and sentence splitting runs within a line.
    """
    sentences: list[str] = []
    for line in answer.splitlines():
        stripped = line.strip().lstrip("*-+#> ").strip()
        if not stripped:
            continue
        parts = [stripped]
        for abbrev in _ABBREVIATIONS:
            parts = [p.replace(abbrev, abbrev.replace(".", "\x00")) for p in parts]
        out: list[str] = []
        for part in parts:
            out.extend(_SENTENCE_SPLIT_RE.split(part))
        sentences.extend(s.replace("\x00", ".").strip() for s in out if s.strip())
    return sentences


def classify_statements(
    answer: str,
    citations: list[Citation],
) -> list[ClassifiedStatement]:
    """Classify every claim-bearing sentence of *answer* against *citations*."""
    if not answer.strip():
        return []

    # Index each citation once, not once per sentence.
    indexed = [
        (citation.document_name, _content_tokens(
            f"{citation.chunk_content} {citation.highlighted_excerpt}"
        ))
        for citation in citations
    ]

    statements: list[ClassifiedStatement] = []
    for sentence in split_sentences(answer):
        tokens = _content_tokens(sentence)
        if len(tokens) < _MIN_SENTENCE_TOKENS:
            continue

        scored: list[tuple[float, str]] = []
        for name, cite_tokens in indexed:
            overlap = tokens & cite_tokens
            if len(overlap) < _MIN_OVERLAP_TOKENS:
                continue
            coverage = len(overlap) / len(tokens)
            if coverage >= _MIN_COVERAGE:
                scored.append((coverage, name))

        scored.sort(key=lambda item: -item[0])
        refs = list(dict.fromkeys(name for _, name in scored))[:3]

        if _is_hedged(sentence.lower()):
            classification = "HYPOTHESIS"
        elif refs:
            classification = "FACT"
        else:
            classification = "UNKNOWN"

        statements.append(
            ClassifiedStatement(
                text=sentence,
                classification=classification,
                evidence_refs=refs,
            )
        )

    return statements


def summarize_statements(
    statements: list[ClassifiedStatement],
) -> EvidenceSummary:
    """Count each classification across an answer."""
    return EvidenceSummary(
        fact_count=sum(1 for s in statements if s.classification == "FACT"),
        hypothesis_count=sum(1 for s in statements if s.classification == "HYPOTHESIS"),
        unknown_count=sum(1 for s in statements if s.classification == "UNKNOWN"),
    )


__all__ = ["classify_statements", "summarize_statements", "split_sentences"]
