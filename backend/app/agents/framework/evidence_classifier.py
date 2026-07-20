from __future__ import annotations

import logging
import re
from typing import Any

from app.agents.framework.response import (
    AgentResponse,
    ClassifiedStatement,
    EvidenceSummary,
)
from app.schemas.rag import Citation

logger = logging.getLogger(__name__)

# Patterns that indicate hallucination-prone content the LLM should never generate
_FORBIDDEN_TOPICS: list[str] = [
    "maintenance history",
    "part number",
    "spare inventory",
    "failure cause",
    "schedule",
]


def has_retrieved_evidence(search_data: dict[str, Any] | None) -> bool:
    """Check whether any evidence was retrieved from the data source.

    Returns True if at least one evidence-bearing key is non-empty.
    """
    if not search_data:
        return False
    evidence_keys = [
        "documents", "document_evidence", "entities", "assets",
        "incidents", "similar_incidents", "history", "graph_evidence",
        "findings", "records", "results", "related_documents",
        "relationships", "citations",
    ]
    for key in evidence_keys:
        val = search_data.get(key)
        if val and (isinstance(val, list) and len(val) > 0):
            return True
        if val and isinstance(val, str) and val.strip():
            return True
    return False


def classify_statements(
    answer: str,
    citations: list[Citation],
) -> list[ClassifiedStatement]:
    """Split the answer into sentences and classify each against evidence.

    Uses a simple heuristic:
    - If the sentence directly matches terms in citation content -> FACT
    - If the sentence uses uncertainty language -> HYPOTHESIS
    - Otherwise -> UNKNOWN
    """
    if not answer.strip():
        return []

    citation_texts = _build_citation_text_index(citations)
    sentences = _split_sentences(answer)
    statements: list[ClassifiedStatement] = []

    for sentence in sentences:
        cleaned = sentence.strip()
        if not cleaned or len(cleaned) < 10:
            continue

        classification, refs = _classify_sentence(cleaned, citation_texts)
        statements.append(
            ClassifiedStatement(
                text=cleaned,
                classification=classification,
                evidence_refs=refs,
            )
        )

    return statements


def build_evidence_summary(
    answer: str,
    citations: list[Citation],
    search_data: dict[str, Any] | None = None,
) -> EvidenceSummary:
    """Build an evidence summary for the response."""
    has_evidence = has_retrieved_evidence(search_data) or len(citations) > 0

    summary = EvidenceSummary(
        has_supporting_evidence=has_evidence,
        top_citation_count=min(len(citations), 3),
    )

    if not has_evidence:
        summary.missing_evidence_statement = (
            "No supporting evidence found."
        )

    return summary


def limit_citations(citations: list[Citation], max_count: int = 3) -> list[Citation]:
    """Rank citations by score and return only the top *max_count*."""
    sorted_cits = sorted(
        citations,
        key=lambda c: max(c.score, c.similarity_score),
        reverse=True,
    )
    return sorted_cits[:max_count]


def contains_forbidden_content(answer: str) -> bool:
    """Check if the answer appears to invent content on forbidden topics.

    Returns True if the answer makes unsupported claims about maintenance
    history, part numbers, spare inventory, failure causes, or schedules
    without citing evidence.
    """
    ans_lower = answer.lower()
    # These patterns suggest specific invented detail
    suspicious_patterns = [
        r"part\s*(#|number|no|num)\s*[:\-]?\s*\w{2,}",  # "Part #ABC-123"
        r"spare.*(stock|inventory|available|on.?hand)",
        r"scheduled\s+(for|on|date)",
        r"maintenance\s+(history|log|record).*(shows|indicates|reveals)",
        r"root\s+cause\s+(is|was|identified|determined)\s",
        r"failure\s+(mode|mechanism|cause)\s+(is|was):",
    ]
    for pattern in suspicious_patterns:
        if re.search(pattern, ans_lower):
            logger.warning(
                "Forbidden content pattern detected in answer: %r",
                pattern,
            )
            return True
    return False


# ── Internal helpers ─────────────────────────────────────────────


def _build_citation_text_index(citations: list[Citation]) -> list[str]:
    """Build a flat list of all citation text for matching."""
    texts: list[str] = []
    for c in citations:
        if c.chunk_content:
            texts.append(c.chunk_content.lower())
        if c.highlighted_excerpt:
            texts.append(c.highlighted_excerpt.lower())
    return texts


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences, handling common abbreviations."""
    text = re.sub(r"(?<=[.!?])\s+", "\n", text)
    return [s.strip() for s in text.split("\n") if s.strip()]


def _classify_sentence(
    sentence: str,
    citation_texts: list[str],
) -> tuple[str, list[str]]:
    """Classify a single sentence against available citation text."""
    sent_lower = sentence.lower()

    # Check for explicit uncertainty markers
    uncertainty_markers = [
        "possibly", "likely", "may", "might", "could", "perhaps",
        "suggests", "indicates", "appears", "seems", "probably",
        "not sure", "uncertain", "unclear", "assume", "assumption",
        "hypothetical", "estimated",
    ]
    is_uncertain = any(m in sent_lower for m in uncertainty_markers)

    # Check for evidence support
    supporting_refs: list[str] = []
    for text in citation_texts:
        words = set(sent_lower.split())
        citation_words = set(text.split())
        overlap = words & citation_words
        if len(overlap) >= 3:
            supporting_refs.append(text[:60])

    if supporting_refs:
        return "FACT", supporting_refs[:2]
    elif is_uncertain:
        return "HYPOTHESIS", []
    else:
        return "UNKNOWN", []
