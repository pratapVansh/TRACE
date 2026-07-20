"""Evidence-first utilities for hallucination-free agent responses.

Every agent must ground every claim in retrievable evidence.  This module
provides:

- ``build_evidence_appendix`` — appends a structured evidence section to
  any answer, showing per-source confidence, document names, graph nodes,
  tools used, and retrieval scores.
- ``build_missing_evidence_response`` — a structured replacement for
  ``no_evidence_response`` that returns ``Missing Evidence``,
  ``Recommended Next Steps``, ``Required Documents``, and
  ``Unknown Fields`` instead of fabricating.
"""

from typing import Any

from app.agents.framework.response import AgentResponse
from app.schemas.rag import Citation, GraphCitation


def build_evidence_appendix(
    citations: list[Citation] | None = None,
    graph_citations: list[GraphCitation] | None = None,
    tools_used: list[str] | None = None,
    confidence: float = 0.0,
    confidence_explanation: str = "",
    search_data: dict[str, Any] | None = None,
) -> str:
    """Build a markdown evidence appendix from existing citations and metadata.

    Appends a transparent ``## Evidence Sources`` section that lists every
    document, graph node, tool, and confidence score backing the answer.
    Designed to be concatenated to any agent's answer text.
    """
    sections: list[str] = ["", "---", "## Evidence Sources\n"]

    doc_sources = _collect_document_sources(citations, search_data)
    if doc_sources:
        sections.append("### Documents")
        for src in doc_sources:
            score_str = f" (score: {src['score']:.2f})" if src["score"] is not None else ""
            sections.append(f"- **{src['name']}**{score_str}")
            if src.get("excerpt"):
                sections.append(f"  > {src['excerpt'][:200]}")
        sections.append("")

    graph_sources = _collect_graph_sources(graph_citations, search_data)
    if graph_sources:
        sections.append("### Graph Nodes")
        for src in graph_sources:
            conf_str = f" (confidence: {src['confidence']:.2f})" if src["confidence"] is not None else ""
            rel = f" → {src['related_entity']}" if src.get("related_entity") else ""
            sections.append(f"- **{src['entity_name']}**{rel}{conf_str}")
        sections.append("")

    if tools_used:
        sections.append(f"### Tools Used")
        sections.append(f"- {', '.join(sorted(set(tools_used)))}")
        sections.append("")

    sections.append(f"### Overall Confidence")
    sections.append(f"**{confidence:.2f}**")
    if confidence_explanation:
        sections.append(f"*{confidence_explanation}*")
    sections.append("")

    return "\n".join(sections)


def build_missing_evidence_response(
    *,
    agent_name: str,
    question: str,
    tools_used: list[str],
    missing_evidence: list[str] | None = None,
    recommended_next_steps: list[str] | None = None,
    required_documents: list[str] | None = None,
    unknown_fields: list[str] | None = None,
) -> AgentResponse:
    """Build a structured **Missing Evidence** ``AgentResponse``.

    Never fabricates.  Returns a transparent breakdown of what was
    missing, what the user can do next, what documents would help,
    and which parts of the query could not be answered.
    """
    lines: list[str] = [
        "## No Supporting Evidence Found",
        "",
        "No supporting evidence found.",
        "",
    ]

    if missing_evidence:
        lines.append("### What Was Missing")
        for item in missing_evidence:
            lines.append(f"- {item}")
        lines.append("")

    if unknown_fields:
        lines.append("### Unknown Fields")
        for field in unknown_fields:
            lines.append(f"- {field}")
        lines.append("")

    if recommended_next_steps:
        lines.append("### Recommended Next Steps")
        for i, step in enumerate(recommended_next_steps, 1):
            lines.append(f"{i}. {step}")
        lines.append("")

    if required_documents:
        lines.append("### Required Documents")
        for doc in required_documents:
            lines.append(f"- {doc}")
        lines.append("")

    lines.append("---")
    lines.append(f"**Query:** {question}")

    return AgentResponse(
        answer="\n".join(lines),
        reasoning=(
            f"{agent_name}: zero grounded evidence retrieved — "
            "response suppressed to prevent hallucination."
        ),
        confidence=0.0,
        confidence_explanation="No supporting evidence found.",
        citations=[],
        graph_citations=[],
        tools_used=tools_used,
        agent_name=agent_name,
    )


def annotate_answer(
    answer: str,
    citations: list[Citation] | None = None,
    graph_citations: list[GraphCitation] | None = None,
    tools_used: list[str] | None = None,
    confidence: float = 0.0,
    confidence_explanation: str = "",
    search_data: dict[str, Any] | None = None,
) -> str:
    """Append the evidence appendix to an agent's answer.

    This is a convenience wrapper that every agent calls before returning
    its final ``AgentResponse`` so the answer always shows evidence
    provenance.
    """
    appendix = build_evidence_appendix(
        citations=citations,
        graph_citations=graph_citations,
        tools_used=tools_used,
        confidence=confidence,
        confidence_explanation=confidence_explanation,
        search_data=search_data,
    )
    return answer + appendix


# ── Internal helpers ───────────────────────────────────────────────

def _collect_document_sources(
    citations: list[Citation] | None,
    search_data: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()

    if citations:
        for c in citations:
            key = c.document_name or ""
            if key and key not in seen:
                seen.add(key)
                sources.append({
                    "name": c.document_name or "Unknown",
                    "score": c.score or c.similarity_score,
                    "excerpt": c.chunk_content or c.highlighted_excerpt,
                })

    if search_data:
        for doc in (search_data.get("documents") or []):
            name = doc.get("document_name") or doc.get("name", "Unknown")
            if name not in seen:
                seen.add(name)
                sources.append({
                    "name": name,
                    "score": doc.get("score") or doc.get("similarity_score"),
                    "excerpt": doc.get("content") or doc.get("chunk_content"),
                })

    return sources


def _collect_graph_sources(
    graph_citations: list[GraphCitation] | None,
    search_data: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()

    if graph_citations:
        for gc in graph_citations:
            key = f"{gc.entity_name}:{gc.relationship_type}:{gc.related_entity}"
            if key not in seen:
                seen.add(key)
                sources.append({
                    "entity_name": gc.entity_name,
                    "entity_type": gc.entity_type,
                    "relationship_type": gc.relationship_type,
                    "related_entity": gc.related_entity,
                    "confidence": gc.confidence,
                })

    if search_data:
        for inc in (search_data.get("incidents") or []):
            name = inc.get("name", "Unknown")
            rel = inc.get("type", "incident")
            key = f"{name}:{rel}"
            if key not in seen:
                seen.add(key)
                sources.append({
                    "entity_name": name,
                    "entity_type": inc.get("type"),
                    "relationship_type": rel,
                    "related_entity": None,
                    "confidence": inc.get("confidence", 0.5),
                })

    return sources
