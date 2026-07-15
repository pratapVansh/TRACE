from datetime import datetime

from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

from app.core.logging import logger
from app.schemas.retrieval import RetrievalFilter, RetrievedChunk, RetrievalResult
from app.services.embedding_service import _encode_batch_async
from app.services.vector_store import VectorStore, VectorStoreOperationError


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
        top_k: int = 10,
        similarity_threshold: float = 0.0,
        filters: RetrievalFilter | None = None,
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

        logger.info(
            "Retrieved %d chunks (requested top_k=%d, threshold=%.2f)",
            len(chunks),
            top_k,
            similarity_threshold,
        )

        return RetrievalResult(results=chunks, total=len(chunks))
