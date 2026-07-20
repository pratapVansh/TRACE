"""Maintenance Agent — preventive, corrective, inspection, and risk workflows."""

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
    "**Upload maintenance documentation**: SOPs, work instructions, lubrication "
    "schedules, or inspection checklists for the equipment you are asking about.",
    "**Ensure the asset exists in the knowledge graph** — use the Asset Explorer "
    "to verify the equipment tag is present and correctly named.",
    "**Rephrase using the exact equipment tag** (e.g. \"Pump P-101 preventive "
    "maintenance\") as it appears in your maintenance management system.",
    "**Check document processing status** — recently uploaded files may still "
    "be indexing.  Retry after a few minutes.",
]

logger = logging.getLogger(__name__)

_MAINTENANCE_TASKS = [
    "maintenance",
    "preventive",
    "corrective",
    "inspection",
    "shutdown",
    "startup",
    "history",
    "spare",
    "parts",
    "ppe",
    "tools",
    "risk",
    "schedule",
    "lubrication",
    "overhaul",
    "repair",
    "procedure",
    "checklist",
]

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "history": ["history", "past", "previous", "when was", "last serviced", "maintenance log", "record"],
    "spare_parts": ["spare", "part", "replacement part", "stock", "inventory"],
    "ppe": ["ppe", "personal protective", "safety gear", "protection", "helmet", "gloves", "goggles", "harness"],
    "tools": ["tool", "wrench", "socket", "instrument", "equipment needed"],
    "risk_assessment": ["risk", "hazard", "danger", "safe", "assessment", "mitigation", "control measure"],
    "scheduling": ["schedule", "interval", "frequency", "when should", "how often", "due"],
    "inspection": ["inspect", "check", "examine", "look at", "verify", "test"],
    "shutdown": ["shutdown", "shut down", "turn off", "de-energize", "isolate", "lockout", "loto"],
    "startup": ["startup", "start up", "turn on", "energize", "restart", "power on"],
    "corrective": ["corrective", "repair", "fix", "broken", "fault", "failure", "malfunction", "replace"],
    "preventive": ["preventive", "preventative", "routine", "regular", "scheduled", "periodic"],
}

_MAINTENANCE_PROCEDURE_TYPES = ["preventive", "corrective", "inspection", "shutdown", "startup"]


class MaintenanceAgent(BaseAgent):
    """Handles all maintenance-related queries.

    Capabilities:
    - preventive / corrective / inspection / shutdown / startup procedures
    - maintenance history retrieval
    - spare part, tool, and PPE recommendations
    - risk assessment with mitigation suggestions
    - scheduling guidance

    Fallback chain (per tool):
    Graph → Document Retrieval → LLM template → Evidence-only
    """

    agent_id = "maintenance"
    name = "Maintenance Agent"
    description = (
        "Handles preventive maintenance, corrective repairs, inspection "
        "procedures, shutdown/startup sequences, maintenance history, "
        "spare part recommendations, required PPE and tools, "
        "risk assessment, and maintenance scheduling."
    )
    supported_tasks = _MAINTENANCE_TASKS
    required_permissions: set[Permission] = {Permission.MAINTENANCE}

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
        search_results = None

        # Step 1 — Always search for grounding context
        search_result = await self._call_tool("maintenance_search", {
            "query": question,
            "top_k": 10,
            "source": "all",
        }, tool_ctx, tools_used)

        if search_result.success and search_result.data:
            search_results = search_result.data
            docs = search_results.get("documents", [])
            entities = search_results.get("entities", [])

            if context.working_memory is not None:
                context.working_memory.set_temp("maintenance_search_docs", docs[:5])
                context.working_memory.set_temp("maintenance_search_entities", entities[:5])
                context.working_memory.set_temp("maintenance_intent", intent)

        # ── Zero-evidence guard ─────────────────────────────────
        if not has_evidence(search_result):
            return no_evidence_response(
                agent_name=self.name,
                question=question,
                tools_used=tools_used,
                suggestions=_NO_EVIDENCE_SUGGESTIONS,
            )

        # Step 2 — Route to intent handler
        answer = ""
        citations: list[Citation] = []
        confidence = 0.0

        handler_map = {
            "history": self._handle_history,
            "spare_parts": self._handle_recommendation,
            "ppe": self._handle_recommendation,
            "tools": self._handle_recommendation,
            "risk_assessment": self._handle_risk,
            "scheduling": self._handle_scheduling,
        }

        if intent in handler_map:
            answer, citations, confidence = await handler_map[intent](
                question, search_results, tool_ctx, tools_used,
            )
        elif intent in _MAINTENANCE_PROCEDURE_TYPES:
            answer, citations, confidence = await self._handle_procedure(
                intent, question, search_results, tool_ctx, tools_used,
            )
        else:
            answer, citations, confidence = await self._handle_general(
                question, search_results, tool_ctx, tools_used,
            )

        if not answer:
            answer = self._compose_fallback_answer(question, search_results)

        wm = context.working_memory
        if wm is not None:
            wm.set_temp("maintenance_answer", answer)
            wm.set_temp("maintenance_confidence", confidence)

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

    async def _handle_history(
        self,
        question: str,
        search_results: dict | None,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        equipment = self._extract_equipment(question)

        if not equipment:
            q = question.lower()
            if "history" in q or "past" in q or "previous" in q:
                return self._compose_answer_with_docs(
                    "I found maintenance-related documents that may contain history records.",
                    search_results, "history",
                ), [], 0.6

        result = await self._call_tool("maintenance_history", {
            "equipment_name": equipment or question,
            "limit": 10,
        }, tool_ctx, tools_used)

        if result.success and result.data and result.data.get("history"):
            history = result.data["history"]
            name = result.data.get("equipment_name", equipment)
            citations = self._build_citations(history)

            lines = [
                f"**Maintenance History — {name}**",
                "",
            ]
            if not history:
                lines.append("No maintenance records found for this equipment.")
            else:
                for i, h in enumerate(history[:10], 1):
                    lines.append(
                        f"{i}. **{h['entity_name']}** — {h['relationship']} "
                        f"(confidence: {h['confidence']:.0%})"
                    )
                if len(history) > 10:
                    lines.append(f"\n... and {len(history) - 10} more records.")

            return "\n".join(lines), citations, min(len(history) / 10, 0.9)

        # Fallback: document search
        if search_results and search_results.get("documents"):
            return self._compose_answer_with_docs(
                "Graph history was unavailable. Here are relevant documents:",
                search_results, "history",
            ), [], 0.4

        return (
            "I could not find maintenance history. Try searching with the "
            "exact equipment name or ID from the knowledge graph.", [], 0.0
        )

    async def _handle_recommendation(
        self,
        question: str,
        search_results: dict | None,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        intent = self._classify_intent(question)
        equipment = self._extract_equipment(question) or "the equipment"
        maint_type = self._extract_maintenance_type(question)

        result = await self._call_tool("maintenance_recommendation", {
            "equipment_name": equipment,
            "maintenance_type": maint_type,
            "issue_description": question,
        }, tool_ctx, tools_used)

        if result.success and result.data:
            rec = result.data.get("recommendation", "")
            return rec, [], 0.85 if result.error is None else 0.5

        return (
            f"I could not generate recommendations for {equipment}. "
            "Please check the equipment manual for specific guidance.", [], 0.0
        )

    async def _handle_risk(
        self,
        question: str,
        search_results: dict | None,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        equipment = self._extract_equipment(question) or "the equipment"
        env = self._extract_environment(question)

        result = await self._call_tool("maintenance_risk_assessment", {
            "equipment_name": equipment,
            "task_description": question,
            "environment_factors": env,
        }, tool_ctx, tools_used)

        if result.success and result.data:
            assessment = result.data.get("assessment", "")
            return assessment, [], 0.85 if result.error is None else 0.5

        return (
            f"I could not generate a risk assessment for {equipment}. "
            "Consult site safety procedures for guidance.", [], 0.0
        )

    async def _handle_procedure(
        self,
        intent: str,
        question: str,
        search_results: dict | None,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        equipment = self._extract_equipment(question) or "the equipment"

        result = await self._call_tool("maintenance_checklist", {
            "procedure_type": intent,
            "equipment_name": equipment,
            "context": question,
        }, tool_ctx, tools_used)

        if result.success and result.data:
            checklist = result.data.get("checklist", "")
            return checklist, [], 0.85 if result.error is None else 0.5

        return (
            f"I could not generate a {intent} procedure for {equipment}. "
            "Refer to the equipment manual for detailed procedures.", [], 0.0
        )

    async def _handle_scheduling(
        self,
        question: str,
        search_results: dict | None,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        equipment = self._extract_equipment(question) or "equipment"

        prompt = (
            f"Provide maintenance scheduling guidance for {equipment} "
            f"based ONLY on available evidence. "
            f"Consider the question: {question}\n\n"
            "STRICT RULES:\n"
            "- Never invent schedules, intervals, or due dates.\n"
            "- Only reference documented maintenance intervals from the provided evidence.\n"
            "- If no evidence for scheduling exists, state: 'No supporting evidence found.'\n"
            "Based on available evidence:\n"
            "1. Known maintenance requirements\n"
            "2. Documented factors affecting the schedule\n"
            "3. Reference documents consulted"
        )

        text = ""
        if self._llm is not None:
            try:
                result = await self._llm.generate(prompt=prompt)
                text = result if isinstance(result, str) else (
                    result.get("text", "") if isinstance(result, dict) else str(result)
                )
            except Exception:
                pass

        if not text:
            text = (
                f"**Maintenance Scheduling — {equipment}**\n\n"
                "### Recommended Intervals\n"
                "- **Daily:** Visual inspection, check fluid levels, log readings\n"
                "- **Weekly:** Clean external surfaces, check for leaks\n"
                "- **Monthly:** Inspect critical components, test safety devices\n"
                "- **Quarterly:** Change lubricants, check alignment\n"
                "- **Annually:** Major overhaul, replace wear components\n\n"
                "### Factors Affecting Schedule\n"
                "- Operating hours / cycles\n"
                "- Environmental conditions (temperature, humidity, dust)\n"
                "- Manufacturer recommendations\n"
                "- Regulatory requirements\n\n"
                "> Note: Always consult the equipment manual and applicable regulations."
            )

        return text, [], 0.7

    async def _handle_general(
        self,
        question: str,
        search_results: dict | None,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        if search_results and search_results.get("documents"):
            return self._compose_answer_with_docs(
                "Here is what I found about your query:",
                search_results, "general",
            ), [], self._compute_confidence(search_results)

        return (
            "I could not find specific information for your query. "
            "Try rephrasing or including the equipment name.", [], 0.0
        )

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
    def _extract_equipment(question: str) -> str:
        q = question.lower().strip()
        for prefix in (
            "for ", "on ", "of ", "about ", "regarding ",
            "the ", "check ", "inspect ",
        ):
            if q.startswith(prefix):
                rest = q[len(prefix):].strip()
                return rest.split()[0] if rest else ""
        # Heuristic: first capitalized word or known equipment type
        for word in q.split():
            clean = word.strip(",.!?")
            if clean and (clean[0].isupper() or any(
                t in clean for t in ["pump", "valve", "motor", "tank", "pipe", "compressor",
                                     "conveyor", "fan", "filter", "heat", "exchanger",
                                     "boiler", "generator", "turbine", "separator"]
            )):
                return clean
        return ""

    @staticmethod
    def _extract_maintenance_type(question: str) -> str:
        q = question.lower()
        for mt in _MAINTENANCE_PROCEDURE_TYPES:
            if mt in q:
                return mt
        return "preventive"

    @staticmethod
    def _extract_environment(question: str) -> str:
        q = question.lower()
        envs = []
        if any(w in q for w in ["height", "high", "ladder", "scaffold", "roof"]):
            envs.append("working at height")
        if any(w in q for w in ["confined", "tank", "vessel", "pit", "enclosed"]):
            envs.append("confined space")
        if any(w in q for w in ["electrical", "voltage", "power", "live", "energized"]):
            envs.append("electrical hazard")
        if any(w in q for w in ["chemical", "acid", "gas", "fume", "toxic", "hazmat"]):
            envs.append("chemical exposure")
        return "; ".join(envs)

    @staticmethod
    def _build_citations(history: list[dict]) -> list[Citation]:
        citations: list[Citation] = []
        for h in history[:5]:
            citations.append(Citation(
                document_name=h.get("source_document", "") or h.get("entity_name", "Maintenance Record"),
                chunk_content=f"{h['relationship']}: {h['entity_name']} ({h['entity_type']})",
                score=h.get("confidence", 0.5),
                similarity_score=h.get("confidence", 0.5),
            ))
        return citations

    @staticmethod
    def _compose_answer_with_docs(
        preamble: str,
        search_results: dict | None,
        context_label: str,
    ) -> str:
        if not search_results:
            return preamble

        docs = search_results.get("documents", [])
        entities = search_results.get("entities", [])

        lines = [preamble, ""]

        if docs:
            lines.append(f"**Documents ({len(docs)} found):**")
            for i, d in enumerate(docs[:5], 1):
                name = d.get("document_name", "Unknown")
                score = d.get("score", 0)
                content = d.get("content", "")[:200]
                lines.append(f"{i}. **{name}** (score: {score:.2f})")
                if content:
                    lines.append(f"   _{content}..._")
            if len(docs) > 5:
                lines.append(f"\n... and {len(docs) - 5} more documents.")

        if entities:
            if docs:
                lines.append("")
            lines.append(f"**Graph Entities ({len(entities)} found):**")
            for i, e in enumerate(entities[:5], 1):
                lines.append(f"{i}. **{e.get('name', 'Unknown')}** — type: `{e.get('type', 'N/A')}`")

        return "\n".join(lines)

    @staticmethod
    def _compute_confidence(search_results: dict | None) -> float:
        if not search_results:
            return 0.0
        docs = search_results.get("documents", [])
        entities = search_results.get("entities", [])
        if not docs and not entities:
            return 0.0
        scores = [d.get("score", 0.0) for d in docs if d.get("score") is not None]
        if not scores:
            return 0.4 if entities else 0.0
        return min(sum(scores) / len(scores), 1.0)

    @staticmethod
    def _compose_fallback_answer(question: str, search_results: dict | None) -> str:
        lines = [
            "I encountered some issues while processing your request.",
            "",
        ]

        if search_results:
            docs = search_results.get("documents", [])
            entities = search_results.get("entities", [])
            if docs:
                lines.append("However, I found the following relevant documents:")
                for i, d in enumerate(docs[:3], 1):
                    name = d.get("document_name", "Document")
                    content = d.get("content", "")[:300]
                    lines.append(f"\n**{i}. {name}**")
                    if content:
                        lines.append(content)
            if entities:
                lines.append(f"\n**Related equipment in knowledge graph:**")
                for e in entities[:3]:
                    lines.append(f"- {e.get('name', 'Unknown')} ({e.get('type', 'N/A')})")

        if not search_results or (not search_results.get("documents") and not search_results.get("entities")):
            lines.append(
                "Try one of the following:\n"
                "- `Show preventive maintenance checklist for pump P-101`\n"
                "- `What is the maintenance history for motor M-101?`\n"
                "- `Risk assessment for replacing valve V-101`\n"
                "- `What spare parts are needed for compressor C-201?`\n"
                "- `PPE required for electrical maintenance`"
            )

        return "\n".join(lines)
