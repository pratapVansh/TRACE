"""Root Cause Analysis Agent — incident investigation and corrective actions."""

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
from app.agents.framework.agents.no_evidence import annotate_answer, has_evidence, has_any_evidence, no_evidence_response
from app.agents.framework.agents.rca_tools import RCA_SYSTEM_PROMPT
from app.core.authorization import Permission
from app.core.authorization.permissions import get_permissions_for_role
from app.schemas.rag import Citation

_NO_EVIDENCE_SUGGESTIONS = [
    "**Upload incident reports**: failure records, event logs, and inspection reports "
    "related to the equipment or process so the system can search them.",
    "**Ensure the asset exists in the knowledge graph** — use the Asset Explorer to "
    "confirm the equipment tag (e.g. \"P-101\") is present with incident relationships.",
    "**Provide more context**: include the equipment ID, incident date, or failure "
    "mode in your query (e.g. \"Root cause of Pump P-101 vibration on 2024-03-15\").",
    "**Check document processing status** — newly uploaded incident records may still "
    "be indexing. Retry after a few minutes.",
]

logger = logging.getLogger(__name__)

_RCA_TASKS = [
    "root cause", "rca", "incident", "failure analysis",
    "why did", "what caused", "investigate", "breakdown analysis",
    "corrective action", "preventive action", "fault",
    "probable cause", "evidence", "similar incident",
]

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "analyze": [
        "root cause", "rca", "why did", "what caused", "analyze",
        "investigate", "determine cause", "find cause",
    ],
    "evidence": [
        "evidence", "gather evidence", "collect evidence",
        "what do we know", "facts", "data",
    ],
    "similar": [
        "similar", "past incident", "previous", "happened before",
        "look up similar", "find similar",
    ],
    "corrective": [
        "corrective action", "fix", "how to prevent",
        "remediation", "action plan", "preventive action",
    ],
}


class RootCauseAnalysisAgent(BaseAgent):
    """Investigates incidents and determines probable root causes.

    Capabilities:
    - incident search across graph and documents
    - evidence gathering from connections and documents
    - root cause analysis with confidence ranking
    - similar incident lookup
    - corrective and preventive action recommendations
    """

    agent_id = "root_cause_analysis"
    name = "Root Cause Analysis Agent"
    description = (
        "Investigates incidents and failures — searches for evidence, "
        "determines probable root causes with confidence ranking, "
        "finds similar past incidents, and recommends corrective actions."
    )
    supported_tasks = _RCA_TASKS
    required_permissions: set[Permission] = {Permission.ASSETS_READ, Permission.MAINTENANCE}
    # Workflow contract enforced by _collect_evidence / _call_root_cause below and
    # handed to the LLM that writes the analysis (see RootCauseTool).
    system_prompt = RCA_SYSTEM_PROMPT

    def __init__(
        self, tool_executor: ToolExecutor | None = None,
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
            context, agent_name=self.name,
            execution_id=str(uuid.uuid4())[:8],
            user_permissions=perm_strings,
        )

        intent = self._classify_intent(question)
        entity = self._extract_entity(question)

        incident_result = await self._call_tool("incident_search", {
            "query": question, "limit": 10, "source": "all",
        }, tool_ctx, tools_used)

        search_data = incident_result.data if incident_result.success else None

        if context.working_memory is not None:
            context.working_memory.set_temp("rca_intent", intent)
            if search_data:
                context.working_memory.set_temp("rca_search_results", search_data)

        # ── Zero-evidence guard ─────────────────────────────────
        if not has_evidence(incident_result):
            return no_evidence_response(
                agent_name=self.name,
                question=question,
                tools_used=tools_used,
                suggestions=_NO_EVIDENCE_SUGGESTIONS,
            )

        # ── Pre-reasoning: retrieve similar past investigations ──
        similar_cases: list[dict] = []
        if context.session is not None:
            try:
                from app.services.experience_replay import ExperienceReplayService
                replay = ExperienceReplayService(context.session)
                similar_cases_raw = await replay.retrieve_similar(question, top_k=3)
                if context.working_memory is not None:
                    context.working_memory.set_temp(
                        "similar_historical_cases",
                        [c.model_dump() for c in similar_cases_raw],
                    )
            except Exception:
                logger.warning("Experience replay retrieval failed", exc_info=True)

        answer = ""
        citations: list[Citation] = []
        confidence = 0.0

        if intent in ("evidence", "analyze"):
            answer, citations, confidence = await self._handle_analysis(
                question, entity, search_data, tool_ctx, tools_used, context
            )
        elif intent == "similar":
            answer, citations, confidence = await self._handle_similar(
                question, entity, search_data, tool_ctx, tools_used,
            )
        elif intent == "corrective":
            answer, citations, confidence = await self._handle_corrective(
                question, entity, search_data, tool_ctx, tools_used,
            )
        else:
            answer, citations, confidence = await self._handle_general(
                question, search_data, tool_ctx, tools_used,
            )

        if not answer:
            answer = self._fallback_answer(question, search_data)

        if context.working_memory is not None:
            context.working_memory.set_temp("rca_answer", answer)
            context.working_memory.set_temp("rca_confidence", confidence)

        _search_dict = locals().get("search_data") or locals().get("search_results") or locals().get("report_data")
        _final_conf, _expl = self.evaluate_confidence(True, _search_dict, locals().get("answer", ""))
        confidence = _final_conf
        answer = annotate_answer(answer, citations=citations, tools_used=tools_used, confidence=confidence, confidence_explanation=_expl, search_data=_search_dict)

        # ── Post-completion: persist investigation record ───────
        if confidence > 0.3 and answer.strip() and context.session is not None:
            try:
                from app.services.experience_replay import ExperienceReplayService
                replay = ExperienceReplayService(context.session)
                await replay.store_investigation_from_components(
                    problem=question,
                    root_cause=answer[:2000],
                    actions="",
                    evidence_summary=f"{len(citations)} document citations",
                    success=confidence >= 0.6,
                    failure_reason=None if confidence >= 0.6 else "Low confidence in analysis",
                    confidence=confidence,
                    citations=[c.model_dump() for c in citations],
                    graph_citations=[],
                    tools_used=tools_used,
                    conversation_id=str(context.conversation_id) if context.conversation_id else None,
                    user_id=str(context.user_id) if context.user_id else None,
                )
            except Exception:
                logger.warning("Experience replay storage failed", exc_info=True)

        return AgentResponse(
            confidence_explanation=_expl,
            answer=answer, citations=citations, confidence=confidence,
            tools_used=tools_used, agent_name=self.name,
        )

    async def _handle_analysis(
        self, question: str, entity: str,
        search_data: dict | None,
        tool_ctx: ToolContext, tools_used: list[str],
        agent_context: AgentContext,
    ) -> tuple[str, list[Citation], float]:

        # 1. Evidence collection always runs first — it is the sole source of
        #    the evidence summary that root_cause is allowed to reason over.
        evidence_summary, evidence_result = await self._collect_evidence(
            question, entity, tool_ctx, tools_used,
        )
        if not evidence_summary:
            logger.info(
                "RCA: evidence_collection returned nothing for %r — root_cause skipped.",
                entity or question,
            )
            return "", [], 0.0

        # 2. Peer agents add supplementary context on top of the collected
        #    evidence; they never stand in for it.
        delegated = await self._delegate_evidence(entity, agent_context)
        if delegated:
            evidence_summary = (
                evidence_summary
                + "\n\nSupplementary agent findings:\n"
                + delegated
            )

        # 3. Analysis, always carrying the collected evidence forward.
        rca_result = await self._call_root_cause(
            question, entity, evidence_summary, tool_ctx, tools_used,
        )

        if rca_result.success and rca_result.data:
            analysis = rca_result.data.get("analysis", "")
            return analysis, self._build_citations(evidence_result), 0.85

        return "", [], 0.0

    async def _collect_evidence(
        self, question: str, entity: str,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, ToolResult | None]:
        """Run ``evidence_collection`` and render its result as a summary string.

        An empty summary means no grounded evidence exists, and therefore that
        ``root_cause`` must not run.
        """
        evidence_result = await self._call_tool("evidence_collection", {
            "entity_name": entity or question,
            "depth": 2, "limit": 30,
        }, tool_ctx, tools_used)

        if not has_evidence(evidence_result):
            return "", evidence_result

        d = evidence_result.data or {}
        graph = d.get("graph_evidence", [])
        docs = d.get("document_evidence", [])

        parts: list[str] = []
        if graph:
            parts.append(
                f"Graph evidence ({len(graph)} items): " +
                "; ".join(
                    f"{e.get('entity_name', 'unknown')} ({e.get('relationship', 'related')})"
                    for e in graph[:8]
                )
            )
        if docs:
            parts.append(
                f"Document evidence ({len(docs)} items): " +
                "; ".join(e.get("document_name", "unnamed") for e in docs[:5])
            )
        return "\n".join(parts), evidence_result

    async def _delegate_evidence(
        self, entity: str, agent_context: AgentContext,
    ) -> str:
        """Ask peer agents for supplementary context around *entity*.

        Returns an empty string when no orchestrator is available or every
        delegation fails.  Callers must treat the result as an addition to the
        ``evidence_collection`` summary, never as a replacement for it.
        """
        if agent_context.orchestrator is None:
            return ""

        tasks = [
            ("maintenance", f"Get maintenance history and work orders for {entity or 'the asset'}"),
            ("knowledge_graph", f"Find connected components and topology for {entity or 'the asset'}"),
            ("document_analysis", f"Extract SOPs and manual guidelines for {entity or 'the asset'}"),
        ]

        delegated_answers: list[str] = []
        for target_agent, subtask in tasks:
            try:
                if hasattr(agent_context.orchestrator, "execute_multi"):
                    resp = await agent_context.orchestrator.execute(
                        question=subtask, user_id=agent_context.user_id,
                        user_role=agent_context.user_role,
                        conversation_id=agent_context.conversation_id,
                        agent_id=target_agent,
                        session=agent_context.session,
                    )
                else:
                    resp = await agent_context.orchestrator.execute(
                        question=subtask, user_id=agent_context.user_id,
                        user_role=agent_context.user_role,
                        conversation_id=agent_context.conversation_id,
                        agent_ids=[target_agent], mode="single",
                        session=agent_context.session,
                    )
                delegated_answers.append(f"[{target_agent}]: {resp.answer}")
            except Exception as exc:
                logger.error("Delegation to %s failed: %s", target_agent, exc)

        return "\n\n".join(delegated_answers)

    async def _call_root_cause(
        self, question: str, entity: str, evidence_summary: str,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> ToolResult:
        """Invoke ``root_cause``, refusing to dispatch without evidence.

        ``evidence_collection`` must have run and produced a summary first;
        analysing an empty summary can only yield an ungrounded answer, so the
        call is blocked here rather than left to the tool to reject.
        """
        if not evidence_summary.strip():
            logger.warning(
                "RCA: root_cause suppressed — no evidence_collection summary available."
            )
            return ToolResult(
                data=None,
                error=(
                    "root_cause requires an evidence_summary produced by "
                    "evidence_collection; none was available."
                ),
            )

        return await self._call_tool("root_cause", {
            "incident_description": question,
            "entity_name": entity,
            "evidence_summary": evidence_summary,
        }, tool_ctx, tools_used)

    async def _handle_similar(
        self, question: str, entity: str,
        search_data: dict | None,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        result = await self._call_tool("similar_incident", {
            "query": question, "entity_name": entity, "limit": 10,
        }, tool_ctx, tools_used)

        if result.success and result.data:
            d = result.data
            similar = d.get("similar_incidents", [])
            docs = d.get("related_documents", [])

            lines = [f"**Similar Incidents — {len(similar)} found**", ""]
            for i, s in enumerate(similar[:8], 1):
                lines.append(f"{i}. **{s['name']}** ({s['type']}) — confidence: {s['confidence']:.0%}")
            if docs:
                lines.append("")
                lines.append(f"**Related Documents ({len(docs)}):**")
                for d_item in docs[:5]:
                    lines.append(f"- {d_item['document_name']} (score: {d_item['score']:.2f})")

            citations = [Citation(
                document_name=s.get("source_document", "Incident Record"),
                chunk_content=s["name"], score=s.get("confidence", 0.5),
                similarity_score=s.get("confidence", 0.5),
            ) for s in similar[:5] if s.get("source_document")]

            return "\n".join(lines), citations, min(len(similar) / 10, 0.85)

        return "No similar incidents found.", [], 0.0

    async def _handle_corrective(
        self, question: str, entity: str,
        search_data: dict | None,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        # Only proceed when incident search already found grounded data
        if not has_evidence(search_data):
            return "", [], 0.0

        # Corrective actions are root-cause conclusions too, so they follow the
        # same contract: collect evidence first, then analyse with it.
        evidence_summary, evidence_result = await self._collect_evidence(
            question, entity, tool_ctx, tools_used,
        )
        if not evidence_summary:
            logger.info(
                "RCA: no evidence for %r — corrective-action analysis skipped.",
                entity or question,
            )
            return "", [], 0.0

        rca_result = await self._call_root_cause(
            question, entity, evidence_summary, tool_ctx, tools_used,
        )

        if rca_result.success and rca_result.data:
            return (
                rca_result.data.get("analysis", ""),
                self._build_citations(evidence_result),
                0.7,
            )
        return "", [], 0.0

    async def _handle_general(
        self, question: str,
        search_data: dict | None,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        if search_data:
            incidents = search_data.get("incidents", [])
            docs = search_data.get("documents", [])
            lines = [f"**Incident Search Results**", ""]
            if incidents:
                lines.append(f"**Graph entities ({len(incidents)}):**")
                for i, s in enumerate(incidents[:8], 1):
                    lines.append(f"{i}. **{s['name']}** ({s['type']})")
            if docs:
                if incidents:
                    lines.append("")
                lines.append(f"**Documents ({len(docs)}):**")
                for d in docs[:5]:
                    lines.append(f"- {d['document_name']} (score: {d.get('score', 0.0):.2f})")
            return "\n".join(lines), [], self._compute_confidence(search_data)
        return "", [], 0.0

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
    def _extract_entity(question: str) -> str:
        q = question.lower()
        for word in q.split():
            clean = word.strip(",.!?")
            if clean and (clean[0].isupper() or any(
                t in clean.lower() for t in [
                    "pump", "valve", "motor", "tank", "pipe", "compressor",
                    "conveyor", "boiler", "generator", "turbine",
                ]
            )):
                return clean
        return ""

    @staticmethod
    def _build_citations(evidence_result: ToolResult | None) -> list[Citation]:
        citations: list[Citation] = []
        if evidence_result is not None and evidence_result.success and evidence_result.data:
            for e in evidence_result.data.get("document_evidence", [])[:5]:
                citations.append(Citation(
                    document_name=e.get("document_name", "Evidence"),
                    chunk_content=e.get("content", "")[:200],
                    score=e.get("score", 0.5),
                    similarity_score=e.get("score", 0.5),
                ))
        return citations

    @staticmethod
    def _compute_confidence(search_data: dict | None) -> float:
        if not search_data:
            return 0.0
        docs = search_data.get("documents", [])
        scores = [d.get("score", 0.0) for d in docs if d.get("score") is not None]
        if scores:
            return min(sum(scores) / len(scores), 1.0)
        return 0.4 if search_data.get("incidents") else 0.0

    @staticmethod
    def _fallback_answer(question: str, search_data: dict | None) -> str:
        lines = ["I encountered some issues processing your RCA request.", ""]
        if search_data:
            incidents = search_data.get("incidents", [])
            docs = search_data.get("documents", [])
            if incidents:
                lines.append(f"**Related incidents ({len(incidents)}):**")
                for s in incidents[:5]:
                    lines.append(f"- **{s['name']}** ({s['type']})")
            if docs:
                if incidents:
                    lines.append("")
                lines.append(f"**Related documents ({len(docs)}):**")
                for d in docs[:3]:
                    lines.append(f"- {d['document_name']}")
        if not search_data or (not search_data.get("incidents") and not search_data.get("documents")):
            lines.append(
                "Try one of the following:\n"
                "- `What caused the pump P-101 failure?`\n"
                "- `Find similar incidents to motor M-101 breakdown`\n"
                "- `Gather evidence for valve V-101 leak`\n"
                "- `Corrective actions for compressor C-201 fault`"
            )
        return "\n".join(lines)
