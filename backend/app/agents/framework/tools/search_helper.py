"""Shared search helpers for tools that query both graph and document stores.

Eliminates the duplicated try/except/logging/reasoning-step pattern
that previously appeared in every search-based tool across the
codebase.

Supports an optional ``RetrievalCacheEntry`` to avoid re-retrieving
data that was already fetched in a previous query within the same
conversation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.agents.framework.tool import ToolResult

if TYPE_CHECKING:
    from app.agents.framework.memory.retrieval_cache import RetrievalCacheEntry
    from app.agents.framework.tools.context import ToolContext


@dataclass
class HybridSearchResult:
    """Normalised result from searching both graph and document stores."""

    documents: list[dict] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    total_documents: int = 0
    total_entities: int = 0


async def search_hybrid(
    *,
    query: str,
    graph_svc: Any | None = None,
    hybrid: Any | None = None,
    top_k: int = 10,
    source: str = "all",
    tool_name: str = "Tool",
    context: ToolContext | None = None,
    graph_query_augment: str = "",
    doc_query_augment: str = "",
    entity_type: str | None = None,
    graph_item_fn: callable | None = None,
    doc_item_fn: callable | None = None,
    cache: RetrievalCacheEntry | None = None,
) -> HybridSearchResult:
    """Search graph entities and/or documents for *query*.

    Parameters
    ----------
    query:
        The search string.
    graph_svc:
        ``GraphQueryService`` instance (or ``None`` to skip).
    hybrid:
        ``HybridRetriever`` instance (or ``None`` to skip).
    top_k:
        Maximum results from each source (clamped to 50).
    source:
        ``"all"``, ``"graph"``, or ``"documents"``.
    tool_name:
        Used in reasoning-step messages (e.g. ``"IncidentSearchTool"``).
    context:
        ``ToolContext`` for logging reasoning steps.
    graph_query_augment:
        Extra text appended to the graph query.
    doc_query_augment:
        Extra text appended to the document query.
    entity_type:
        Optional entity type filter for graph search.
    graph_item_fn:
        Optional callable ``(entity) -> dict`` to build graph-result dicts.
        Default: builds id/name/type/confidence/source_document.
    doc_item_fn:
        Optional callable ``(item) -> dict`` to build document-result dicts.
        Default: builds content/score/document_name/document_id/page_number/source.

    Returns
    -------
    A ``HybridSearchResult`` with ``documents`` and ``entities`` lists.
    Never raises — all exceptions are caught and logged as reasoning steps.
    """
    if not query.strip():
        return HybridSearchResult()

    top_k = min(top_k, 50)

    # ── Cache check ──────────────────────────────────────────────
    # If the cache already covers every term in this query we can
    # return the cached documents/entities directly without another
    # round-trip to the graph or vector store.
    if cache is not None and cache.is_query_cached(query):
        _add_step(context, f"{tool_name}: full cache hit for {query!r}")
        return HybridSearchResult(
            documents=list(cache.document_chunks),
            entities=list(cache.graph_entities),
            total_documents=len(cache.document_chunks),
            total_entities=len(cache.graph_entities),
        )

    result = HybridSearchResult()

    # --- Graph search ---
    if source in ("all", "graph") and graph_svc is not None:
        gq = query + (" " + graph_query_augment if graph_query_augment else "")
        try:
            entities, total = await graph_svc.search_entities(
                query=gq, limit=top_k, entity_type=entity_type or None,
            )
            for e in entities:
                if graph_item_fn is not None:
                    result.entities.append(graph_item_fn(e))
                else:
                    result.entities.append({
                        "id": e.id,
                        "name": e.name,
                        "type": e.type,
                        "confidence": e.confidence,
                        "source_document": e.source_document,
                    })
            result.total_entities = len(result.entities)
        except Exception as exc:
            _add_step(context, f"{tool_name}: graph search failed — {exc}")

    # --- Document search ---
    if source in ("all", "documents") and hybrid is not None:
        dq = query + (" " + doc_query_augment if doc_query_augment else "")
        try:
            unified = await hybrid.retrieve(query=dq, top_k=top_k)
            for item in unified.items:
                if doc_item_fn is not None:
                    result.documents.append(doc_item_fn(item))
                else:
                    result.documents.append({
                        "content": item.content[:2000],
                        "score": item.score,
                        "document_name": item.document_name,
                        "document_id": item.document_id,
                        "page_number": getattr(item, "page_number", None),
                        "source": getattr(item, "source", ""),
                    })
            result.total_documents = len(result.documents)
        except Exception as exc:
            _add_step(context, f"{tool_name}: document retrieval failed — {exc}")

    # ── Merge fresh results into cache ──────────────────────────
    if cache is not None and (result.documents or result.entities):
        cache.merge_search_results(query, result.documents, result.entities)
        _add_step(
            context,
            f"{tool_name}: cached {result.total_documents} doc(s), "
            f"{result.total_entities} entity(ies)",
        )

    _add_step(
        context,
        f"{tool_name}: {result.total_documents} doc(s), "
        f"{result.total_entities} entity(ies) for {query!r}",
    )
    return result


def _add_step(context: ToolContext | None, msg: str) -> None:
    if context is not None:
        context.add_reasoning_step(msg)
