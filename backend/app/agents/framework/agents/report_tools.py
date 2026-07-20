"""Report-generation tools.

Reuses HybridRetriever, LLMProvider, and GraphQueryService.
"""

from typing import Any

from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.base import FrameworkTool
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.schemas import ToolCategory, ToolMetadata

_REPORT_TYPES = ["incident", "maintenance", "compliance"]


class ReportGenerationTool(FrameworkTool):
    """Generates structured reports (incident, maintenance, compliance)."""

    metadata = ToolMetadata(
        tool_id="report_generation",
        name="Report Generation",
        description=(
            "Generates structured reports including incident reports, "
            "maintenance reports, and compliance reports. "
            "Uses available data to populate the report."
        ),
        category=ToolCategory.REPORTING,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "enum": ["incident", "maintenance", "compliance"],
                    "description": "Type of report to generate",
                },
                "title": {"type": "string", "description": "Report title"},
                "context": {"type": "string", "description": "Context, findings, or data to include"},
                "author": {"type": "string", "description": "Report author (default 'AI Agent')"},
            },
            "required": ["report_type", "title", "context"],
        },
    )

    def __init__(self, llm_provider: Any = None, hybrid_retriever: Any = None) -> None:
        self._llm = llm_provider
        self._hybrid = hybrid_retriever

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        report_type = params.get("report_type", "")
        title = params.get("title", "")
        report_context = params.get("context", "")
        author = params.get("author", "AI Agent")

        if report_type not in _REPORT_TYPES:
            return ToolResult(data=None, error=f"Unsupported report type: {report_type}")
        if not title.strip() or not report_context.strip():
            return ToolResult(data=None, error="title and context are required.")

        # ── Accumulated context from conversation ───────────────
        conversation_summary = context.build_conversation_summary()
        accumulated_findings = context.build_accumulated_findings()
        accumulated_evidence = context.build_accumulated_evidence()

        grounding_docs: list[str] = []
        if self._hybrid is not None:
            try:
                # Use the accumulated context to inform retrieval
                query_parts = [title, report_context, report_type]
                if conversation_summary:
                    query_parts.append(conversation_summary[:200])
                unified = await self._hybrid.retrieve(
                    query=" ".join(query_parts), top_k=5,
                )
                grounding_docs = [
                    f"[{item.document_name}] {item.content[:500]}"
                    for item in unified.items
                ]
            except Exception:
                pass

        prompt = self._build_report_prompt(
            report_type, title, report_context, author, grounding_docs,
            conversation_summary=conversation_summary,
            accumulated_findings=accumulated_findings,
            accumulated_evidence=accumulated_evidence,
        )

        report = ""
        if self._llm is not None:
            try:
                result = await self._llm.generate(prompt=prompt)
                report = result if isinstance(result, str) else (
                    result.get("text", "") if isinstance(result, dict) else str(result)
                )
            except Exception as exc:
                report = self._fallback_report(report_type, title, report_context, author)
                context.add_reasoning_step(f"ReportGenerationTool: LLM unavailable — {exc}")
        else:
            report = self._fallback_report(report_type, title, report_context, author)

        context.add_reasoning_step(f"ReportGenerationTool: {report_type} report generated ({len(report)} chars)")
        return ToolResult(data={
            "report_type": report_type, "title": title,
            "report": report, "author": author,
            "grounding_documents": len(grounding_docs),
        })

    @staticmethod
    def _build_report_prompt(
        rtype: str, title: str, ctx: str, author: str, docs: list[str],
        *,
        conversation_summary: str = "",
        accumulated_findings: str = "",
        accumulated_evidence: str = "",
    ) -> str:
        prompt = f"Generate a {rtype} report.\nTitle: {title}\nAuthor: {author}\n\nUser notes:\n{ctx}\n"

        if conversation_summary:
            prompt += f"\n## Conversation History\n{conversation_summary}\n"
        if accumulated_findings:
            prompt += f"\n## Prior Findings\n{accumulated_findings}\n"
        if accumulated_evidence:
            prompt += f"\n## Prior Evidence\n{accumulated_evidence}\n"

        if docs:
            prompt += "\n## Reference Documents\n" + "\n".join(docs[:3]) + "\n"
        templates = {
            "incident": (
                "\nSTRICT RULES:\n"
                "- Never invent root causes, failure modes, or impact assessments.\n"
                "- Every claim MUST be grounded in the reference data.\n"
                "- If evidence is missing for a section, write: 'No supporting evidence found.'\n"
                "Format as:\n"
                "## Incident Report\n### Incident Details\n- Date/Time\n- Location\n- Equipment\n"
                "### Description\n### Findings\n### Supporting Evidence\n### Actions Taken\n"
                "### Attachments/References"
            ),
            "maintenance": (
                "\nSTRICT RULES:\n"
                "- Never invent part numbers, labor hours, schedules, or test results.\n"
                "- Only include information present in the reference data.\n"
                "- If evidence is missing, write: 'No supporting evidence found.'\n"
                "Format as:\n"
                "## Maintenance Report\n### Equipment Info\n### Maintenance Type\n### Work Performed\n"
                "### Findings\n### Supporting Evidence"
            ),
            "compliance": (
                "\nSTRICT RULES:\n"
                "- Never invent non-compliances or corrective actions not in evidence.\n"
                "- Every finding MUST cite specific reference documents.\n"
                "- If evidence is missing, write: 'No supporting evidence found.'\n"
                "Format as:\n"
                "## Compliance Report\n### Scope\n### Standards Referenced\n### Findings\n"
                "### Evidence\n### Recommendations"
            ),
        }
        prompt += templates.get(rtype, "")
        return prompt

    @staticmethod
    def _fallback_report(rtype: str, title: str, ctx: str, author: str) -> str:
        sect_templates = {
            "incident": [
                "### Incident Details", "- Date/Time: [Date]", "- Location: [Location]",
                "- Equipment: [Equipment]",
                "### Description", ctx,
                "### Root Cause", "[To be determined]",
                "### Impact", "[To be assessed]",
                "### Corrective Actions", "1. [Action 1]\n2. [Action 2]",
                "### Preventive Measures", "1. [Measure 1]\n2. [Measure 2]",
            ],
            "maintenance": [
                "### Equipment Info", f"Equipment: {title}",
                "### Maintenance Type", "[Preventive/Corrective]",
                "### Work Performed", ctx,
                "### Parts Used", "[List parts]",
                "### Test Results", "[Pass/Fail]",
                "### Recommendations", "[Recommendations]",
                "### Next Scheduled Maintenance", "[Date]",
            ],
            "compliance": [
                "### Scope", ctx,
                "### Standards Referenced", "[Applicable standards]",
                "### Findings", "[Findings]",
                "### Non-Compliances", "[List non-compliances]",
                "### Corrective Actions", "1. [Action 1]\n2. [Action 2]",
                "### Recommendations", "[Recommendations]",
            ],
        }
        sections = sect_templates.get(rtype, ["### Details", ctx])
        lines = [f"# {title}", f"**Type:** {rtype.title()} Report", f"**Author:** {author}", ""]
        for s in sections:
            lines.append(s)
        lines.extend(["", "---", "*Report generated by AI Agent.*"])
        return "\n".join(lines)


class ExecutiveSummaryTool(FrameworkTool):
    """Generates concise executive summaries from reports or data."""

    metadata = ToolMetadata(
        tool_id="executive_summary",
        name="Executive Summary",
        description=(
            "Generates a concise executive summary from a report, "
            "findings, or data. Suitable for management review."
        ),
        category=ToolCategory.REPORTING,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Report content or findings to summarize"},
                "max_bullets": {"type": "integer", "description": "Max bullet points (default 5)"},
                "audience": {
                    "type": "string",
                    "enum": ["executive", "technical", "general"],
                    "description": "Target audience (default executive)",
                },
            },
            "required": ["content"],
        },
    )

    def __init__(self, llm_provider: Any = None) -> None:
        self._llm = llm_provider

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        content = params.get("content", "")
        max_bullets = min(params.get("max_bullets", 5), 10)
        audience = params.get("audience", "executive")

        if not content.strip():
            return ToolResult(data=None, error="content is required.")

        prompt = (
            f"Generate a {audience}-focused executive summary from the following content. "
            f"Use at most {max_bullets} bullet points. Keep each point concise.\n\n"
            f"Content:\n{content[:4000]}"
        )

        summary = ""
        if self._llm is not None:
            try:
                result = await self._llm.generate(prompt=prompt)
                summary = result if isinstance(result, str) else (
                    result.get("text", "") if isinstance(result, dict) else str(result)
                )
            except Exception as exc:
                summary = self._fallback_summary(content, max_bullets)
                context.add_reasoning_step(f"ExecutiveSummaryTool: LLM unavailable — {exc}")
        else:
            summary = self._fallback_summary(content, max_bullets)

        context.add_reasoning_step(f"ExecutiveSummaryTool: summary generated ({len(summary)} chars)")
        return ToolResult(data={
            "summary": summary, "audience": audience, "max_bullets": max_bullets,
        })

    @staticmethod
    def _fallback_summary(content: str, max_bullets: int) -> str:
        sentences = [s.strip() for s in content.replace("\n", " ").split(".") if len(s.strip()) > 20]
        lines = ["## Executive Summary", ""]
        for i, s in enumerate(sentences[:max_bullets], 1):
            lines.append(f"{i}. {s}.")
        lines.extend(["", "---", "*Summary generated by AI Agent.*"])
        return "\n".join(lines)


class MarkdownReportTool(FrameworkTool):
    """Formats content into a well-structured markdown report."""

    metadata = ToolMetadata(
        tool_id="markdown_report",
        name="Markdown Report",
        description=(
            "Formats provided content into a clean, well-structured "
            "markdown report with proper headings and sections."
        ),
        category=ToolCategory.REPORTING,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Report title"},
                "sections": {
                    "type": "string",
                    "description": "JSON or newline-separated section data. "
                                   "Format: 'Section Title:::content' per section.",
                },
                "include_toc": {"type": "boolean", "description": "Include table of contents (default false)"},
            },
            "required": ["title", "sections"],
        },
    )

    def __init__(self, llm_provider: Any = None) -> None:
        self._llm = llm_provider

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        title = params.get("title", "")
        sections_raw = params.get("sections", "")
        include_toc = params.get("include_toc", False)

        if not title.strip() or not sections_raw.strip():
            return ToolResult(data=None, error="title and sections are required.")

        paragraphs = sections_raw.split(":::")
        sections: list[tuple[str, str]] = []
        for i in range(0, len(paragraphs) - 1, 2):
            heading = paragraphs[i].strip()
            body = paragraphs[i + 1].strip() if i + 1 < len(paragraphs) else ""
            sections.append((heading, body))
        if not sections:
            sections = [("Content", sections_raw)]

        if self._llm is not None and len(sections_raw) > 500:
            try:
                prompt = (
                    f"Format the following content into a professional markdown report "
                    f"titled '{title}'."
                )
                if include_toc:
                    prompt += " Include a table of contents."
                prompt += f"\n\nContent:\n{sections_raw[:4000]}"
                result = await self._llm.generate(prompt=prompt)
                formatted = result if isinstance(result, str) else (
                    result.get("text", "") if isinstance(result, dict) else str(result)
                )
                return ToolResult(data={"title": title, "report": formatted, "include_toc": include_toc})
            except Exception:
                pass

        report = self._format_markdown(title, sections, include_toc)
        context.add_reasoning_step(f"MarkdownReportTool: report formatted ({len(report)} chars)")
        return ToolResult(data={
            "title": title, "report": report,
            "section_count": len(sections), "include_toc": include_toc,
        })

    @staticmethod
    def _format_markdown(title: str, sections: list[tuple[str, str]], toc: bool) -> str:
        lines = [f"# {title}", ""]
        if toc:
            lines.append("## Table of Contents")
            for heading, _ in sections:
                anchor = heading.lower().replace(" ", "-").replace("/", "")
                lines.append(f"- [{heading}](#{anchor})")
            lines.append("")
        for heading, body in sections:
            lines.append(f"## {heading}")
            lines.append(body)
            lines.append("")
        lines.append("---")
        lines.append("*Report generated by AI Agent.*")
        return "\n".join(lines)
