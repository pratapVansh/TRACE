from fastapi import APIRouter, Depends, HTTPException
try:
    from qdrant_client.models import FieldCondition, Filter, MatchValue, Range  # noqa: PLC0415
    _QD_SEARCH_AVAILABLE = True
except ImportError:
    FieldCondition = object  # type: ignore[assignment,misc]
    Filter = object
    MatchValue = object
    Range = object
    _QD_SEARCH_AVAILABLE = False

from app.api.authorization import require_permission
from app.api.deps import get_graph_query_optional, get_ranking_service, get_vector_store
from app.core.authorization import PERMISSIONS
from app.core.config import settings
from app.middleware.rate_limit import RateLimiter
from app.schemas.auth import UserMeResponse
from app.schemas.vector import (
    RankingWeights,
    SearchFilter,
    SearchMode,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from app.services.embedding_service import _encode_batch_async
from app.services.ranking_service import RankingService
from app.services.vector_store import VectorStore, VectorStoreOperationError

router = APIRouter(prefix="/search", tags=["search"])

search_rate_limiter = RateLimiter(
    max_requests=settings.search_rate_limit_max,
    window_seconds=settings.search_rate_limit_window_seconds,
)


def _build_qdrant_filter(filters: SearchFilter) -> Filter | None:
    conditions: list[FieldCondition] = []

    if filters.document_id:
        conditions.append(
            FieldCondition(key="document_id", match=MatchValue(value=filters.document_id))
        )

    if filters.filename:
        conditions.append(
            FieldCondition(key="filename", match=MatchValue(value=filters.filename))
        )

    if filters.language:
        conditions.append(
            FieldCondition(key="metadata.language", match=MatchValue(value=filters.language))
        )

    if filters.document_type:
        conditions.append(
            FieldCondition(key="document_type", match=MatchValue(value=filters.document_type))
        )

    if filters.uploaded_by:
        conditions.append(
            FieldCondition(key="uploaded_by", match=MatchValue(value=filters.uploaded_by))
        )

    date_range: dict[str, float] = {}
    if filters.uploaded_after:
        date_range["gte"] = filters.uploaded_after.timestamp()
    if filters.uploaded_before:
        date_range["lte"] = filters.uploaded_before.timestamp()
    if date_range:
        conditions.append(
            FieldCondition(key="upload_date", range=Range(**date_range))
        )

    return Filter(must=conditions) if conditions else None


@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    _rate_limit: None = Depends(search_rate_limiter),
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.SEARCH)),
    vector_store: VectorStore = Depends(get_vector_store),
    ranking_service: RankingService = Depends(get_ranking_service),
    graph_svc: "GraphQueryService | None" = Depends(get_graph_query_optional),
) -> SearchResponse:
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    qdrant_filter = _build_qdrant_filter(request.filters) if request.filters else None

    if request.mode == SearchMode.KEYWORD:
        try:
            results = await vector_store.fulltext_search(query, request.top_k, qdrant_filter, request.offset)
        except VectorStoreOperationError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
    elif request.mode == SearchMode.RANKED:
        try:
            query_vector = (await _encode_batch_async([query]))[0]
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to embed query: {exc}")

        weights = request.weights or RankingWeights()
        try:
            results = await ranking_service.ranked_search(
                query_vector, query, request.top_k, qdrant_filter, weights
            )
        except VectorStoreOperationError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
    else:
        try:
            query_vector = (await _encode_batch_async([query]))[0]
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to embed query: {exc}")

        if request.mode == SearchMode.SEMANTIC:
            try:
                results = await vector_store.search(query_vector, request.top_k, qdrant_filter, request.offset)
            except VectorStoreOperationError as exc:
                raise HTTPException(status_code=503, detail=str(exc))
        else:
            try:
                results = await vector_store.hybrid_search(
                    query_vector, query, request.top_k, qdrant_filter
                )
            except VectorStoreOperationError as exc:
                raise HTTPException(status_code=503, detail=str(exc))

    # Build base results from vector search
    items: list[SearchResultItem] = []
    for r in results:
        chunk_content = r["payload"].get("content", "")
        graph_facts_for_item: list[dict] = []

        # M27: enrich with graph facts if graph service is available
        if graph_svc:
            try:
                entities, _total = await graph_svc.search_entities(
                    query=query, skip=0, limit=5,
                )
                for ent in entities:
                    if ent.name.lower() in chunk_content.lower():
                        graph_facts_for_item.append({
                            "entity_name": ent.name,
                            "entity_type": ent.type,
                            "confidence": ent.confidence,
                            "source_document": ent.source_document,
                        })
            except Exception:
                pass  # graph enrichment is best-effort

        items.append(SearchResultItem(
            score=r["score"],
            document_id=r["payload"].get("document_id", ""),
            chunk=chunk_content,
            page=r["payload"].get("page_number"),
            filename=r["payload"].get("filename", ""),
            metadata=r["payload"].get("metadata") or {},
            graph_facts=graph_facts_for_item,
        ))

    return SearchResponse(results=items)
