"""Asset Intelligence Agent — equipment overview, relationships, risk, maintenance."""

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
from app.agents.framework.agents.no_evidence import annotate_answer, has_evidence, no_evidence_response
from app.core.authorization import Permission
from app.core.authorization.permissions import get_permissions_for_role
from app.schemas.rag import Citation

_NO_EVIDENCE_SUGGESTIONS = [
    "**Verify the asset tag**: search the Asset Explorer for the exact equipment ID "
    "(e.g. \"P-101\", \"MV-201\") as it appears in your P&IDs or CMMS.",
    "**Upload asset documentation**: P&IDs, data sheets, equipment manuals, or "
    "maintenance records so the system can index and discover the asset.",
    "**Check knowledge graph population**: new assets are added automatically "
    "when their source documents are processed. Confirm the document status is Ready.",
    "**Try a broader query**: instead of a specific tag, search by equipment type "
    "(e.g. \"centrifugal pump\") to find similar assets in the system.",
]

logger = logging.getLogger(__name__)

_ASSET_TASKS = [
    "asset", "equipment", "machine", "device", "unit",
    "overview", "connected", "relationship", "hierarchy",
    "maintenance status", "maintenance history",
    "related documents", "related sops", "risk profile",
    "equipment history", "maintenance recommendation",
    "parts", "components", "specification",
]

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "asset_overview": [
        "overview", "summary", "tell me about", "what is",
        "information", "details", "spec", "specification",
    ],
    "connected_assets": [
        "connected", "related assets", "associated", "linked",
        "other equipment", "parts of", "components",
    ],
    "equipment_relationships": [
        "relationship", "hierarchy", "parent", "child", "part of",
        "belongs to", "assembly", "subsystem",
    ],
    "maintenance_status": [
        "maintenance status", "maintenance state", "last serviced",
        "maintenance due", "service due", "overdue",
    ],
    "related_documents": [
        "related documents", "associated documents", "documentation",
        "manuals for", "drawings for", "files for",
    ],
    "related_sops": [
        "sop", "standard operating procedure", "work instruction",
        "procedure for",
    ],
    "risk_profile": [
        "risk", "risk profile", "hazard", "danger", "criticality",
        "reliability", "failure risk",
    ],
    "equipment_history": [
        "history", "past", "previous", "record", "log",
        "incident", "failure history", "breakdown",
    ],
    "maintenance_recommendations": [
        "maintenance recommendation", "how to maintain",
        "service recommendation", "care for", "maintain",
        "preventive maintenance for",
    ],
}


class AssetIntelligenceAgent(BaseAgent):
    """Provides intelligence about physical plant assets.

    Capabilities:
    - asset overview combining graph and document data
    - connected assets and equipment relationships
    - risk profile with factor analysis
    - maintenance status, history, and recommendations
    - related documents and SOP discovery

    Fallback chain (per tool):
    Graph → Document Retrieval → LLM template → Evidence-only
    """

    agent_id = "asset_intelligence"
    name = "Asset Intelligence Agent"
    description = (
        "Provides intelligence about physical plant assets — "
        "overviews, connected equipment, risk profiles, maintenance "
        "status, related documents, and recommendations."
    )
    supported_tasks = _ASSET_TASKS
    required_permissions: set[Permission] = {Permission.ASSETS_READ}

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

        intent = self._classify_intent(question)
        asset_name = self._extract_asset_name(question)
        search_results = None

        # Step 1 — Always search for grounding
        search_result = await self._call_tool("asset_search", {
            "query": asset_name or question,
            "limit": 10,
            "source": "all",
        }, tool_ctx, tools_used)

        if search_result.success and search_result.data:
            search_results = search_result.data
            assets = search_results.get("assets", [])

            if context.working_memory is not None:
                context.working_memory.set_temp("asset_search_results", assets[:5])
                context.working_memory.set_temp("asset_intent", intent)

            if not asset_name and assets:
                asset_name = assets[0].get("name", "")

        # ── Zero-evidence guard ─────────────────────────────────
        if not has_evidence(search_result):
            return no_evidence_response(
                agent_name=self.name,
                question=question,
                tools_used=tools_used,
                suggestions=_NO_EVIDENCE_SUGGESTIONS,
            )

        # Step 2 — Route to handler
        answer = ""
        citations: list[Citation] = []
        confidence = 0.0

        handler_map = {
            "asset_overview": self._handle_overview,
            "connected_assets": self._handle_connected_assets,
            "equipment_relationships": self._handle_relationships,
            "maintenance_status": self._handle_maintenance_status,
            "maintenance_recommendations": self._handle_maintenance_recommendations,
            "related_documents": self._handle_related_documents,
            "related_sops": self._handle_related_sops,
            "risk_profile": self._handle_risk_profile,
            "equipment_history": self._handle_equipment_history,
        }

        if intent in handler_map:
            answer, citations, confidence = await handler_map[intent](
                question, asset_name, search_results, tool_ctx, tools_used,
            )
        else:
            answer, citations, confidence = await self._handle_general(
                question, asset_name, search_results, tool_ctx, tools_used,
            )

        if not answer:
            answer = self._compose_fallback_answer(question, asset_name, search_results)

        wm = context.working_memory
        if wm is not None:
            wm.set_temp("asset_answer", answer)
            wm.set_temp("asset_confidence", confidence)

        _search_dict = locals().get("search_data") or locals().get("search_results") or locals().get("report_data")
        _final_conf, _expl = self.evaluate_confidence(True, _search_dict, locals().get("answer", ""))
        confidence = _final_conf
        answer = annotate_answer(answer, citations=citations, tools_used=tools_used, confidence=confidence, confidence_explanation=_expl, search_data=_search_dict)
        return AgentResponse(
            confidence_explanation=_expl,
            answer=answer,
            citations=citations,
            confidence=confidence,
            tools_used=tools_used,
            agent_name=self.name,
        )

    # ── Intent Handlers ──────────────────────────────────────────

    async def _handle_overview(
        self,
        question: str, asset_name: str,
        search_results: dict | None,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        result = await self._call_tool("asset_summary", {
            "asset_name": asset_name or question,
        }, tool_ctx, tools_used)

        if result.success and result.data:
            summary = result.data.get("summary", "")
            return summary, [], result.data.get("confidence", 0.5)

        if search_results:
            return self._compose_asset_list(search_results), [], 0.4
        return "", [], 0.0

    async def _handle_connected_assets(
        self,
        question: str, asset_name: str,
        search_results: dict | None,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        return await self._relationship_query(
            asset_name, search_results, tool_ctx, tools_used,
            title="Connected Assets",
            focus="all",
        )

    async def _handle_relationships(
        self,
        question: str, asset_name: str,
        search_results: dict | None,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        return await self._relationship_query(
            asset_name, search_results, tool_ctx, tools_used,
            title="Equipment Relationships",
            focus="hierarchy",
        )

    async def _relationship_query(
        self,
        asset_name: str, search_results: dict | None,
        tool_ctx: ToolContext, tools_used: list[str],
        title: str, focus: str,
    ) -> tuple[str, list[Citation], float]:
        aid = self._resolve_asset_id(search_results)

        result = await self._call_tool("asset_relationship", {
            "asset_id": aid or "",
            "asset_name": asset_name or "",
            "depth": 1,
            "limit": 30,
        }, tool_ctx, tools_used)

        if result.success and result.data:
            data = result.data
            rels = data.get("relationships", [])
            breakdown = data.get("relationship_breakdown", {})
            name = data.get("asset_name", asset_name or "Unknown")

            if not rels:
                return (
                    f"**{title} — {name}**\n\nNo connections found in the knowledge graph.",
                ), [], 0.3

            lines = [
                f"**{title} — {name}**",
                f"{len(rels)} connection(s) across {len(breakdown)} type(s)",
                "",
            ]
            for rel_type, count in sorted(breakdown.items(), key=lambda x: -x[1]):
                lines.append(f"- **{rel_type}** ({count})")
            lines.append("")

            for i, r in enumerate(rels[:12], 1):
                lines.append(
                    f"{i}. {r['relationship_type']} → **{r['target_name']}** ({r['target_type']})"
                )
            if len(rels) > 12:
                lines.append(f"\n... and {len(rels) - 12} more.")

            return "\n".join(lines), [], min(len(rels) / 30, 0.9)

        return self._compose_asset_list(search_results), [], 0.3

    async def _handle_maintenance_status(
        self,
        question: str, asset_name: str,
        search_results: dict | None,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        aid = self._resolve_asset_id(search_results)
        result = await self._call_tool("asset_maintenance", {
            "asset_id": aid or "",
            "asset_name": asset_name or "",
            "include_recommendations": False,
        }, tool_ctx, tools_used)

        if result.success and result.data:
            data = result.data
            records = data.get("maintenance_records", [])
            name = data.get("asset_name", asset_name or "Unknown")

            lines = [f"**Maintenance Status — {name}**", ""]
            if records:
                lines.append(f"{len(records)} maintenance record(s) found:")
                for r in records[:10]:
                    lines.append(f"- {r['relationship']}: **{r['entity_name']}**")
            else:
                lines.append("No maintenance records found in the knowledge graph.")

            lines.append("")
            if data.get("related_documents", 0) > 0:
                lines.append(f"({data['related_documents']} related document(s) available)")

            return "\n".join(lines), [], min(len(records) / 10, 0.85)

        return self._compose_asset_list(search_results), [], 0.3

    async def _handle_maintenance_recommendations(
        self,
        question: str, asset_name: str,
        search_results: dict | None,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        aid = self._resolve_asset_id(search_results)
        result = await self._call_tool("asset_maintenance", {
            "asset_id": aid or "",
            "asset_name": asset_name or "",
            "include_recommendations": True,
        }, tool_ctx, tools_used)

        if result.success and result.data:
            data = result.data
            recs = data.get("recommendations", "")
            name = data.get("asset_name", asset_name or "Unknown")

            if recs:
                return recs, [], 0.75

            return (
                f"Could not generate maintenance recommendations for '{name}'."
            ), [], 0.3

        return self._compose_asset_list(search_results), [], 0.3

    async def _handle_related_documents(
        self,
        question: str, asset_name: str,
        search_results: dict | None,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        if search_results and search_results.get("documents"):
            docs = search_results["documents"]
            lines = [
                f"**Related Documents — {asset_name or 'Search Results'}**",
                f"{len(docs)} document(s) found",
                "",
            ]
            citations = []
            for i, d in enumerate(docs[:8], 1):
                lines.append(f"{i}. **{d['document_name']}** (score: {d.get('score', 0.0):.2f})")
                content = d.get("content", "")[:200]
                if content:
                    lines.append(f"   _{content}..._")
                citations.append(Citation(
                    document_name=d.get("document_name", "Unknown"),
                    chunk_content=content or "Related document",
                    score=d.get("score", 0.5),
                    similarity_score=d.get("score", 0.5),
                ))
            if len(docs) > 8:
                lines.append(f"\n... and {len(docs) - 8} more.")
            return "\n".join(lines), citations, self._compute_confidence(search_results)

        result = await self._call_tool("asset_search", {
            "query": asset_name or question,
            "source": "documents",
            "limit": 10,
        }, tool_ctx, tools_used)

        if result.success and result.data and result.data.get("documents"):
            return await self._handle_related_documents(
                question, asset_name, result.data, tool_ctx, tools_used,
            )

        return f"No documents found for '{asset_name or 'your query'}'." + (
            " Try uploading relevant documentation."
        ), [], 0.0

    async def _handle_related_sops(
        self,
        question: str, asset_name: str,
        search_results: dict | None,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        sop_result = await self._call_tool("asset_search", {
            "query": f"SOP {asset_name or question} procedure",
            "source": "documents",
            "limit": 10,
        }, tool_ctx, tools_used)

        if sop_result.success and sop_result.data:
            docs = sop_result.data.get("documents", [])
            sop_docs = [
                d for d in docs
                if "sop" in d.get("document_name", "").lower()
                or "procedure" in d.get("document_name", "").lower()
                or "sop" in d.get("content", "").lower()[:200]
            ]
            if sop_docs:
                lines = [
                    f"**Related SOPs — {asset_name or 'Search Results'}**",
                    f"{len(sop_docs)} SOP(s) found",
                    "",
                ]
                for i, d in enumerate(sop_docs[:8], 1):
                    lines.append(f"{i}. **{d['document_name']}** (score: {d.get('score', 0.0):.2f})")
                return "\n".join(lines), [], 0.8

            if docs:
                lines = [
                    f"**Related Documents — {asset_name or 'Search Results'}**",
                    "No specific SOPs found, but these documents may help:",
                    "",
                ]
                for i, d in enumerate(docs[:5], 1):
                    lines.append(f"{i}. **{d['document_name']}** (score: {d.get('score', 0.0):.2f})")
                return "\n".join(lines), [], 0.5

        return (
            f"No SOPs found for '{asset_name or 'your query'}'. "
            "Ensure SOPs are uploaded with appropriate naming."
        ), [], 0.0

    async def _handle_risk_profile(
        self,
        question: str, asset_name: str,
        search_results: dict | None,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        aid = self._resolve_asset_id(search_results)
        result = await self._call_tool("asset_risk", {
            "asset_id": aid or "",
            "asset_name": asset_name or "",
        }, tool_ctx, tools_used)

        if result.success and result.data:
            data = result.data
            lines = [
                f"## Risk Profile — {data['asset_name']}",
                "",
                f"**Risk Score:** {data['risk_score']:.0%}",
                f"**Risk Level:** {data['risk_level']}",
                "",
            ]
            if data.get("findings"):
                lines.append("### Risk Factors")
                for f_data in data["findings"]:
                    lines.append(f"- **[{f_data['severity'].upper()}]** {f_data['detail']}")
                lines.append("")
            if data.get("analysis"):
                lines.append("### Analysis")
                lines.append(data["analysis"])

            return "\n".join(lines), [], 1.0 - data.get("risk_score", 0.5)

        return self._compose_asset_list(search_results), [], 0.3

    async def _handle_equipment_history(
        self,
        question: str, asset_name: str,
        search_results: dict | None,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        aid = self._resolve_asset_id(search_results)
        result = await self._call_tool("asset_maintenance", {
            "asset_id": aid or "",
            "asset_name": asset_name or "",
            "include_recommendations": False,
        }, tool_ctx, tools_used)

        if result.success and result.data:
            data = result.data
            records = data.get("maintenance_records", [])
            name = data.get("asset_name", asset_name or "Unknown")

            if records:
                lines = [
                    f"**Equipment History — {name}**",
                    f"{len(records)} record(s) found",
                    "",
                ]
                for i, r in enumerate(records[:12], 1):
                    lines.append(f"{i}. {r['relationship']}: **{r['entity_name']}** ({r['entity_type']})")
                citations = [
                    Citation(
                        document_name=r.get("source_document", "Asset Record"),
                        chunk_content=f"{r['relationship']}: {r['entity_name']}",
                        score=r.get("confidence", 0.5),
                        similarity_score=r.get("confidence", 0.5),
                    )
                    for r in records[:5] if r.get("source_document")
                ]
                return "\n".join(lines), citations, min(len(records) / 15, 0.85)

            return (
                f"No history records found for '{name}' in the knowledge graph."
            ), [], 0.3

        return self._compose_asset_list(search_results), [], 0.3

    async def _handle_general(
        self,
        question: str, asset_name: str,
        search_results: dict | None,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        return await self._handle_overview(
            question, asset_name, search_results, tool_ctx, tools_used,
        )

    # ── Helpers ──────────────────────────────────────────────────

    async def _call_tool(
        self, tool_id: str, params: dict[str, Any],
        ctx: ToolContext, tools_used: list[str],
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
        scored: list[tuple[str, int]] = []
        for intent, keywords in _INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in q)
            if score > 0:
                scored.append((intent, score))
        if not scored:
            return "general"
        scored.sort(key=lambda x: -x[1])
        return scored[0][0]

    @staticmethod
    def _extract_asset_name(question: str) -> str:
        q = question.lower().strip()
        for prefix in (
            "for ", "on ", "of ", "about ", "regarding ",
            "the ", "show ", "find ", "tell me about ",
        ):
            if q.startswith(prefix):
                rest = q[len(prefix):].strip()
                words = rest.split()
                if words:
                    candidate = words[0].strip(",.!?")
                    if candidate and len(candidate) > 1 and not candidate.startswith("asset"):
                        return candidate
        for word in q.split():
            clean = word.strip(",.!?")
            if clean and (clean[0].isupper() or any(
                t in clean.lower() for t in [
                    "pump", "valve", "motor", "tank", "pipe", "compressor",
                    "conveyor", "fan", "filter", "boiler", "generator",
                    "turbine", "separator", "vessel", "column", "reactor",
                    "furnace", "cooler", "exchanger", "chiller", "dryer",
                    "mill", "crusher", "sieve", "screen", "cyclone",
                ]
            )):
                return clean
        return ""

    @staticmethod
    def _resolve_asset_id(search_results: dict | None) -> str:
        if search_results:
            assets = search_results.get("assets", [])
            if assets:
                return assets[0].get("id", "")
        return ""

    @staticmethod
    def _compose_asset_list(search_results: dict) -> str:
        if not search_results:
            return "No assets found."
        assets = search_results.get("assets", [])
        docs = search_results.get("documents", [])
        lines: list[str] = []
        if assets:
            lines.append(f"**Assets Found ({len(assets)}):**")
            for i, a in enumerate(assets[:10], 1):
                lines.append(f"{i}. **{a['name']}** — type: `{a['type']}`")
            if len(assets) > 10:
                lines.append(f"... and {len(assets) - 10} more.")
        if docs:
            if assets:
                lines.append("")
            lines.append(f"**Related Documents ({len(docs)}):**")
            for i, d in enumerate(docs[:5], 1):
                lines.append(f"{i}. **{d['document_name']}** (score: {d.get('score', 0.0):.2f})")
        if not assets and not docs:
            lines.append("No assets or documents found.")
        return "\n".join(lines)

    @staticmethod
    def _compute_confidence(search_results: dict | None) -> float:
        if not search_results:
            return 0.0
        docs = search_results.get("documents", [])
        scores = [d.get("score", 0.0) for d in docs if d.get("score") is not None]
        if scores:
            return min(sum(scores) / len(scores), 1.0)
        return 0.4 if search_results.get("assets") else 0.0

    @staticmethod
    def _compose_fallback_answer(question: str, asset_name: str, search_results: dict | None) -> str:
        lines = [
            "I encountered some issues processing your request.",
            "",
        ]
        if search_results:
            assets = search_results.get("assets", [])
            docs = search_results.get("documents", [])
            if assets:
                lines.append(f"**Assets Found ({len(assets)}):**")
                for a in assets[:5]:
                    lines.append(f"- **{a['name']}** ({a['type']})")
            if docs:
                if assets:
                    lines.append("")
                lines.append(f"**Related Documents ({len(docs)}):**")
                for d in docs[:3]:
                    lines.append(f"- {d['document_name']}")
        if not search_results or (not search_results.get("assets") and not search_results.get("documents")):
            lines.append(
                "Try one of the following:\n"
                "- `Show me pump P-101`\n"
                "- `What assets are connected to motor M-101?`\n"
                "- `Risk profile for compressor C-201`\n"
                "- `Maintenance status of valve V-101`\n"
                "- `Related documents for heat exchanger HX-301`\n"
                "- `SOPs for centrifugal pump`"
            )
        return "\n".join(lines)
