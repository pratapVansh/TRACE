from datetime import datetime

from app.core.config import settings
from app.core.logging import logger
from app.schemas.retrieval import RetrievalFilter, RetrievedChunk, RetrievalResult
from app.services.embedding_service import _encode_batch_async
from app.services.reranker_service import candidate_count, rerank
from app.services.retrieval_dedup import dedup_by_document
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

        # Over-fetch so the reranker has candidates to reorder, and search
        # both keyword and vector space: exact identifiers (asset tags, part
        # numbers) are precisely what embeddings blur together.
        fetch_k = candidate_count(top_k)
        try:
            results = await self._vector_store.hybrid_search(
                query_vector=query_vector,
                query_text=query,
                top_k=fetch_k,
                query_filter=qdrant_filter,
            )
        except VectorStoreOperationError as exc:
            logger.error("Retrieval search failed: %s", exc)
            raise

        candidates = [
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
            for r in results
        ]

        # Rerank first, then threshold. The fused score coming out of hybrid
        # search is an RRF ranking weight, not a similarity, so filtering on
        # it against ``similarity_threshold`` would discard everything.
        # Reranking replaces it with a calibrated 0-1 relevance.
        #
        # The threshold defaults to 0.0 — retrieval rank-limits instead of
        # score-filtering. The cross-encoder orders results well but its
        # absolute values do not separate hits from misses, so a non-zero
        # default silently returned nothing for almost every conversational
        # question. See the note on ``retrieval_similarity_threshold``.
        # Rerank the full candidate set without trimming: dedup runs next and
        # needs the surplus to refill slots freed by collapsing a document's
        # repeat passages. Trimming here first is what made ``top_k=5`` return
        # four results whenever one document held two of the top five chunks.
        reranked = await rerank(query, candidates)
        chunks = (
            [c for c in reranked if c.score >= similarity_threshold]
            if similarity_threshold > 0.0
            else list(reranked)
        )

        chunks = (
            dedup_by_document(chunks, top_k=top_k)
            if dedup_documents
            else chunks[:top_k]
        )

        logger.info(
            "Retrieved %d chunks (requested top_k=%d, threshold=%.2f, dedup=%s)",
            len(chunks),
            top_k,
            similarity_threshold,
            dedup_documents,
        )

        return RetrievalResult(results=chunks, total=len(chunks))
