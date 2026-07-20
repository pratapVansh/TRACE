"""Compliance tools for the ComplianceAgent.

Reuses HybridRetriever, GraphQueryService, DocumentService, and LLMProvider.
Follows the same patterns as maintenance_tools.py.
"""

from typing import Any

from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.base import FrameworkTool
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.schemas import ToolCategory, ToolMetadata
from app.agents.framework.tools.search_helper import search_hybrid

_COMPLIANCE_STANDARDS = [
    "osha", "iso", "iso 9001", "iso 14001", "iso 45001",
    "api", "ansi", "asme", "ieee", "nfpa", "iec",
    "six sigma", "lean", "tpm",
    "sop", "standard operating procedure",
]

_COMPLIANCE_KEYWORDS = [
    "compliance", "regulation", "standard", "audit", "violation",
    "non-compliance", "corrective action", "preventive action",
    "safety", "hazard", "risk", "procedure", "policy",
    "inspection", "certification", "permit", "license",
    "documentation", "record", "log", "report",
]


class ComplianceSearchTool(FrameworkTool):
    """Searches compliance documentation, procedures, and graph entities."""

    metadata = ToolMetadata(
        tool_id="compliance_search",
        name="Compliance Search",
        description=(
            "Searches compliance documents (SOPs, regulations, standards) "
            "and knowledge-graph entities for compliance-related information."
        ),
        category=ToolCategory.SEARCH,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Compliance-related search query"},
                "top_k": {"type": "integer", "description": "Max results (default 10)"},
                "source": {
                    "type": "string",
                    "enum": ["all", "documents", "graph"],
                    "description": "Where to search (default all)",
                },
                "standard": {
                    "type": "string",
                    "description": "Optional compliance standard filter (e.g. OSHA, ISO 9001)",
                },
            },
            "required": ["query"],
        },
    )

    def __init__(
        self,
        hybrid_retriever: Any = None,
        graph_query_service: Any = None,
    ) -> None:
        self._hybrid = hybrid_retriever
        self._graph_svc = graph_query_service

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        query = params.get("query", "")
        top_k = min(params.get("top_k", 10), 50)
        source = params.get("source", "all")
        standard = params.get("standard", "")

        if not query.strip():
            return ToolResult(data=None, error="Search query cannot be empty.")

        if standard:
            query = f"{query} {standard} compliance"

        sr = await search_hybrid(
            query=query,
            graph_svc=self._graph_svc,
            hybrid=self._hybrid,
            top_k=top_k,
            source=source,
            tool_name="ComplianceSearchTool",
            context=context,
            doc_item_fn=lambda item: {
                "content": item.content[:2000], "score": item.score,
                "document_name": item.document_name, "document_id": item.document_id,
                "page_number": item.page_number, "source": item.source,
            },
        )

        if not sr.documents and not sr.entities:
            return ToolResult(
                data={"documents": [], "entities": [], "total_documents": 0, "total_entities": 0},
                error="No results found from any source.",
            )

        return ToolResult(
            data={
                "documents": sr.documents,
                "entities": sr.entities,
                "total_documents": sr.total_documents,
                "total_entities": sr.total_entities,
            },
            metadata={"doc_count": sr.total_documents, "entity_count": sr.total_entities},
        )


class ComplianceCheckTool(FrameworkTool):
    """Checks compliance status for equipment, procedures, or areas."""

    metadata = ToolMetadata(
        tool_id="compliance_check",
        name="Compliance Check",
        description=(
            "Checks if equipment, procedures, or operational areas are compliant "
            "with specified standards or regulations. Returns pass/fail with details."
        ),
        category=ToolCategory.REPORTING,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Equipment name, procedure name, or area to check"},
                "standard": {
                    "type": "string",
                    "description": "Compliance standard (e.g. OSHA, ISO 9001, SOP-123)",
                },
                "scope": {
                    "type": "string",
                    "enum": ["full", "documentation", "procedure", "equipment"],
                    "description": "Scope of check (default full)",
                },
            },
            "required": ["target"],
        },
    )

    def __init__(
        self,
        hybrid_retriever: Any = None,
        graph_query_service: Any = None,
        llm_provider: Any = None,
    ) -> None:
        self._hybrid = hybrid_retriever
        self._graph_svc = graph_query_service
        self._llm = llm_provider

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        target = params.get("target", "")
        standard = params.get("standard", "")
        scope = params.get("scope", "full")

        if not target.strip():
            return ToolResult(data=None, error="target is required.")

        # Gather evidence from available sources
        evidence_docs: list[dict] = []
        evidence_entities: list[dict] = []

        search_query = f"{target} {standard} compliance procedure".strip()
        if self._hybrid is not None:
            try:
                unified = await self._hybrid.retrieve(query=search_query, top_k=8)
                for item in unified.items:
                    evidence_docs.append({
                        "content": item.content[:1000],
                        "score": item.score,
                        "document_name": item.document_name,
                    })
            except Exception:
                pass

        if self._graph_svc is not None:
            try:
                results, _ = await self._graph_svc.search_entities(query=target, limit=5)
                for e in results:
                    evidence_entities.append({
                        "id": e.id,
                        "name": e.name,
                        "type": e.type,
                        "confidence": e.confidence,
                        "source_document": e.source_document,
                    })
            except Exception:
                pass

        check_result = self._compute_check_result(target, standard, scope, evidence_docs, evidence_entities)

        if self._llm is not None:
            try:
                prompt = self._build_check_prompt(target, standard, scope, evidence_docs, evidence_entities)
                result = await self._llm.generate(prompt=prompt)
                llm_text = result if isinstance(result, str) else (
                    result.get("text", "") if isinstance(result, dict) else str(result)
                )
                if llm_text.strip():
                    check_result["llm_assessment"] = llm_text
            except Exception as exc:
                context.add_reasoning_step(f"ComplianceCheckTool: LLM unavailable — {exc}")

        context.add_reasoning_step(
            f"ComplianceCheckTool: {target} → compliant={check_result['compliant']}, "
            f"score={check_result['score']:.0%}"
        )

        return ToolResult(
            data=check_result,
            metadata={
                "compliant": check_result["compliant"],
                "score": check_result["score"],
            },
        )

    @staticmethod
    def _compute_check_result(
        target: str, standard: str, scope: str,
        docs: list[dict], entities: list[dict],
    ) -> dict:
        has_docs = len(docs) > 0
        has_entities = len(entities) > 0
        avg_score = 0.0
        if docs:
            avg_score = sum(d.get("score", 0.0) for d in docs) / len(docs)

        findings: list[dict] = []
        if not has_docs:
            findings.append({
                "type": "missing_documentation",
                "severity": "high",
                "detail": f"No compliance documents found for '{target}'.",
            })
        if not has_entities:
            findings.append({
                "type": "missing_entity",
                "severity": "medium",
                "detail": f"'{target}' not found in knowledge graph.",
            })

        compliant = len(findings) == 0
        score = min(avg_score, 0.9) if compliant else max(avg_score * 0.5, 0.1)

        return {
            "target": target,
            "standard": standard or "general",
            "scope": scope,
            "compliant": compliant,
            "score": round(score, 2),
            "findings": findings,
            "evidence_documents": len(docs),
            "evidence_entities": len(entities),
        }

    @staticmethod
    def _build_check_prompt(
        target: str, standard: str, scope: str,
        docs: list[dict], entities: list[dict],
    ) -> str:
        prompt = (
            f"Perform a compliance check for '{target}'"
        )
        if standard:
            prompt += f" against standard '{standard}'"
        prompt += f" (scope: {scope}).\n\n"

        if docs:
            prompt += "Relevant documents:\n"
            for d in docs[:3]:
                prompt += f"- [{d['document_name']}] (relevance: {d['score']:.2f}): {d['content'][:300]}\n"
        if entities:
            prompt += "Relevant entities:\n"
            for e in entities[:3]:
                prompt += f"- {e['name']} (type: {e['type']})\n"

        prompt += (
            "\nProvide:\n"
            "1. Compliance status (Compliant / Partially Compliant / Non-Compliant)\n"
            "2. Key findings\n"
            "3. Specific gaps or violations\n"
            "4. Recommended corrective actions\n"
            "Be specific and reference the evidence provided."
        )
        return prompt


class ComplianceGapTool(FrameworkTool):
    """Identifies gaps in compliance documentation, inspections, and procedures."""

    metadata = ToolMetadata(
        tool_id="compliance_gap",
        name="Compliance Gap Analysis",
        description=(
            "Identifies missing documentation, missed inspections, "
            "violated procedures, and other compliance gaps for equipment or areas."
        ),
        category=ToolCategory.REPORTING,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Equipment, area, or process to analyze"},
                "gap_type": {
                    "type": "string",
                    "enum": ["all", "documentation", "inspection", "procedure", "certification"],
                    "description": "Type of gaps to focus on (default all)",
                },
                "standard": {"type": "string", "description": "Reference standard for gap assessment"},
            },
            "required": ["target"],
        },
    )

    def __init__(
        self,
        graph_query_service: Any = None,
        hybrid_retriever: Any = None,
        document_service: Any = None,
        llm_provider: Any = None,
    ) -> None:
        self._graph_svc = graph_query_service
        self._hybrid = hybrid_retriever
        self._doc_svc = document_service
        self._llm = llm_provider

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        target = params.get("target", "")
        gap_type = params.get("gap_type", "all")
        standard = params.get("standard", "")

        if not target.strip():
            return ToolResult(data=None, error="target is required.")

        gaps: list[dict] = []
        found_docs: list[dict] = []
        found_entities: list[dict] = []

        # Phase 1 — Collect evidence
        if self._hybrid is not None:
            try:
                unified = await self._hybrid.retrieve(query=f"{target} compliance {standard}", top_k=10)
                for item in unified.items:
                    found_docs.append({
                        "content": item.content[:500],
                        "score": item.score,
                        "document_name": item.document_name,
                        "document_id": item.document_id,
                    })
            except Exception:
                pass

        if self._graph_svc is not None:
            try:
                results, _ = await self._graph_svc.search_entities(query=target, limit=5)
                for e in results:
                    found_entities.append({
                        "id": e.id,
                        "name": e.name,
                        "type": e.type,
                        "source_document": e.source_document,
                    })
            except Exception:
                pass

        # Phase 2 — Detect gaps
        if gap_type in ("all", "documentation"):
            doc_gaps = self._detect_documentation_gaps(target, standard, found_docs)
            gaps.extend(doc_gaps)

        if gap_type in ("all", "inspection"):
            insp_gaps = self._detect_inspection_gaps(target, found_entities, found_docs)
            gaps.extend(insp_gaps)

        if gap_type in ("all", "procedure"):
            proc_gaps = self._detect_procedure_gaps(target, found_docs)
            gaps.extend(proc_gaps)

        if gap_type in ("all", "certification"):
            cert_gaps = self._detect_certification_gaps(target, found_entities)
            gaps.extend(cert_gaps)

        severe_count = sum(1 for g in gaps if g.get("severity") in ("critical", "high"))
        medium_count = sum(1 for g in gaps if g.get("severity") == "medium")
        low_count = sum(1 for g in gaps if g.get("severity") == "low")

        llm_analysis = ""
        if self._llm is not None and gaps:
            try:
                prompt = self._build_gap_prompt(target, standard, gap_type, gaps, found_docs)
                result = await self._llm.generate(prompt=prompt)
                llm_analysis = result if isinstance(result, str) else (
                    result.get("text", "") if isinstance(result, dict) else str(result)
                )
            except Exception:
                llm_analysis = self._fallback_gap_summary(target, gaps)

        if not llm_analysis and gaps:
            llm_analysis = self._fallback_gap_summary(target, gaps)

        context.add_reasoning_step(
            f"ComplianceGapTool: {len(gaps)} gap(s) found for {target} "
            f"(critical={severe_count}, medium={medium_count}, low={low_count})"
        )

        return ToolResult(
            data={
                "target": target,
                "standard": standard or "general",
                "total_gaps": len(gaps),
                "severity_summary": {
                    "critical": severe_count,
                    "high": severe_count,
                    "medium": medium_count,
                    "low": low_count,
                },
                "gaps": gaps,
                "analysis": llm_analysis,
                "evidence_documents": len(found_docs),
                "evidence_entities": len(found_entities),
            },
            metadata={"gap_count": len(gaps), "severe_count": severe_count},
        )

    @staticmethod
    def _detect_documentation_gaps(target: str, standard: str, docs: list[dict]) -> list[dict]:
        gaps: list[dict] = []
        if not docs:
            gaps.append({
                "type": "missing_documentation",
                "severity": "high",
                "category": "documentation",
                "detail": f"No compliance documentation found for '{target}'.",
                "recommendation": "Locate and upload relevant SOPs, manuals, and compliance records.",
            })
            return gaps

        check_terms = ["sop", "procedure", "manual", "guideline", "policy", "standard"]
        missing_terms = [t for t in check_terms if not any(t in d.get("document_name", "").lower() or t in d.get("content", "").lower() for d in docs)]
        if missing_terms:
            gaps.append({
                "type": "incomplete_documentation",
                "severity": "medium",
                "category": "documentation",
                "detail": f"Missing document types: {', '.join(missing_terms)}.",
                "recommendation": f"Ensure {', '.join(missing_terms)} documents are available for '{target}'.",
            })

        if standard:
            std_lower = standard.lower()
            std_terms = std_lower.replace(" ", "_").split("_")
            if not any(any(st in d.get("content", "").lower() or st in d.get("document_name", "").lower() for st in std_terms) for d in docs):
                gaps.append({
                    "type": "standard_not_referenced",
                    "severity": "high",
                    "category": "documentation",
                    "detail": f"No documents reference standard '{standard}' for '{target}'.",
                    "recommendation": f"Update documentation to reference {standard} requirements.",
                })

        return gaps

    @staticmethod
    def _detect_inspection_gaps(target: str, entities: list[dict], docs: list[dict]) -> list[dict]:
        gaps: list[dict] = []
        has_inspection_doc = any(
            "inspect" in d.get("content", "").lower() or "inspection" in d.get("document_name", "").lower()
            for d in docs
        )
        if not has_inspection_doc:
            gaps.append({
                "type": "missing_inspection_procedure",
                "severity": "high",
                "category": "inspection",
                "detail": f"No inspection procedure found for '{target}'.",
                "recommendation": "Create or upload an inspection checklist and schedule.",
            })

        has_schedule_ref = any(
            "schedule" in d.get("content", "").lower() or "interval" in d.get("content", "").lower() or "frequency" in d.get("content", "").lower()
            for d in docs
        )
        if not has_schedule_ref:
            gaps.append({
                "type": "missing_inspection_schedule",
                "severity": "medium",
                "category": "inspection",
                "detail": f"No inspection schedule or interval defined for '{target}'.",
                "recommendation": "Define inspection frequency based on manufacturer recommendations and regulations.",
            })

        return gaps

    @staticmethod
    def _detect_procedure_gaps(target: str, docs: list[dict]) -> list[dict]:
        gaps: list[dict] = []
        procedure_keywords = ["step", "procedure", "instructions", "how to", "method", "process"]
        has_procedure = any(
            any(kw in d.get("content", "").lower() for kw in procedure_keywords)
            for d in docs
        )
        if not has_procedure:
            gaps.append({
                "type": "missing_procedure",
                "severity": "critical",
                "category": "procedure",
                "detail": f"No operational or maintenance procedure found for '{target}'.",
                "recommendation": "Develop and approve a standard operating procedure (SOP).",
            })
        return gaps

    @staticmethod
    def _detect_certification_gaps(target: str, entities: list[dict]) -> list[dict]:
        gaps: list[dict] = []
        cert_keywords = ["certified", "certification", "qualified", "approved", "calibrated"]
        has_cert = any(
            any(kw in e.get("name", "").lower() or kw in e.get("type", "").lower() for kw in cert_keywords)
            for e in entities
        )
        if not has_cert and not entities:
            gaps.append({
                "type": "unknown_certification_status",
                "severity": "medium",
                "category": "certification",
                "detail": f"Certification status for '{target}' is unknown.",
                "recommendation": "Verify and record certification/qualification status.",
            })
        return gaps

    @staticmethod
    def _build_gap_prompt(target: str, standard: str, gap_type: str, gaps: list[dict], docs: list[dict]) -> str:
        prompt = f"Analyze compliance gaps for '{target}'"
        if standard:
            prompt += f" against standard '{standard}'"
        prompt += f".\n\nIdentified gaps ({len(gaps)}):\n"
        for g in gaps:
            prompt += f"- [{g['severity'].upper()}] {g['type']}: {g['detail']}\n"

        if docs:
            prompt += "\nReference documents:\n"
            for d in docs[:3]:
                prompt += f"- {d['document_name']}: {d['content'][:200]}\n"

        prompt += (
            "\nProvide:\n"
            "1. Overall compliance gap assessment\n"
            "2. Prioritized remediation plan\n"
            "3. Estimated effort for each gap\n"
            "4. Suggested owner for each action item"
        )
        return prompt

    @staticmethod
    def _fallback_gap_summary(target: str, gaps: list[dict]) -> str:
        lines = [f"**Compliance Gap Summary — {target}**", ""]
        by_severity: dict[str, list[dict]] = {}
        for g in gaps:
            by_severity.setdefault(g.get("severity", "low"), []).append(g)

        for severity in ("critical", "high", "medium", "low"):
            items = by_severity.get(severity, [])
            if items:
                lines.append(f"### {severity.title()} Priority")
                for i, g in enumerate(items, 1):
                    lines.append(f"{i}. **{g['type'].replace('_', ' ').title()}**")
                    lines.append(f"   - {g['detail']}")
                    lines.append(f"   - *Recommendation:* {g.get('recommendation', 'Review and address.')}")
                lines.append("")

        lines.append("### Next Steps")
        lines.append("1. Address critical and high-severity gaps immediately")
        lines.append("2. Assign owners for each gap")
        lines.append("3. Set target completion dates")
        lines.append("4. Schedule follow-up audit")

        return "\n".join(lines)


class ComplianceRecommendationTool(FrameworkTool):
    """Generates compliance improvement recommendations."""

    metadata = ToolMetadata(
        tool_id="compliance_recommendation",
        name="Compliance Recommendation",
        description=(
            "Generates actionable recommendations to improve compliance "
            "based on identified findings, gaps, or audit results."
        ),
        category=ToolCategory.REPORTING,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "finding": {"type": "string", "description": "Compliance finding, gap, or violation description"},
                "standard": {"type": "string", "description": "Applicable standard or regulation"},
                "severity": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low"],
                    "description": "Severity of the finding (default medium)",
                },
                "target": {"type": "string", "description": "Equipment, area, or process affected"},
            },
            "required": ["finding"],
        },
    )

    def __init__(self, llm_provider: Any = None) -> None:
        self._llm = llm_provider

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        finding = params.get("finding", "")
        standard = params.get("standard", "")
        severity = params.get("severity", "medium")
        target = params.get("target", "")

        if not finding.strip():
            return ToolResult(data=None, error="finding is required.")

        prompt = (
            f"Generate compliance improvement recommendations for the following finding:\n"
            f"Finding: {finding}\n"
        )
        if standard:
            prompt += f"Standard/Regulation: {standard}\n"
        if target:
            prompt += f"Affected: {target}\n"
        prompt += f"Severity: {severity}\n\n"
        prompt += (
            "Provide:\n"
            "1. Immediate corrective actions\n"
            "2. Long-term preventive measures\n"
            "3. Required resources (documents, training, tools)\n"
            "4. Estimated timeline\n"
            "5. Verification method\n"
            "Format as a structured action plan."
        )

        recommendation_text = ""
        if self._llm is not None:
            try:
                result = await self._llm.generate(prompt=prompt)
                recommendation_text = result if isinstance(result, str) else (
                    result.get("text", "") if isinstance(result, dict) else str(result)
                )
            except Exception as exc:
                recommendation_text = self._fallback_recommendation(finding, standard, severity, target)
                context.add_reasoning_step(f"ComplianceRecommendationTool: LLM unavailable — {exc}")
        else:
            recommendation_text = self._fallback_recommendation(finding, standard, severity, target)

        context.add_reasoning_step(
            f"ComplianceRecommendationTool: recommendation for finding (severity={severity})"
        )

        return ToolResult(
            data={
                "finding": finding,
                "standard": standard or "general",
                "severity": severity,
                "target": target or "general",
                "recommendation": recommendation_text,
            },
        )

    @staticmethod
    def _fallback_recommendation(finding: str, standard: str, severity: str, target: str) -> str:
        lines = [
            f"## Compliance Action Plan",
            "",
            f"**Finding:** {finding}",
        ]
        if standard:
            lines.append(f"**Standard:** {standard}")
        if target:
            lines.append(f"**Affected:** {target}")
        lines.append(f"**Severity:** {severity.title()}")
        lines.append("")

        urgency = {
            "critical": "Immediate (within 24 hours)",
            "high": "Short-term (within 1 week)",
            "medium": "Medium-term (within 1 month)",
            "low": "Long-term (within 3 months)",
        }

        lines.append(f"**Target Resolution:** {urgency.get(severity, 'As soon as practical')}")
        lines.append("")

        lines.append("### Immediate Corrective Actions")
        lines.append("1. Acknowledge and document the finding")
        lines.append("2. Implement containment measures to prevent escalation")
        lines.append("3. Notify relevant stakeholders")
        lines.append("")

        lines.append("### Long-Term Preventive Measures")
        lines.append("1. Perform root cause analysis")
        lines.append("2. Update relevant procedures and documentation")
        lines.append("3. Provide additional training to personnel")
        lines.append("4. Implement monitoring and verification processes")
        lines.append("")

        lines.append("### Required Resources")
        lines.append("- Updated documentation / SOPs")
        lines.append("- Personnel training")
        lines.append("- Possible equipment modifications")
        lines.append("")

        lines.append("### Verification Method")
        lines.append("- Internal audit / inspection")
        lines.append("- Document review")
        lines.append("- Follow-up verification check")
        lines.append("")
        lines.append("> *This is a template. Adjust based on specific finding details and site requirements.*")

        return "\n".join(lines)
