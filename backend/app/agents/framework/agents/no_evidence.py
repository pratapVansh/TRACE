"""Centralized zero-evidence guard for all framework agents.

When retrieval returns zero documents AND zero graph entities, agents MUST
NOT call the LLM.  This module provides:

- ``has_evidence``       — pure predicate; true if at least one piece of
                           evidence (document chunk or graph entity) was
                           retrieved.
- ``no_evidence_response`` — builds a structured ``Missing Evidence``
                           ``AgentResponse`` with sections for what was
                           missing, recommended next steps, required
                           documents, and unknown fields.

- ``annotate_answer``    — appends a transparent ``Evidence Sources``
                           appendix to any agent answer so every claim
                           is accompanied by provenance (documents,
                           graph nodes, tools, confidence scores).

Usage in every agent's ``execute()`` (immediately after the grounding
search, before any intent-handler dispatch)::

    if not has_evidence(search_result):
        return no_evidence_response(
            agent_name=self.name,
            question=question,
            tools_used=tools_used,
            missing_evidence=[...],
            recommended_next_steps=[...],
        )

And before returning the final ``AgentResponse``::

    answer = annotate_answer(
        answer,
        citations=citations,
        graph_citations=graph_citations,
        tools_used=tools_used,
        confidence=confidence,
        confidence_explanation=conf_expl,
        search_data=search_data,
    )
"""

from __future__ import annotations

from typing import Any

from app.agents.framework.response import AgentResponse
from app.agents.framework.tool import ToolResult


# ── Evidence predicates ────────────────────────────────────────────────


def has_evidence(result: ToolResult | dict | None) -> bool:
    """Return True if *result* contains at least one document or graph entity.

    Accepts:
    - ``ToolResult``  — inspects ``.data`` dict for known keys.
    - ``dict``        — inspects directly for known keys.
    - ``None``        — always False.

    Keys inspected (any non-empty list counts as evidence):
        documents, document_evidence, entities, assets,
        incidents, similar_incidents, history, graph_evidence,
        findings, records, results.
    """
    if result is None:
        return False

    data: dict[str, Any] | None
    if isinstance(result, ToolResult):
        if not result.success or result.data is None:
            return False
        data = result.data
    elif isinstance(result, dict):
        data = result
    else:
        return False

    _EVIDENCE_KEYS = (
        "documents",
        "document_evidence",
        "entities",
        "assets",
        "incidents",
        "similar_incidents",
        "history",
        "graph_evidence",
        "findings",
        "records",
        "results",
    )
    return any(bool(data.get(k)) for k in _EVIDENCE_KEYS)


def has_any_evidence(*results: ToolResult | dict | None) -> bool:
    """Return True if *any* of the supplied results contain evidence."""
    return any(has_evidence(r) for r in results)


# ── Response builder ───────────────────────────────────────────────────

_DEFAULT_MISSING: list[str] = [
    "No documents containing relevant information were found.",
    "No knowledge-graph entities matched your query.",
    "No tool returned data that could ground an answer.",
]

_DEFAULT_NEXT_STEPS: list[str] = [
    "**Upload relevant documents** (SOPs, P&IDs, maintenance records, "
    "inspection reports) to the TRACE document store so they can be "
    "indexed and retrieved.",
    "**Verify the knowledge graph** contains the equipment or entity "
    "you are querying.  Use the Graph Explorer to check whether the "
    "asset exists and is correctly named.",
    "**Rephrase your query** using the exact equipment tag, asset ID, "
    "or document title as it appears in the system.",
]

_DEFAULT_REQUIRED_DOCS: list[str] = [
    "Equipment specifications, P&IDs, and technical manuals",
    "Maintenance records and inspection reports",
    "Standard operating procedures (SOPs) for the equipment",
]

_DEFAULT_UNKNOWN: list[str] = [
    "No supporting evidence found.",
]


def no_evidence_response(
    *,
    agent_name: str,
    question: str,
    tools_used: list[str],
    suggestions: list[str] | None = None,
    missing_evidence: list[str] | None = None,
    recommended_next_steps: list[str] | None = None,
    required_documents: list[str] | None = None,
    unknown_fields: list[str] | None = None,
) -> AgentResponse:
    """Build a structured *Missing Evidence* ``AgentResponse``.

    The response always contains four sections so the user knows exactly
    what is missing and what to do next.

    Parameters
    ----------
    agent_name:
        Name of the calling agent (included for traceability).
    question:
        The original user question.
    tools_used:
        Tools invoked before the guard fired.
    suggestions:
        Deprecated — use ``recommended_next_steps`` instead.  Falls back
        to the three generic tips when nothing else is provided.
    missing_evidence:
        Specific evidence that was not found.
    recommended_next_steps:
        Actionable steps the user can take next.
    required_documents:
        Document types that would help answer the query.
    unknown_fields:
        Parts of the query the system couldn't determine.
    """
    from app.agents.framework.agents.evidence import build_missing_evidence_response

    effective_missing = missing_evidence or (
        [f"No {agent_name.lower()} evidence was found for: {question}"]
        if suggestions is None
        else [f"No evidence matched the search terms: {question}"]
    )

    effective_steps = (
        recommended_next_steps
        or _suggestions_to_steps(suggestions)
        or _DEFAULT_NEXT_STEPS
    )

    effective_docs = required_documents or _DEFAULT_REQUIRED_DOCS
    effective_unknown = unknown_fields or _DEFAULT_UNKNOWN

    return build_missing_evidence_response(
        agent_name=agent_name,
        question=question,
        tools_used=tools_used,
        missing_evidence=effective_missing,
        recommended_next_steps=effective_steps,
        required_documents=effective_docs,
        unknown_fields=effective_unknown,
    )


def annotate_answer(
    answer: str,
    citations: list | None = None,
    graph_citations: list | None = None,
    tools_used: list[str] | None = None,
    confidence: float = 0.0,
    confidence_explanation: str = "",
    search_data: dict[str, Any] | None = None,
) -> str:
    """Append a transparent ``Evidence Sources`` appendix to *answer*.

    Every agent should call this before returning its final
    ``AgentResponse`` so each claim is accompanied by provenance
    (documents, graph nodes, tools, retrieval scores).
    """
    from app.agents.framework.agents.evidence import build_evidence_appendix

    appendix = build_evidence_appendix(
        citations=citations,
        graph_citations=graph_citations,
        tools_used=tools_used,
        confidence=confidence,
        confidence_explanation=confidence_explanation,
        search_data=search_data,
    )
    return answer + appendix


def _suggestions_to_steps(suggestions: list[str] | None) -> list[str] | None:
    """Convert legacy suggestion strings to recommended-next-step format."""
    if suggestions is None:
        return None
    return list(suggestions)
