from collections import OrderedDict
from datetime import datetime

from app.core.config import settings
from app.core.logging import logger
from app.schemas.retrieval import RetrievalFilter, RetrievedChunk, RetrievalResult
from app.services.embedding_service import _encode_batch_async
from app.services.vector_store import VectorStore, VectorStoreOperationError

# Lazy import for qdrant types that may not be available in all environments
try:
    from qdrant_client.models import FieldCondition, Filter, MatchValue, Range  # noqa: PLC0415
    _QD_MODELS_AVAILABLE = True
except ImportError:
    FieldCondition = object  # type: ignore[assignment,misc]
    Filter = object
    MatchValue = object
    Range = object
    _QD_MODELS_AVAILABLE = False


def _build_qdrant_filter(filters: RetrievalFilter) -> Filter | None:
    conditions: list[FieldCondition] = []

    if filters.document_id:
        conditions.append(
            FieldCondition(key="document_id", match=MatchValue(value=filters.document_id))
        )

    if filters.filename:
        conditions.append(
            FieldCondition(key="filename", match=MatchValue(value=filters.filename))
        )

    if filters.document_type:
        conditions.append(
            FieldCondition(key="document_type", match=MatchValue(value=filters.document_type))
        )

    if filters.uploaded_by:
        conditions.append(
            FieldCondition(key="uploaded_by", match=MatchValue(value=filters.uploaded_by))
        )

    if filters.language:
        conditions.append(
            FieldCondition(key="metadata.language", match=MatchValue(value=filters.language))
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


class RetrieverService:
    def __init__(self, vector_store: VectorStore) -> None:
        self._vector_store = vector_store

    async def retrieve(
        self,
        query: str,
        top_k: int = settings.retrieval_top_k,
        similarity_threshold: float = settings.retrieval_similarity_threshold,
        filters: RetrievalFilter | None = None,
        dedup_documents: bool = settings.retrieval_dedup_documents,
    ) -> RetrievalResult:
        query_vector = (await _encode_batch_async([query]))[0]

        qdrant_filter = _build_qdrant_filter(filters) if filters else None

        try:
            results = await self._vector_store.search(
                query_vector=query_vector,
                top_k=top_k,
                query_filter=qdrant_filter,
            )
        except VectorStoreOperationError as exc:
            logger.error("Retrieval search failed: %s", exc)
            raise

        filtered = [r for r in results if r["score"] >= similarity_threshold]

        chunks = [
            RetrievedChunk(
                chunk_id=r.get("id") or r["payload"].get("chunk_id", ""),
                score=r["score"],
                document_id=r["payload"].get("document_id", ""),
                document_name=r["payload"].get("filename", ""),
                content=r["payload"].get("content", ""),
                page_number=r["payload"].get("page_number"),
                chunk_index=r["payload"].get("chunk_index"),
                metadata=r["payload"].get("metadata") or {},
            )
            for r in filtered
        ]

        if dedup_documents:
            seen: dict[str, RetrievedChunk] = OrderedDict()
            for chunk in chunks:
                doc_id = chunk.document_id
                if doc_id not in seen or chunk.score > seen[doc_id].score:
                    seen[doc_id] = chunk
            chunks = list(seen.values())

        logger.info(
            "Retrieved %d chunks (requested top_k=%d, threshold=%.2f, dedup=%s)",
            len(chunks),
            top_k,
            similarity_threshold,
            dedup_documents,
        )

        return RetrievalResult(results=chunks, total=len(chunks))
