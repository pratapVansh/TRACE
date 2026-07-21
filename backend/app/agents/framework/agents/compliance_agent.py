"""Compliance Agent — SOP/regulatory compliance, gap analysis, audit preparation."""

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
    "**Upload compliance documents**: SOPs, regulatory standards, audit checklists, "
    "and inspection records for the topic you are checking.",
    "**Verify the procedure or standard exists** in the document store — search for "
    "the SOP number or regulation code (e.g. \"ISO 45001\", \"SOP-MAINT-001\").",
    "**Ensure related assets are in the knowledge graph** so compliance checks can "
    "link equipment to the applicable procedures and standards.",
    "**Check document processing status** — recently uploaded compliance documents "
    "may still be indexing.  Retry after a few minutes.",
]

logger = logging.getLogger(__name__)

_COMPLIANCE_TASKS = [
    "compliance",
    "sop",
    "regulation",
    "standard",
    "audit",
    "violation",
    "non-compliance",
    "corrective action",
    "safety",
    "inspection compliance",
    "documentation",
    "certification",
    "gap",
    "recommendation",
    "compliance score",
    "audit preparation",
]

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "sop_compliance": [
        "sop", "standard operating procedure", "procedure compliance",
        "work instruction", "follow procedure",
    ],
    "regulatory_compliance": [
        "regulation", "regulatory", "osha", "iso", "legal", "statutory",
        "comply with", "standard", "code", "requirement",
    ],
    "missing_documentation": [
        "missing document", "missing documentation", "need document",
        "missing sop", "absent", "not found", "where is",
        "document missing", "lack of documentation",
    ],
    "missing_inspections": [
        "missing inspection", "overdue inspection", "inspection past due",
        "not inspected", "inspection missing", "incomplete inspection",
        "missed inspection",
    ],
    "compliance_scoring": [
        "compliance score", "score", "rating", "how compliant",
        "compliance level", "percentage", "health", "status",
    ],
    "violated_procedures": [
        "violation", "violated", "non-compliance", "breach",
        "infraction", "deviation", "nonconformance", "incident",
        "not following", "failed to comply",
    ],
    "safety_recommendations": [
        "safety recommendation", "suggest", "improve safety",
        "safety improvement", "make safer", "hazard reduction",
        "corrective action", "preventive action",
    ],
    "audit_preparation": [
        "audit", "audit preparation", "get ready for audit",
        "audit checklist", "audit readiness", "prepare for audit",
        "audit scope", "audit plan",
    ],
}

_SUPPORTED_STANDARDS = [
    "osha", "iso 9001", "iso 14001", "iso 45001",
    "api", "ansi", "asme", "nfpa", "iec",
]

_COMPLIANCE_SEVERITIES = ["critical", "high", "medium", "low"]


class ComplianceAgent(BaseAgent):
    """Handles all compliance-related queries.

    Capabilities:
    - SOP compliance verification
    - Regulatory compliance checks
    - Missing documentation / inspection detection
    - Compliance scoring
    - Violated procedure identification
    - Safety recommendations
    - Audit preparation

    Fallback chain (per tool):
    Graph → Document Retrieval → LLM template → Evidence-only
    """

    agent_id = "compliance"
    name = "Compliance Agent"
    description = (
        "Handles SOP compliance, regulatory compliance, missing "
        "documentation and inspections, compliance scoring, violated "
        "procedures, safety recommendations, and audit preparation."
    )
    supported_tasks = _COMPLIANCE_TASKS
    required_permissions: set[Permission] = {Permission.COMPLIANCE}

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
        search_result = await self._call_tool("compliance_search", {
            "query": question,
            "top_k": 10,
            "source": "all",
        }, tool_ctx, tools_used)

        if search_result.success and search_result.data:
            search_results = search_result.data
            docs = search_results.get("documents", [])
            entities = search_results.get("entities", [])

            if context.working_memory is not None:
                context.working_memory.set_temp("compliance_search_docs", docs[:5])
                context.working_memory.set_temp("compliance_search_entities", entities[:5])
                context.working_memory.set_temp("compliance_intent", intent)

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
            "sop_compliance": self._handle_sop_compliance,
            "regulatory_compliance": self._handle_regulatory_compliance,
            "missing_documentation": self._handle_missing_documentation,
            "missing_inspections": self._handle_missing_inspections,
            "compliance_scoring": self._handle_compliance_scoring,
            "violated_procedures": self._handle_violated_procedures,
            "safety_recommendations": self._handle_safety_recommendations,
            "audit_preparation": self._handle_audit_preparation,
        }

        if intent in handler_map:
            answer, citations, confidence = await handler_map[intent](
                question, search_results, tool_ctx, tools_used,
            )
        else:
            answer, citations, confidence = await self._handle_general(
                question, search_results, tool_ctx, tools_used,
            )

        if not answer:
            answer = self._compose_fallback_answer(question, search_results)

        wm = context.working_memory
        if wm is not None:
            wm.set_temp("compliance_answer", answer)
            wm.set_temp("compliance_confidence", confidence)

        _search_dict = search_results
        _final_conf, _expl = self.evaluate_confidence(True, _search_dict, answer)
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

    async def _handle_sop_compliance(
        self,
        question: str,
        search_results: dict | None,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        target = self._extract_target(question)

        result = await self._call_tool("compliance_check", {
            "target": target or question,
            "standard": "SOP",
            "scope": "procedure",
        }, tool_ctx, tools_used)

        if result.success and result.data:
            data = result.data
            lines = [
                f"## SOP Compliance Check — {data['target']}",
                "",
                f"**Status:** {'✅ Compliant' if data['compliant'] else '❌ Issues Found'}",
                f"**Score:** {data['score']:.0%}",
                "",
            ]
            if data.get("findings"):
                lines.append("### Findings")
                for f_data in data["findings"]:
                    lines.append(f"- **{f_data['severity'].upper()}** {f_data['detail']}")
                lines.append("")
            if data.get("llm_assessment"):
                lines.append("### Assessment")
                lines.append(data["llm_assessment"])

            citations = self._build_citations_from_check(data)
            return "\n".join(lines), citations, data["score"]

        return self._compose_answer_with_docs(
            "Could not complete SOP compliance check. Here are relevant documents:",
            search_results, "sop",
        ), [], 0.3

    async def _handle_regulatory_compliance(
        self,
        question: str,
        search_results: dict | None,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        target = self._extract_target(question)
        standard = self._extract_standard(question)

        result = await self._call_tool("compliance_check", {
            "target": target or question,
            "standard": standard or "regulatory",
            "scope": "full",
        }, tool_ctx, tools_used)

        if result.success and result.data:
            data = result.data
            lines = [
                f"## Regulatory Compliance Check — {data['target']}",
                "",
                f"**Standard:** {data['standard']}",
                f"**Status:** {'✅ Compliant' if data['compliant'] else '❌ Issues Found'}",
                f"**Score:** {data['score']:.0%}",
                "",
            ]
            if data.get("findings"):
                lines.append("### Findings")
                for f_data in data["findings"]:
                    lines.append(f"- **{f_data['severity'].upper()}** {f_data['detail']}")
                lines.append("")
            if data.get("llm_assessment"):
                lines.append("### Assessment")
                lines.append(data["llm_assessment"])

            citations = self._build_citations_from_check(data)
            return "\n".join(lines), citations, data["score"]

        return self._compose_answer_with_docs(
            "Could not complete regulatory compliance check. Here are relevant documents:",
            search_results, "regulatory",
        ), [], 0.3

    async def _handle_missing_documentation(
        self,
        question: str,
        search_results: dict | None,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        target = self._extract_target(question)

        result = await self._call_tool("compliance_gap", {
            "target": target or question,
            "gap_type": "documentation",
        }, tool_ctx, tools_used)

        if result.success and result.data:
            data = result.data
            total = data.get("total_gaps", 0)
            gaps = data.get("gaps", [])
            analysis = data.get("analysis", "")

            if total == 0:
                return (
                    f"No documentation gaps found for '{data['target']}'. "
                    "All required documentation appears to be in place."
                ), [], 0.9

            lines = [
                f"## Documentation Gaps — {data['target']}",
                "",
                f"**{total} gap(s) identified.**",
                "",
            ]
            for g in gaps:
                lines.append(f"- **[{g['severity'].upper()}] {g['type'].replace('_', ' ').title()}**")
                lines.append(f"  {g['detail']}")
                if g.get("recommendation"):
                    lines.append(f"  → {g['recommendation']}")
            lines.append("")

            if analysis:
                lines.append("### Analysis")
                lines.append(analysis)

            return "\n".join(lines), [], min(1.0 - (total * 0.1), 0.7)

        return self._compose_answer_with_docs(
            "Could not identify documentation gaps. Here are relevant documents:",
            search_results, "documentation",
        ), [], 0.3

    async def _handle_missing_inspections(
        self,
        question: str,
        search_results: dict | None,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        target = self._extract_target(question)

        result = await self._call_tool("compliance_gap", {
            "target": target or question,
            "gap_type": "inspection",
        }, tool_ctx, tools_used)

        if result.success and result.data:
            data = result.data
            total = data.get("total_gaps", 0)
            gaps = data.get("gaps", [])
            analysis = data.get("analysis", "")

            if total == 0:
                return (
                    f"No inspection gaps found for '{data['target']}'. "
                    "Inspection procedures and schedules appear to be in place."
                ), [], 0.9

            lines = [
                f"## Inspection Gaps — {data['target']}",
                "",
                f"**{total} gap(s) identified.**",
                "",
            ]
            for g in gaps:
                lines.append(f"- **[{g['severity'].upper()}] {g['type'].replace('_', ' ').title()}**")
                lines.append(f"  {g['detail']}")
                if g.get("recommendation"):
                    lines.append(f"  → {g['recommendation']}")
            lines.append("")

            if analysis:
                lines.append("### Analysis")
                lines.append(analysis)

            return "\n".join(lines), [], min(1.0 - (total * 0.15), 0.6)

        return self._compose_answer_with_docs(
            "Could not identify inspection gaps. Here are relevant documents:",
            search_results, "inspection",
        ), [], 0.3

    async def _handle_compliance_scoring(
        self,
        question: str,
        search_results: dict | None,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        target = self._extract_target(question)

        check_result = await self._call_tool("compliance_check", {
            "target": target or question,
            "scope": "full",
        }, tool_ctx, tools_used)

        gap_result = await self._call_tool("compliance_gap", {
            "target": target or question,
            "gap_type": "all",
        }, tool_ctx, tools_used)

        check_data = check_result.data if check_result.success else {}
        gap_data = gap_result.data if gap_result.success else {}

        doc_count = check_data.get("evidence_documents", 0) if check_data else 0
        entity_count = check_data.get("evidence_entities", 0) if check_data else 0
        gap_count = gap_data.get("total_gaps", 0) if gap_data else 0
        check_score = check_data.get("score", 0.0) if check_data else 0.0

        base_score = check_score if doc_count > 0 else 0.2
        gap_penalty = gap_count * 0.1
        final_score = max(0.0, min(1.0, base_score - gap_penalty))

        severity = "Critical" if final_score < 0.3 else "High" if final_score < 0.5 else "Medium" if final_score < 0.7 else "Good" if final_score < 0.9 else "Excellent"

        lines = [
            f"## Compliance Score — {target or 'General'}",
            "",
            f"**Overall Score:** {final_score:.0%} ({severity})",
            "",
            "### Breakdown",
            f"- Evidence documents found: {doc_count}",
            f"- Graph entities found: {entity_count}",
            f"- Compliance check score: {check_score:.0%}",
            f"- Gaps identified: {gap_count}",
            f"- Gap penalty: -{gap_penalty:.0%}",
            "",
            "### Recommendations",
        ]
        if gap_count > 0:
            lines.append("- Address identified gaps to improve score")
        if doc_count == 0:
            lines.append("- Upload relevant compliance documentation")
        if entity_count == 0:
            lines.append("- Register equipment/areas in knowledge graph")
        if final_score >= 0.9:
            lines.append("- Maintain current compliance practices")
            lines.append("- Schedule regular audits to sustain score")

        return "\n".join(lines), [], final_score

    async def _handle_violated_procedures(
        self,
        question: str,
        search_results: dict | None,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        target = self._extract_target(question)

        gap_result = await self._call_tool("compliance_gap", {
            "target": target or question,
            "gap_type": "procedure",
        }, tool_ctx, tools_used)

        if gap_result.success and gap_result.data:
            data = gap_result.data
            gaps = data.get("gaps", [])
            analysis = data.get("analysis", "")

            procedure_gaps = [g for g in gaps if g.get("category") == "procedure"]
            if not procedure_gaps:
                return (
                    f"No procedure violations found for '{data['target']}'."
                ), [], 0.85

            lines = [
                f"## Procedure Violations — {data['target']}",
                "",
                f"**{len(procedure_gaps)} violation(s) identified.**",
                "",
            ]
            for g in procedure_gaps:
                lines.append(f"- **[{g['severity'].upper()}]** {g['detail']}")
                if g.get("recommendation"):
                    lines.append(f"  → {g['recommendation']}")
            lines.append("")

            if analysis:
                lines.append("### Corrective Action Plan")
                lines.append(analysis)

            return "\n".join(lines), [], min(1.0 - (len(procedure_gaps) * 0.2), 0.6)

        return self._compose_answer_with_docs(
            "Could not identify procedure violations. Here are relevant documents:",
            search_results, "violations",
        ), [], 0.3

    async def _handle_safety_recommendations(
        self,
        question: str,
        search_results: dict | None,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        target = self._extract_target(question)
        finding = question

        gap_result = await self._call_tool("compliance_gap", {
            "target": target or question,
            "gap_type": "all",
        }, tool_ctx, tools_used)

        gaps_summary = ""
        if gap_result.success and gap_result.data:
            gaps = gap_result.data.get("gaps", [])
            if gaps:
                gaps_summary = "; ".join(f"{g['type']}: {g['detail']}" for g in gaps[:3])

        if gaps_summary:
            finding = f"{question}. Identified issues: {gaps_summary}"

        result = await self._call_tool("compliance_recommendation", {
            "finding": finding,
            "severity": "high",
            "target": target or "general",
        }, tool_ctx, tools_used)

        if result.success and result.data:
            rec = result.data.get("recommendation", "")
            return rec, [], 0.75 if result.error is None else 0.5

        return (
            f"Could not generate safety recommendations for '{target or 'your query'}'. "
            "Consult site safety procedures and relevant regulations.", [], 0.0
        )

    async def _handle_audit_preparation(
        self,
        question: str,
        search_results: dict | None,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        target = self._extract_target(question)
        standard = self._extract_standard(question)

        check_result = await self._call_tool("compliance_check", {
            "target": target or "general operations",
            "standard": standard or "regulatory",
            "scope": "full",
        }, tool_ctx, tools_used)

        gap_result = await self._call_tool("compliance_gap", {
            "target": target or "general operations",
            "gap_type": "all",
        }, tool_ctx, tools_used)

        check_data = check_result.data if check_result.success else {}
        gap_data = gap_result.data if gap_result.success else {}

        gaps = gap_data.get("gaps", []) if gap_data else []
        check_assessment = check_data.get("llm_assessment", "") if check_data else ""

        lines = [
            f"## Audit Preparation — {target or 'General Operations'}",
            "",
            "### Readiness Summary",
        ]

        if check_data:
            lines.append(f"- **Compliance Status:** {'✅ Ready' if check_data.get('compliant') else '❌ Issues Found'}")
            lines.append(f"- **Check Score:** {check_data.get('score', 0.0):.0%}")
        lines.append(f"- **Gaps Identified:** {len(gaps)}")
        lines.append("")

        if gaps:
            lines.append("### Gaps to Address Before Audit")
            by_severity: dict[str, list[dict]] = {}
            for g in gaps:
                by_severity.setdefault(g.get("severity", "medium"), []).append(g)
            for sev in ("critical", "high", "medium", "low"):
                for g in by_severity.get(sev, []):
                    lines.append(f"- **[{sev.upper()}]** {g['detail']}")
            lines.append("")

        lines.append("### Pre-Audit Checklist")
        lines.append("1. ✅ Verify all SOPs are current and accessible")
        lines.append("2. ✅ Confirm training records are complete")
        lines.append("3. ✅ Review maintenance logs for overdue items")
        lines.append("4. ✅ Check inspection records are up to date")
        lines.append("5. ✅ Verify calibration certificates are valid")
        lines.append("6. ✅ Ensure corrective actions are documented")
        lines.append("7. ✅ Prepare evidence files for sampling")
        lines.append("")

        if check_assessment:
            lines.append("### Assessment")
            lines.append(check_assessment)

        rec_result = await self._call_tool("compliance_recommendation", {
            "finding": f"Audit preparation for {target or 'general operations'}",
            "severity": "high",
            "target": target or "general",
        }, tool_ctx, tools_used)

        if rec_result.success and rec_result.data:
            lines.append("")
            lines.append("### Action Plan")
            lines.append(rec_result.data.get("recommendation", ""))

        severity_count = gap_data.get("severity_summary", {}).get("critical", 0) if gap_data else 0
        confidence = max(0.3, 0.8 - (severity_count * 0.15))

        return "\n".join(lines), [], min(confidence, 0.95)

    async def _handle_general(
        self,
        question: str,
        search_results: dict | None,
        tool_ctx: ToolContext,
        tools_used: list[str],
    ) -> tuple[str, list[Citation], float]:
        if search_results and search_results.get("documents"):
            return self._compose_answer_with_docs(
                "Here is what I found regarding compliance:",
                search_results, "general",
            ), [], self._compute_confidence(search_results)

        return (
            "I could not find specific compliance information. "
            "Try specifying a regulation, standard, or equipment name.", [], 0.0
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
    def _extract_target(question: str) -> str:
        q = question.lower().strip()
        for prefix in (
            "for ", "on ", "of ", "about ", "regarding ",
            "check ", "find ", "show ",
        ):
            if q.startswith(prefix):
                rest = q[len(prefix):].strip()
                words = rest.split()
                if words:
                    candidate = words[0].strip(",.!?")
                    if candidate and len(candidate) > 1:
                        return candidate
        for word in q.split():
            clean = word.strip(",.!?")
            if clean and (clean[0].isupper() or any(
                t in clean.lower() for t in [
                    "pump", "valve", "motor", "tank", "pipe", "compressor",
                    "conveyor", "boiler", "generator", "turbine", "exchanger",
                    "area", "unit", "plant", "line", "system",
                ]
            )):
                return clean
        return ""

    @staticmethod
    def _extract_standard(question: str) -> str:
        q = question.lower()
        matches = [s for s in _SUPPORTED_STANDARDS if s in q]
        if matches:
            return matches[0]
        if "sop" in q:
            return "SOP"
        if "regulation" in q or "regulatory" in q:
            return "regulatory"
        return ""

    @staticmethod
    def _build_citations_from_check(check_data: dict) -> list[Citation]:
        citations: list[Citation] = []
        if check_data.get("evidence_documents", 0) > 0:
            citations.append(Citation(
                document_name=check_data.get("target", "Compliance Check"),
                chunk_content=f"Compliance check result: {'Compliant' if check_data.get('compliant') else 'Non-Compliant'} "
                             f"(score: {check_data.get('score', 0.0):.0%})",
                score=check_data.get("score", 0.5),
                similarity_score=check_data.get("score", 0.5),
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
            "I encountered some issues processing your compliance request.",
            "",
        ]

        if search_results:
            docs = search_results.get("documents", [])
            entities = search_results.get("entities", [])
            if docs:
                lines.append("However, I found these relevant documents:")
                for i, d in enumerate(docs[:3], 1):
                    name = d.get("document_name", "Document")
                    content = d.get("content", "")[:300]
                    lines.append(f"\n**{i}. {name}**")
                    if content:
                        lines.append(content)
            if entities:
                lines.append(f"\n**Related entities in knowledge graph:**")
                for e in entities[:3]:
                    lines.append(f"- {e.get('name', 'Unknown')} ({e.get('type', 'N/A')})")

        if not search_results or (not search_results.get("documents") and not search_results.get("entities")):
            lines.append(
                "Try one of the following:\n"
                "- `Check SOP compliance for pump P-101`\n"
                "- `What regulations apply to compressor C-201?`\n"
                "- `Find missing documentation for motor M-101`\n"
                "- `Compliance score for the plant`\n"
                "- `Are there any procedure violations for valve V-101?`\n"
                "- `Prepare for an ISO 9001 audit`\n"
                "- `Safety recommendations for confined space entry`"
            )

        return "\n".join(lines)
