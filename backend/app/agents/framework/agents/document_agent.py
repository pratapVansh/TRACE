"""Document Analysis Agent — the first production AI agent for TRACE."""

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
    "**Upload relevant documents** (SOPs, P&IDs, manuals, inspection reports) "
    "to the TRACE document store and wait for indexing to complete.",
    "**Rephrase your query** using exact document titles, equipment tags, or "
    "procedure names as they appear in the uploaded files.",
    "**Check the document list** to confirm the files covering this topic "
    "have been successfully processed (status = Ready).",
]

logger = logging.getLogger(__name__)

_DOCUMENT_TASKS = [
    "document",
    "summarize",
    "summarisation",
    "sop",
    "p&id",
    "manual",
    "procedure",
    "specification",
    "safety",
    "ppe",
    "valve",
    "equipment",
    "maintenance interval",
    "operating parameters",
    "terminology",
    "compare documents",
]


class DocumentAnalysisAgent(BaseAgent):
    """Answers questions about uploaded industrial documents.

    Capabilities:
    - semantic search across documents
    - summarization of document content
    - metadata lookup
    - document comparison
    - citation generation
    - confidence scoring
    """

    agent_id = "document_analysis"
    name = "Document Analysis Agent"
    description = (
        "Answers questions about uploaded industrial documents "
        "such as SOPs, P&IDs, manuals, and specifications."
    )
    supported_tasks = _DOCUMENT_TASKS
    required_permissions: set[Permission] = {Permission.DOCUMENTS_READ}

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

        citations: list[Citation] = []
        confidence = 0.0

        # Step 1 — Search for relevant documents
        search_result = await self._call_tool("document_search", {
            "query": question,
            "top_k": 10,
        }, tool_ctx, tools_used)

        documents: list[dict] = []
        if search_result.success and search_result.data:
            documents = search_result.data.get("documents", [])
            raw_citations = search_result.data.get("citations", [])
            citations = [Citation(**c) for c in raw_citations]
            confidence = self._compute_confidence(documents)

            wm = context.working_memory
            if wm is not None:
                for doc in documents:
                    wm.set_temp(f"doc_{doc.get('document_id', '')}", doc)

        # ── Zero-evidence guard ─────────────────────────────────
        if not has_evidence(search_result):
            return no_evidence_response(
                agent_name=self.name,
                question=question,
                tools_used=tools_used,
                suggestions=_NO_EVIDENCE_SUGGESTIONS,
            )

        # Step 2 — Decide next action based on intent
        intent = self._classify_intent(question)
        answer = ""

        if intent == "metadata" and documents:
            doc_ids = list({d.get("document_id") for d in documents if d.get("document_id")})
            if doc_ids:
                meta_result = await self._call_tool("document_metadata", {
                    "document_id": doc_ids[0],
                }, tool_ctx, tools_used)
                if meta_result.success and meta_result.data:
                    meta = meta_result.data
                    answer = (
                        f"**{meta.get('filename', 'Document')}**\n"
                        f"- Type: {meta.get('doc_type', 'N/A')}\n"
                        f"- Status: {meta.get('status', 'N/A')}\n"
                        f"- Size: {self._format_size(meta.get('file_size_bytes', 0))}\n"
                        f"- Department: {meta.get('department', 'N/A')}\n"
                        f"- Uploaded: {meta.get('created_at', 'N/A')}"
                    )

        elif intent == "comparison" and len(documents) >= 1:
            doc_sets = self._group_by_document(documents)
            keys = list(doc_sets.keys())

            if len(keys) >= 2:
            # If we got at least 2 distinct documents — compare them
                doc_a_id = keys[0]
                doc_b_id = keys[1]
                doc_a_content = "\n".join(
                    d.get("content", "") for d in doc_sets[doc_a_id]
                )
                doc_b_content = "\n".join(
                    d.get("content", "") for d in doc_sets[doc_b_id]
                )
                doc_a_name = doc_sets[doc_a_id][0].get("document_name", doc_a_id)
                doc_b_name = doc_sets[doc_b_id][0].get("document_name", doc_b_id)

                comp_result = await self._call_tool("document_comparison", {
                    "doc_a_name": doc_a_name,
                    "doc_a_content": doc_a_content,
                    "doc_b_name": doc_b_name,
                    "doc_b_content": doc_b_content,
                }, tool_ctx, tools_used)
                if comp_result.success and comp_result.data:
                    answer = comp_result.data.get("comparison", "")
            else:
                # Only one document — just summarise
                intent = "summary"

        if not answer or intent in ("summary", "general"):
            summary_result = await self._call_tool("document_summary", {
                "query": question,
                "documents": documents,
                "format": "detailed" if len(documents) > 3 else "concise",
            }, tool_ctx, tools_used)
            if summary_result.success and summary_result.data:
                answer = summary_result.data.get("summary", "")

        if not answer:
            answer = self._fallback_answer(documents, question)

        wm = context.working_memory
        if wm is not None:
            wm.set_temp("final_answer", answer)
            wm.set_temp("confidence", confidence)

        _search_dict = search_result.data if search_result.success else None
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

    # ── Internals ──────────────────────────────────────────────

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
        q = question.lower()
        if any(w in q for w in ("metadata", "info about", "details", "what type", "when was", "who uploaded", "file info")):
            return "metadata"
        if any(w in q for w in ("compare", "difference", "versus", "vs ", "similarities", "which is better")):
            return "comparison"
        if any(w in q for w in ("summarize", "summary", "overview", "what is this", "tell me about", "explain")):
            return "summary"
        return "general"

    @staticmethod
    def _compute_confidence(documents: list[dict]) -> float:
        if not documents:
            return 0.0
        scores = [d.get("score", 0.0) for d in documents if d.get("score") is not None]
        if not scores:
            return 0.3
        avg = sum(scores) / len(scores)
        return min(avg, 1.0)

    @staticmethod
    def _group_by_document(documents: list[dict]) -> dict[str, list[dict]]:
        groups: dict[str, list[dict]] = {}
        for d in documents:
            did = d.get("document_id") or d.get("document_name", "unknown")
            if did not in groups:
                groups[did] = []
            groups[did].append(d)
        return groups

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    @staticmethod
    def _fallback_answer(documents: list[dict], question: str) -> str:
        if not documents:
            return (
                "I could not find any relevant documents to answer your question. "
                "Please try uploading documents or rephrasing your query."
            )

        doc_names = list({
            d.get("document_name", "Unknown") for d in documents
        })
        parts = [
            f"I found information in {len(doc_names)} document(s): "
            + ", ".join(doc_names[:5]),
            "",
            "Here are the most relevant excerpts:",
        ]
        for i, d in enumerate(documents[:3]):
            content = d.get("content", "")
            preview = content[:300] + "..." if len(content) > 300 else content
            parts.append(f"\n--- Excerpt {i + 1} ---\n{preview}")

        if len(documents) > 3:
            parts.append(f"\n[... {len(documents) - 3} more excerpt(s) available]")

        return "\n".join(parts)
