"""Report Generation Agent — structured reports, executive summaries, markdown."""

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

_NO_EVIDENCE_SUGGESTIONS = [
    "**Use the Report agent in a workflow**: ask \"Generate an incident report "
    "for Pump P-101 failure\" so the system retrieves evidence before drafting.",
    "**Provide context in your request**: include the equipment tag, incident "
    "date, and scope (e.g. \"Maintenance report for Motor M-201 overhaul on 2024-03-01\").",
    "**Run a retrieval query first**: ask the Asset or RCA agent about the "
    "incident, then ask for a report — the chain will carry the evidence forward.",
]

logger = logging.getLogger(__name__)

_REPORT_TASKS = [
    "report", "generate report", "incident report", "maintenance report",
    "compliance report", "executive summary", "summary",
    "document report", "create report", "markdown",
]

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "incident_report": ["incident report", "accident report", "failure report", "event report"],
    "maintenance_report": ["maintenance report", "service report", "repair report", "work order"],
    "compliance_report": ["compliance report", "audit report", "regulatory report", "inspection report"],
    "executive_summary": ["executive summary", "summary for management", "brief", "overview"],
    "markdown": ["markdown", "format", "formatted report", "document"],
}


class ReportGenerationAgent(BaseAgent):
    """Generates structured reports, executive summaries, and markdown documents.

    Capabilities:
    - incident reports with root cause and corrective actions
    - maintenance reports with work performed and recommendations
    - compliance reports with findings and non-compliances
    - executive summaries for management review
    - markdown-formatted reports
    """

    agent_id = "report_generation"
    name = "Report Generation Agent"
    description = (
        "Generates structured incident, maintenance, and compliance reports, "
        "executive summaries, and markdown-formatted documents."
    )
    supported_tasks = _REPORT_TASKS
    required_permissions: set[Permission] = {
        Permission.DOCUMENTS_READ, Permission.MAINTENANCE, Permission.COMPLIANCE,
    }

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
        title = self._extract_title(question)
        report_type = self._map_intent_to_report_type(intent)

        if context.working_memory is not None:
            context.working_memory.set_temp("report_intent", intent)
            context.working_memory.set_temp("report_title", title)

        # ── Zero-evidence guard ─────────────────────────────────
        # The report agent is legitimately called standalone OR at the end of
        # a multi-agent chain.  When invoked standalone with no prior evidence
        # (no retrieved_documents deposited by preceding agents), refuse to
        # fabricate.  When invoked in a chain the evidence is non-empty.
        has_prior_evidence = bool(context.retrieved_documents)
        if not has_prior_evidence:
            return no_evidence_response(
                agent_name=self.name,
                question=question,
                tools_used=tools_used,
                suggestions=_NO_EVIDENCE_SUGGESTIONS,
            )

        answer = ""
        confidence = 0.0

        if intent == "executive_summary":
            answer, confidence = await self._handle_summary(question, title, tool_ctx, tools_used)
        elif intent == "markdown":
            answer, confidence = await self._handle_markdown(question, title, tool_ctx, tools_used)
        else:
            answer, confidence = await self._handle_report(
                report_type, title, question, tool_ctx, tools_used,
            )

        if not answer:
            answer = self._fallback_answer(question)

        if context.working_memory is not None:
            context.working_memory.set_temp("report_answer", answer)
            context.working_memory.set_temp("report_confidence", confidence)

        _search_dict = {"retrieved_documents": list(context.retrieved_documents)} if context.retrieved_documents else None
        _final_conf, _expl = self.evaluate_confidence(True, _search_dict, answer)
        confidence = _final_conf
        answer = annotate_answer(answer, tools_used=tools_used, confidence=confidence, confidence_explanation=_expl, search_data=_search_dict)
        return AgentResponse(
            confidence_explanation=_expl,
            answer=answer, confidence=confidence,
            tools_used=tools_used, agent_name=self.name,
        )

    async def _handle_report(
        self, report_type: str, title: str, question: str,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, float]:
        result = await self._call_tool("report_generation", {
            "report_type": report_type,
            "title": title or f"{report_type.title()} Report",
            "context": question,
            "author": "AI Agent",
        }, tool_ctx, tools_used)

        if result.success and result.data:
            report = result.data.get("report", "")
            return report, 0.85 if result.error is None else 0.5

        return "", 0.0

    async def _handle_summary(
        self, question: str, title: str,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, float]:
        result = await self._call_tool("executive_summary", {
            "content": question,
            "max_bullets": 5,
            "audience": "executive",
        }, tool_ctx, tools_used)

        if result.success and result.data:
            summary = result.data.get("summary", "")
            return summary, 0.8

        return "", 0.0

    async def _handle_markdown(
        self, question: str, title: str,
        tool_ctx: ToolContext, tools_used: list[str],
    ) -> tuple[str, float]:
        result = await self._call_tool("markdown_report", {
            "title": title or "Generated Report",
            "sections": question,
            "include_toc": len(question) > 500,
        }, tool_ctx, tools_used)

        if result.success and result.data:
            report = result.data.get("report", "")
            return report, 0.75

        return "", 0.0

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
            for rt in _REPORT_TASKS:
                if rt in q:
                    scored.append(("report", 1))
                    break
        if not scored:
            scored.append(("general_report", 1))
        scored.sort(key=lambda x: -x[1])
        return scored[0][0]

    @staticmethod
    def _extract_title(question: str) -> str:
        q = question.lower()
        for prefix in ("titled ", "called ", "named "):
            if prefix in q:
                rest = q.split(prefix, 1)[1].strip()
                end = rest.find(" about")
                if end > 0:
                    return rest[:end].strip().title()
                return rest[:60].strip().title()
        for rt in ["incident", "maintenance", "compliance"]:
            if rt in q:
                idx = q.find(rt)
                return q[idx:].split(" report")[0].strip().title() + " Report"
        return "Report"

    @staticmethod
    def _map_intent_to_report_type(intent: str) -> str:
        mapping = {
            "incident_report": "incident",
            "maintenance_report": "maintenance",
            "compliance_report": "compliance",
        }
        return mapping.get(intent, "incident")

    @staticmethod
    def _fallback_answer(question: str) -> str:
        return (
            "I could not generate the requested report. Try:\n"
            "- `Generate an incident report for pump P-101 failure`\n"
            "- `Create a maintenance report for motor M-101 service`\n"
            "- `Executive summary of the Q1 compliance audit`\n"
            "- `Format this into a markdown report`"
        )
