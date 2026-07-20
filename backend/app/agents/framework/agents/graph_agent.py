"""Knowledge Graph Agent — explores and explains graph-structured data."""

import logging
import uuid
from typing import Any

from app.ai.base import LLMProvider
from app.agents.framework.base import BaseAgent
from app.agents.framework.context import AgentContext
from app.agents.framework.response import AgentResponse
from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.executor import ToolExecutor
from app.agents.framework.agents.no_evidence import annotate_answer, no_evidence_response
from app.core.authorization import Permission
from app.core.authorization.permissions import get_permissions_for_role
from app.schemas.rag import GraphCitation

_NO_EVIDENCE_SUGGESTIONS = [
    "**Verify graph population**: use the Graph Explorer to confirm the "
    "entity you are looking for exists in the knowledge graph.",
    "**Upload source documents** that reference the equipment or entity — "
    "the document processor will extract entities and relationships automatically.",
    "**Check the entity name**: graph search is case-sensitive for IDs. "
    "Try the exact tag (e.g. \"P-101\", \"Pump P101\") as shown in P&IDs.",
]

logger = logging.getLogger(__name__)

_GRAPH_TASKS = [
    "graph",
    "entity",
    "relationship",
    "knowledge graph",
    "connected",
    "neighbor",
    "path",
    "shortest path",
    "statistics",
    "schema",
    "network",
    "link",
]

_RECOMMENDED_NEXT_STEPS: dict[str, str] = {
    "search": "Try `graph neighbors` on one of the entities found above to explore connections.",
    "neighbors": "Try `graph path` between two of the discovered entities to find their shortest connection.",
    "path": "Explore the entities along the path by querying their neighbors.",
    "statistics": "Dive deeper by searching for specific entity types found in the graph.",
}


class KnowledgeGraphAgent(BaseAgent):
    """Explores and answers questions about the knowledge graph.

    Capabilities:
    - search for entities by name
    - retrieve entity neighbors and relationships
    - find shortest paths between entities
    - gather graph statistics
    - natural-language explanation of graph structures
    - graph citation generation
    """

    agent_id = "knowledge_graph"
    name = "Knowledge Graph Agent"
    description = (
        "Explores the knowledge graph — finds entities, "
        "navigates relationships, discovers paths, and explains "
        "graph structures in natural language."
    )
    supported_tasks = _GRAPH_TASKS
    required_permissions: set[Permission] = {Permission.KNOWLEDGE_GRAPH}

    def __init__(
        self,
        tool_executor: ToolExecutor | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self._tool_executor = tool_executor
        self._llm = llm_provider

    async def execute(self, context: AgentContext) -> AgentResponse:
        question = context.question
        tools_used: list[str] = []

        user_permissions = get_permissions_for_role(context.user_role)
        perm_strings = {p.value for p in user_permissions}

        tool_ctx = ToolContext.from_agent_context(
            context,
            agent_name=self.name,
            execution_id=str(uuid.uuid4())[:8],
            user_permissions=perm_strings,
        )

        citations: list[GraphCitation] = []
        answer = ""
        confidence = 0.0

        intent = self._classify_intent(question)

        if intent == "statistics":
            answer, statistics_data = await self._handle_statistics(tool_ctx, tools_used)
            confidence = 0.95 if statistics_data else 0.0

        elif intent == "path":
            answer = await self._handle_path(question, tool_ctx, tools_used)
            confidence = 0.8 if answer else 0.0

        elif intent == "neighbors":
            answer, entity = await self._handle_neighbors(question, tool_ctx, tools_used)
            confidence = 0.85 if answer else 0.0
            if entity:
                citations.append(GraphCitation(
                    entity_name=entity.get("name", ""),
                    entity_type=entity.get("type", ""),
                    relationship_type="neighbor_of",
                    related_entity="",
                    confidence=0.85,
                    supporting_content=question,
                ))

        else:
            answer, entities = await self._handle_search(question, tool_ctx, tools_used)
            confidence = self._compute_confidence(entities)
            for ent in entities[:5]:
                citations.append(GraphCitation(
                    entity_name=ent.get("name", ""),
                    entity_type=ent.get("type", ""),
                    relationship_type="mentioned_in",
                    related_entity="",
                    confidence=ent.get("confidence", 0.5),
                    supporting_content=question,
                ))

        # ── Zero-evidence guard ─────────────────────────────────
        # confidence == 0.0 and empty answer means no data was found
        if not answer and confidence == 0.0:
            return no_evidence_response(
                agent_name=self.name,
                question=question,
                tools_used=tools_used,
                suggestions=_NO_EVIDENCE_SUGGESTIONS,
            )

        if not answer:
            answer = self._fallback_answer(question)

        if context.working_memory is not None:
            wm = context.working_memory
            wm.set_temp("graph_intent", intent)
            wm.set_temp("final_answer", answer)
            wm.set_temp("confidence", confidence)

        _search_dict = locals().get("search_data") or locals().get("search_results") or locals().get("report_data")
        _final_conf, _expl = self.evaluate_confidence(True, _search_dict, locals().get("answer", ""))
        confidence = _final_conf
        answer = annotate_answer(answer, graph_citations=citations, tools_used=tools_used, confidence=confidence, confidence_explanation=_expl, search_data=_search_dict)
        return AgentResponse(
            confidence_explanation=_expl,
            answer=answer,
            graph_citations=citations,
            confidence=confidence,
            tools_used=tools_used,
            agent_name=self.name,
        )

    # ── Intent Handlers ──────────────────────────────────────────

    async def _handle_search(
        self,
        question: str,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, list[dict]]:
        query = self._extract_search_query(question)
        result = await self._call_tool("graph_search", {
            "query": query,
            "limit": 10,
        }, tool_ctx, tools_used)

        if not result.success or not result.data:
            return "", []

        entities = result.data.get("entities", [])
        total = result.data.get("total", 0)

        if not entities:
            return f"I could not find any entities matching '{query}' in the knowledge graph.", []

        # Store in working memory
        for e in entities:
            tool_ctx.set_temp(f"graph_entity_{e['id']}", e)

        answer_lines = [
            f"I found **{total} entit{'y' if total == 1 else 'ies'}** matching '{query}':",
            "",
        ]
        for i, e in enumerate(entities, 1):
            aliases_str = f" (aliases: {', '.join(e['aliases'])})" if e.get("aliases") else ""
            answer_lines.append(
                f"{i}. **{e['name']}** — type: `{e['type']}`{aliases_str}"
            )

        answer_lines.append("")
        answer_lines.append(_RECOMMENDED_NEXT_STEPS["search"])

        return "\n".join(answer_lines), entities

    async def _handle_neighbors(
        self,
        question: str,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, dict | None]:
        entity_id = self._extract_entity_id(question)
        if not entity_id:
            return self._ask_for_entity_id("neighbors"), None

        result = await self._call_tool("graph_neighbors", {
            "entity_id": entity_id,
            "depth": 1,
            "limit": 20,
        }, tool_ctx, tools_used)

        if not result.success:
            return f"Could not retrieve neighbors: {result.error}", None
        if result.data is None:
            return f"Entity '{entity_id}' was not found in the knowledge graph.", None

        entity = result.data.get("entity")
        neighbors = result.data.get("neighbors", [])
        total = result.data.get("total", 0)

        if total == 0:
            return f"Entity **{entity['name']}** has no direct connections in the graph.", entity

        # Store in working memory
        tool_ctx.set_temp("graph_current_entity", entity)
        tool_ctx.set_temp("graph_traversed_neighbors", neighbors)
        for n in neighbors:
            n_ent = n["entity"]
            rel = n["relationship"]
            tool_ctx.set_temp(
                f"graph_node_{n_ent['id']}",
                {"name": n_ent["name"], "type": n_ent["type"], "via": rel["type"]},
            )

        rel_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        for n in neighbors:
            rel_type = n["relationship"]["type"]
            n_type = n["entity"]["type"]
            rel_counts[rel_type] = rel_counts.get(rel_type, 0) + 1
            type_counts[n_type] = type_counts.get(n_type, 0) + 1

        answer_lines = [
            f"**{entity['name']}** ({entity['type']}) has **{total}** direct connection(s):",
            "",
        ]

        if len(rel_counts) <= 5:
            rel_summary = ", ".join(f"`{k}` ({v})" for k, v in sorted(rel_counts.items(), key=lambda x: -x[1]))
            answer_lines.append(f"Relationships: {rel_summary}")
            answer_lines.append("")

        type_summary = ", ".join(f"`{k}` ({v})" for k, v in sorted(type_counts.items(), key=lambda x: -x[1]))
        answer_lines.append(f"Neighbor types: {type_summary}")
        answer_lines.append("")

        for i, n in enumerate(neighbors[:8], 1):
            n_ent = n["entity"]
            rel = n["relationship"]
            answer_lines.append(
                f"{i}. **{n_ent['name']}** ({n_ent['type']}) ──{rel['type']}──>"
            )

        if len(neighbors) > 8:
            answer_lines.append(f"\n... and {total - 8} more.")

        answer_lines.append("")
        answer_lines.append(_RECOMMENDED_NEXT_STEPS["neighbors"])

        return "\n".join(answer_lines), entity

    async def _handle_path(
        self,
        question: str,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> str:
        source_id = self._extract_first_id(question, "source")
        target_id = self._extract_first_id(question, "target")

        if not source_id or not target_id:
            return (
                "To find a path, I need two entity IDs.\n"
                "Try: `Find path from [ID1] to [ID2]`"
            )

        result = await self._call_tool("graph_path", {
            "source_id": source_id,
            "target_id": target_id,
            "max_depth": 6,
        }, tool_ctx, tools_used)

        if not result.success:
            return f"Path search failed: {result.error}"

        data = result.data
        if data is None or not data.get("path_found"):
            return (
                f"No path exists between the two entities "
                f"(max depth = {data.get('total_length', 6)}). "
                "They may be in disconnected subgraphs."
            )

        segments = data.get("segments", [])
        total_length = data.get("total_length", 0)

        # Store in working memory
        tool_ctx.set_temp("graph_path_segments", segments)
        visited: list[str] = []
        for s in segments:
            if s["source"]["name"] not in visited:
                visited.append(s["source"]["name"])
            if s["target"]["name"] not in visited:
                visited.append(s["target"]["name"])
        tool_ctx.set_temp("graph_visited_nodes", visited)
        tool_ctx.set_temp("graph_path_length", total_length)

        path_str = " → ".join(
            s["source"]["name"] for s in segments
        ) + " → " + segments[-1]["target"]["name"]

        answer_lines = [
            f"**Path found!** ({total_length} hop{'s' if total_length > 1 else ''})",
            "",
            f"`{path_str}`",
            "",
            "**Path details:**",
        ]
        for i, s in enumerate(segments, 1):
            answer_lines.append(
                f"{i}. {s['source']['name']} ({s['source']['type']}) "
                f"──{s['relationship']['type']}──> "
                f"{s['target']['name']} ({s['target']['type']})"
            )

        answer_lines.append("")
        answer_lines.append(_RECOMMENDED_NEXT_STEPS["path"])

        return "\n".join(answer_lines)

    async def _handle_statistics(
        self,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, dict | None]:
        result = await self._call_tool("graph_statistics", {}, tool_ctx, tools_used)

        if not result.success or not result.data:
            return "Graph statistics are not available right now.", None

        data = result.data

        entity_types = data.get("entity_types", [])
        rel_types = data.get("relationship_types", [])

        entity_type_str = ", ".join(
            f"`{t['type']}` ({t['count']})" for t in entity_types[:8]
        ) if entity_types else "N/A"

        rel_type_str = ", ".join(
            f"`{t['type']}` ({t['count']})" for t in rel_types[:8]
        ) if rel_types else "N/A"

        answer_lines = [
            "**Knowledge Graph Statistics**",
            "",
            f"- **Entities:** {data.get('total_entities', 0)}",
            f"- **Relationships:** {data.get('total_relationships', 0)}",
            f"- **Documents referenced:** {data.get('total_documents', 0)}",
            "",
            f"**Entity types:** {entity_type_str}",
            "",
            f"**Relationship types:** {rel_type_str}",
        ]

        if entity_types and len(entity_types) > 8:
            answer_lines.append(f"\n(... and {len(entity_types) - 8} more entity types)")

        answer_lines.append("")
        answer_lines.append(_RECOMMENDED_NEXT_STEPS["statistics"])

        tool_ctx.set_temp("graph_statistics", data)

        return "\n".join(answer_lines), data

    # ── Helpers ──────────────────────────────────────────────────

    async def _call_tool(
        self,
        tool_id: str,
        params: dict[str, Any],
        ctx: ToolContext,
        tools_used: list[str],
    ) -> ToolResult:
        if self._tool_executor is None:
            return ToolResult(data=None, error="Tool executor not available.")
        result = await self._tool_executor.execute(tool_id, params, ctx)
        if tool_id not in tools_used:
            tools_used.append(tool_id)
        return result

    @staticmethod
    def _classify_intent(question: str) -> str:
        q = question.lower().strip()
        if any(w in q for w in ("statistics", "stats", "how many", "count", "schema", "overview", "what kind")):
            return "statistics"
        if any(w in q for w in ("path", "route", "connection between", "how is", "related to", "link between", "shortest", "connect")):
            return "path"
        if any(w in q for w in ("neighbor", "connected to", "relations", "adjacent", "around", "linked to", "what is connected", "explore")):
            return "neighbors"
        return "search"

    @staticmethod
    def _extract_search_query(question: str) -> str:
        for prefix in ("find ", "search ", "show ", "look up ", "where is ", "what is "):
            if question.lower().startswith(prefix):
                return question[len(prefix):].strip()
        return question.strip()

    @staticmethod
    def _extract_entity_id(question: str) -> str | None:
        for prefix in ("neighbors of ", "neighbor ", "connected to ", "around ", "explore "):
            if question.lower().startswith(prefix):
                candidate = question[len(prefix):].strip()
                if candidate:
                    return candidate
        return None

    @staticmethod
    def _extract_first_id(question: str, label: str) -> str | None:
        for prefix in (f"{label} ", f"{label}:"):
            if prefix in question.lower():
                after = question.lower().split(prefix, 1)[1].strip()
                parts = after.split()
                if parts:
                    return parts[0].rstrip(",.")
        return None

    @staticmethod
    def _ask_for_entity_id(context: str) -> str:
        return (
            f"I need an entity ID to look up {context}.\n\n"
            "Try: `search pumps` to find entities first, "
            "then use the entity ID from the results."
        )

    @staticmethod
    def _compute_confidence(entities: list[dict]) -> float:
        if not entities:
            return 0.0
        scores = [e.get("confidence", 0.0) for e in entities if e.get("confidence") is not None]
        if not scores:
            return 0.4
        return min(sum(scores) / len(scores), 1.0)

    @staticmethod
    def _fallback_answer(question: str) -> str:
        return (
            "I could not find relevant information in the knowledge graph. "
            "Try one of the following:\n"
            "- `What entities are in the graph?` (statistics)\n"
            "- `Find pumps` (search by name)\n"
            "- `Neighbors of [entity ID]` (explore connections)\n"
            "- `Path from [ID1] to [ID2]` (find shortest path)"
        )
