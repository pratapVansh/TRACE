"""Document-analysis tools for the DocumentAnalysisAgent.

These tools reuse existing services (HybridRetriever, DocumentService,
LLMProvider) and never access repositories directly.
"""

import uuid
from typing import Any

from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.base import FrameworkTool
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.schemas import ToolCategory, ToolMetadata
from app.schemas.hybrid import UnifiedContext, UnifiedContextItem
from app.schemas.rag import Citation


class DocumentSearchTool(FrameworkTool):
    """Searches uploaded documents using HybridRetriever."""

    metadata = ToolMetadata(
        tool_id="document_search",
        name="Document Search",
        description=(
            "Performs semantic + keyword search across uploaded "
            "industrial documents.  Returns ranked chunks with scores."
        ),
        category=ToolCategory.DOCUMENT,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "top_k": {"type": "integer", "description": "Number of results (default 10)"},
            },
            "required": ["query"],
        },
    )

    def __init__(self, hybrid_retriever: Any = None) -> None:
        self._hybrid_retriever = hybrid_retriever

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        query = params.get("query", "")
        top_k = params.get("top_k", 10)

        if not query.strip():
            return ToolResult(data=None, error="Search query cannot be empty.")
        if self._hybrid_retriever is None:
            return ToolResult(data=None, error="Hybrid retriever is not available.")

        unified: UnifiedContext = await self._hybrid_retriever.retrieve(
            query=query, top_k=top_k,
        )
        items = unified.items if hasattr(unified, "items") else []
        documents = [item for item in items if item.score > 0]

        citations = [
            Citation(
                document_name=d.document_name,
                chunk_content=d.content,
                score=d.score,
                similarity_score=d.score,
                page_number=d.page_number,
            )
            for d in documents
        ]

        context.add_reasoning_step(
            f"DocumentSearchTool: found {len(documents)} results for query={query!r}"
        )

        return ToolResult(
            data={
                "documents": [
                    {
                        "content": d.content,
                        "score": d.score,
                        "source": d.source,
                        "document_id": d.document_id,
                        "document_name": d.document_name,
                        "page_number": d.page_number,
                    }
                    for d in documents
                ],
                "citations": [c.model_dump() for c in citations],
                "total": len(documents),
            },
            metadata={"citation_count": len(citations)},
        )


class DocumentSummaryTool(FrameworkTool):
    """Generates a summary of document content using the LLM."""

    metadata = ToolMetadata(
        tool_id="document_summary",
        name="Document Summary",
        description="Produces a summary of document content tailored to the user's question.",
        category=ToolCategory.DOCUMENT,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Original user question"},
                "documents": {
                    "type": "array",
                    "description": "List of document content blocks",
                    "items": {"type": "object"},
                },
                "format": {
                    "type": "string",
                    "enum": ["concise", "detailed", "bullet_points"],
                },
            },
            "required": ["query", "documents"],
        },
    )

    def __init__(self, llm_provider: Any = None) -> None:
        self._llm = llm_provider

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        query = params.get("query", "")
        documents: list[dict] = params.get("documents", [])
        fmt = params.get("format", "concise")

        if not documents:
            return ToolResult(data=None, error="No documents provided for summarization.")

        text_parts = [d.get("content", "") for d in documents if d.get("content")]
        context_text = "\n\n---\n\n".join(text_parts)

        if self._llm is None:
            summary = "\n\n".join(text_parts[:3])
            if len(text_parts) > 3:
                summary += f"\n\n[... {len(text_parts) - 3} more section(s) omitted]"
            return ToolResult(data={"summary": summary, "format": fmt})

        style_map = {
            "concise": "a single paragraph (2-3 sentences)",
            "detailed": "several paragraphs covering all key points",
            "bullet_points": "bullet-point format",
        }
        prompt = (
            f"Answer the following question based on the document content below.\n\n"
            f"Question: {query}\n\n"
            f"Document content:\n{context_text}\n\n"
            f"Provide your answer in {style_map.get(fmt, 'a concise paragraph')}."
        )
        try:
            answer = await self._llm.generate(prompt=prompt)
            context.add_reasoning_step(f"DocumentSummaryTool: generated {fmt} summary")
            return ToolResult(data={"summary": answer, "format": fmt})
        except Exception as exc:
            return ToolResult(data=None, error=f"LLM summarization failed: {exc}")


class DocumentMetadataTool(FrameworkTool):
    """Retrieves metadata about an uploaded document."""

    metadata = ToolMetadata(
        tool_id="document_metadata",
        name="Document Metadata",
        description="Returns filename, type, status, size, and timestamps for a document.",
        category=ToolCategory.DOCUMENT,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "UUID of the document"},
            },
            "required": ["document_id"],
        },
    )

    def __init__(self, document_service: Any = None) -> None:
        self._document_service = document_service

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        doc_id = params.get("document_id", "")
        if not doc_id.strip():
            return ToolResult(data=None, error="document_id is required.")
        if self._document_service is None:
            return ToolResult(data=None, error="Document service is not available.")

        try:
            detail = await self._document_service.get_document(
                document_id=uuid.UUID(doc_id),
            )
            context.add_reasoning_step(f"DocumentMetadataTool: metadata for {doc_id}")
            return ToolResult(
                data={
                    "id": str(detail.id),
                    "filename": detail.original_filename,
                    "doc_type": detail.doc_type,
                    "status": detail.status,
                    "mime_type": detail.mime_type,
                    "file_size_bytes": detail.file_size_bytes,
                    "version": detail.version_no,
                    "department": detail.department,
                    "category": detail.document_category,
                    "uploaded_by": str(detail.uploaded_by) if detail.uploaded_by else None,
                    "uploaded_by_name": detail.uploaded_by_name,
                    "created_at": detail.created_at.isoformat() if hasattr(detail.created_at, "isoformat") else str(detail.created_at),
                    "updated_at": detail.updated_at.isoformat() if hasattr(detail.updated_at, "isoformat") else str(detail.updated_at),
                },
            )
        except Exception as exc:
            return ToolResult(data=None, error=f"Failed to retrieve metadata: {exc}")


class DocumentComparisonTool(FrameworkTool):
    """Compares two sets of document content side-by-side."""

    metadata = ToolMetadata(
        tool_id="document_comparison",
        name="Document Comparison",
        description=(
            "Compares the content of two documents and highlights "
            "key similarities and differences."
        ),
        category=ToolCategory.DOCUMENT,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "doc_a_name": {"type": "string", "description": "Name of the first document"},
                "doc_a_content": {"type": "string", "description": "Content of the first document"},
                "doc_b_name": {"type": "string", "description": "Name of the second document"},
                "doc_b_content": {"type": "string", "description": "Content of the second document"},
            },
            "required": ["doc_a_name", "doc_a_content", "doc_b_name", "doc_b_content"],
        },
    )

    def __init__(self, llm_provider: Any = None) -> None:
        self._llm = llm_provider

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        doc_a_name = params.get("doc_a_name", "Document A")
        doc_a_content = params.get("doc_a_content", "")
        doc_b_name = params.get("doc_b_name", "Document B")
        doc_b_content = params.get("doc_b_content", "")

        if not doc_a_content or not doc_b_content:
            return ToolResult(data=None, error="Both documents must have content.")

        comparison = ""
        if self._llm is not None:
            prompt = (
                f"Compare the following two documents and highlight "
                f"key similarities and differences.\n\n"
                f"--- Document A ({doc_a_name}) ---\n{doc_a_content[:3000]}\n\n"
                f"--- Document B ({doc_b_name}) ---\n{doc_b_content[:3000]}\n\n"
                f"Provide a structured comparison covering purpose, scope, "
                f"key details, and any notable differences."
            )
            try:
                comparison = await self._llm.generate(prompt=prompt)
            except Exception:
                comparison = ""

        context.add_reasoning_step(
            f"DocumentComparisonTool: compared {doc_a_name} vs {doc_b_name}"
        )

        return ToolResult(
            data={
                "document_a": {"name": doc_a_name, "content_preview": doc_a_content[:500]},
                "document_b": {"name": doc_b_name, "content_preview": doc_b_content[:500]},
                "comparison": comparison,
            },
        )
