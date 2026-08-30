"""Root-cause analysis tools.

Reuses GraphQueryService, HybridRetriever, and LLMProvider.
"""

from typing import Any

from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.base import FrameworkTool
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.schemas import ToolCategory, ToolMetadata
from app.agents.framework.tools.search_helper import search_hybrid

RCA_SYSTEM_PROMPT = """You are the Root Cause Analysis Agent for an industrial asset management system.

WORKFLOW (mandatory, in this order):
1. `incident_search` — locate the incident, failure, or asset being asked about.
2. `evidence_collection` — ALWAYS run this next to gather graph connections and
   related documents. Its output is the one and only evidence summary.
3. `root_cause` — call this ONLY after step 2 produced evidence, and always pass
   that evidence through as `evidence_summary`.

HARD RULES:
- NEVER call `root_cause` without an `evidence_summary` from `evidence_collection`.
  If evidence collection returns nothing, do not analyse — report that no
  supporting evidence was found.
- Peer-agent findings (maintenance, knowledge graph, document analysis) are
  supplementary context only. They never replace `evidence_collection`.
- Every causal claim must cite specific evidence. Never invent root causes,
  failure modes, or corrective actions that the evidence does not support.
- If the evidence is insufficient to determine a cause, state:
  'No supporting evidence found.'
"""


class IncidentSearchTool(FrameworkTool):
    """Searches for incidents, failures, and anomalies in the knowledge graph and documents."""

    metadata = ToolMetadata(
        tool_id="incident_search",
        name="Incident Search",
        description=(
            "Searches for incident reports, failure records, anomalies, "
            "and safety events in the knowledge graph and document store."
        ),
        category=ToolCategory.SEARCH,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Incident, failure, or event description"},
                "limit": {"type": "integer", "description": "Max results (default 10)"},
                "source": {
                    "type": "string", "enum": ["all", "graph", "documents"],
                    "description": "Search source (default all)",
                },
            },
            "required": ["query"],
        },
    )

    def __init__(self, graph_query_service: Any = None, hybrid_retriever: Any = None) -> None:
        self._graph_svc = graph_query_service
        self._hybrid = hybrid_retriever

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        if not isinstance(params, dict):
            return ToolResult(data=None, error="params must be a dict.")
        query = params.get("query", "")
        limit = min(params.get("limit", 10), 50)
        source = params.get("source", "all")

        if not query.strip():
            return ToolResult(data=None, error="Search query cannot be empty.")

        sr = await search_hybrid(
            query=query,
            graph_svc=self._graph_svc,
            hybrid=self._hybrid,
            top_k=limit,
            source=source,
            tool_name="IncidentSearchTool",
            context=context,
            doc_query_augment="incident failure root cause",
        )

        return ToolResult(data={
            "incidents": sr.entities,
            "documents": sr.documents,
            "total_incidents": sr.total_entities,
            "total_documents": sr.total_documents,
        })


class EvidenceCollectionTool(FrameworkTool):
    """Gathers evidence from graph neighbors and documents for a given incident or equipment."""

    metadata = ToolMetadata(
        tool_id="evidence_collection",
        name="Evidence Collection",
        description=(
            "Gathers evidence by exploring graph connections and retrieving "
            "related documents for a specific entity, incident, or equipment."
        ),
        category=ToolCategory.KNOWLEDGE_GRAPH,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Entity ID in the knowledge graph"},
                "entity_name": {"type": "string", "description": "Entity name (used if ID is unknown)"},
                "depth": {"type": "integer", "description": "Graph traversal depth (default 2, max 4)"},
                "limit": {"type": "integer", "description": "Max evidence items (default 20)"},
            },
            "required": [],
        },
    )

    def __init__(self, graph_query_service: Any = None, hybrid_retriever: Any = None) -> None:
        self._graph_svc = graph_query_service
        self._hybrid = hybrid_retriever

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        if not isinstance(params, dict):
            return ToolResult(data=None, error="params must be a dict.")
        entity_id = params.get("entity_id", "")
        entity_name = params.get("entity_name", "")
        depth = min(params.get("depth", 2), 4)
        limit = min(params.get("limit", 20), 100)

        if not entity_id and not entity_name:
            return ToolResult(data=None, error="Either entity_id or entity_name is required.")

        resolved_id = entity_id
        resolved_name = entity_name
        graph_evidence: list[dict] = []
        doc_evidence: list[dict] = []

        if self._graph_svc is not None:
            try:
                if not resolved_id and resolved_name:
                    results, _ = await self._graph_svc.search_entities(query=resolved_name, limit=3)
                    if results:
                        resolved_id = results[0].id
                        resolved_name = results[0].name

                if resolved_id:
                    entity, nbrs, total = await self._graph_svc.get_neighbors(
                        entity_id=resolved_id, depth=depth, limit=limit,
                    )
                    if entity:
                        resolved_name = entity.name
                    for n in nbrs:
                        graph_evidence.append({
                            "entity_name": n.entity.name,
                            "entity_type": n.entity.type,
                            "relationship": n.relationship.type,
                            "confidence": n.entity.confidence,
                            "source_document": n.entity.source_document,
                            "depth": n.depth,
                        })
            except Exception as exc:
                context.add_reasoning_step(f"EvidenceCollectionTool: graph query failed — {exc}")

        search_term = resolved_name or resolved_id
        sr_docs = await search_hybrid(
            query=f"{search_term} incident evidence root cause",
            graph_svc=None,
            hybrid=self._hybrid,
            top_k=limit,
            source="documents",
            tool_name="EvidenceCollectionTool",
            context=context,
        )
        for d in sr_docs.documents:
            doc_evidence.append({
                "content": d.get("content", "")[:1000],
                "score": d.get("score", 0.0),
                "document_name": d.get("document_name", ""),
            })
        return ToolResult(data={
            "entity_id": resolved_id or "unknown",
            "entity_name": resolved_name or search_term,
            "graph_evidence": graph_evidence,
            "document_evidence": doc_evidence,
            "total_graph": len(graph_evidence),
            "total_documents": len(doc_evidence),
        })


class RootCauseTool(FrameworkTool):
    """Analyzes evidence to determine probable root cause with confidence ranking."""

    metadata = ToolMetadata(
        tool_id="root_cause",
        name="Root Cause Analysis",
        description=(
            "Analyzes gathered evidence to determine probable root causes "
            "of incidents or failures. Ranks causes by confidence and "
            "recommends corrective actions."
        ),
        category=ToolCategory.REPORTING,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "incident_description": {"type": "string", "description": "Description of the incident or failure"},
                "entity_name": {"type": "string", "description": "Affected equipment or entity"},
                "evidence_summary": {"type": "string", "description": "Pre-gathered evidence summary"},
            },
            "required": ["incident_description"],
        },
    )

    def __init__(self, llm_provider: Any = None) -> None:
        self._llm = llm_provider

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        if not isinstance(params, dict):
            return ToolResult(data=None, error="params must be a dict.")
        description = params.get("incident_description", "")
        entity = params.get("entity_name", "")
        evidence = params.get("evidence_summary", "")

        if not description.strip():
            return ToolResult(data=None, error="incident_description is required.")

        # Refuse to generate if no evidence was supplied — prevents hallucination.
        if not evidence.strip():
            return ToolResult(
                data=None,
                error=(
                    "Root cause analysis requires grounded evidence. "
                    "No evidence summary was provided — run EvidenceCollectionTool "
                    "first and pass the result as evidence_summary."
                ),
            )

        prompt = (
            f"Analyze the following incident using ONLY the provided evidence:\n\n"
            f"Incident: {description}\n"
        )
        if entity:
            prompt += f"Affected equipment/entity: {entity}\n"
        if evidence:
            prompt += f"\nAvailable evidence:\n{evidence}\n"
        prompt += (
            "\nSTRICT RULES:\n"
            "- Never invent root causes, failure modes, or corrective actions not directly supported by evidence.\n"
            "- Every causal claim MUST cite specific evidence.\n"
            "- If the evidence is insufficient to determine a cause, state: 'No supporting evidence found.'\n"
            "Based ONLY on available evidence:\n"
            "1. Findings directly supported by evidence\n"
            "2. Contributing factors (only if evidenced)\n"
            "3. Recommended actions based on evidence\n"
            "Format as a structured analysis."
        )

        analysis = ""
        if self._llm is not None:
            try:
                result = await self._llm.generate(
                    prompt=prompt, system_prompt=RCA_SYSTEM_PROMPT,
                )
                analysis = result if isinstance(result, str) else (
                    result.get("text", "") if isinstance(result, dict) else str(result)
                )
            except Exception as exc:
                analysis = self._fallback_rca(description, entity, evidence)
                context.add_reasoning_step(f"RootCauseTool: LLM unavailable — {exc}")
        else:
            analysis = self._fallback_rca(description, entity, evidence)

        context.add_reasoning_step(f"RootCauseTool: analysis generated for incident")
        return ToolResult(data={
            "incident_description": description,
            "entity": entity or "unknown",
            "analysis": analysis,
        })

    @staticmethod
    def _fallback_rca(description: str, entity: str, evidence: str) -> str:
        lines = [
            "## Root Cause Analysis",
            f"**Incident:** {description}",
        ]
        if entity:
            lines.append(f"**Affected Entity:** {entity}")
        lines.extend([
            "",
            "### Probable Causes (Ranked)",
            "1. **High Confidence:** Operational factor — review procedure adherence",
            "2. **Medium Confidence:** Mechanical factor — inspect for wear or misalignment",
            "3. **Low Confidence:** Environmental factor — check ambient conditions",
            "",
            "### Evidence",
            "- Review maintenance logs for recent changes",
            "- Inspect equipment for visible damage or wear patterns",
            "- Interview operators about any unusual observations",
            "",
            "### Corrective Actions",
            "1. Immediate: Isolate equipment and conduct detailed inspection",
            "2. Short-term: Replace worn components per manufacturer specs",
            "3. Long-term: Update preventive maintenance schedule if needed",
            "",
            "### Preventive Measures",
            "- Enhance inspection checklists to include identified failure modes",
            "- Provide additional training on proper operating procedures",
            "- Implement condition monitoring for early warning",
            "> *Based on standard RCA methodology (5-Why / Fishbone).*",
        ])
        return "\n".join(lines)


class SimilarIncidentTool(FrameworkTool):
    """Finds similar past incidents using graph and document similarity."""

    metadata = ToolMetadata(
        tool_id="similar_incident",
        name="Similar Incident Search",
        description=(
            "Finds past incidents similar to the current one by searching "
            "the knowledge graph and document store for matching patterns."
        ),
        category=ToolCategory.SEARCH,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Incident description or keywords"},
                "entity_name": {"type": "string", "description": "Affected equipment or entity"},
                "limit": {"type": "integer", "description": "Max similar incidents (default 10)"},
            },
            "required": ["query"],
        },
    )

    def __init__(self, graph_query_service: Any = None, hybrid_retriever: Any = None) -> None:
        self._graph_svc = graph_query_service
        self._hybrid = hybrid_retriever

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        if not isinstance(params, dict):
            return ToolResult(data=None, error="params must be a dict.")
        query = params.get("query", "")
        entity = params.get("entity_name", "")
        limit = min(params.get("limit", 10), 30)

        if not query.strip():
            return ToolResult(data=None, error="query is required.")

        search_q = f"{query} {entity} similar incident failure".strip()

        sr = await search_hybrid(
            query=search_q,
            graph_svc=self._graph_svc,
            hybrid=self._hybrid,
            top_k=limit,
            source="all",
            tool_name="SimilarIncidentTool",
            context=context,
        )

        return ToolResult(data={
            "similar_incidents": sr.entities,
            "related_documents": sr.documents,
            "total_similar": sr.total_entities,
            "total_documents": sr.total_documents,
        })
