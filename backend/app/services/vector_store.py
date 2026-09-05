"""Vector store abstraction and Qdrant implementation."""

import re
import threading
from abc import ABC, abstractmethod
from uuid import UUID

from app.core.config import settings
from app.core.logging import logger
from app.core.retry import RetryPolicy, is_http_status_retryable, retry_sync

# Lazy import — qdrant_client may not be importable in all environments
# (e.g., grpc DLL blocked by App Control policy on Windows).
# Type-checkers can safely ignore the module-level names.
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.exceptions import UnexpectedResponse
    from qdrant_client.models import (  # type: ignore[unused-import]
        Distance,
        FieldCondition,
        Filter,
        MatchText,
        MatchValue,
        PayloadSchemaType,
        PointStruct,
        Range,
        TextIndexParams,
        TokenizerType,
        VectorParams,
    )
    _QDRAINT_AVAILABLE = True
except ImportError:
    QdrantClient = None  # type: ignore[assignment,misc]
    UnexpectedResponse = Exception  # type: ignore[assignment,misc]
    # Define dummy types so type annotations don't fail
    Distance = object
    FieldCondition = object
    Filter = object
    MatchText = object
    MatchValue = object
    PayloadSchemaType = object
    PointStruct = object
    Range = object
    TextIndexParams = object
    TokenizerType = object
    VectorParams = object
    _QDRAINT_AVAILABLE = False


def _is_qdrant_retryable(exc: Exception) -> bool:
    if isinstance(exc, ValueError):
        return False
    if isinstance(exc, UnexpectedResponse):
        return is_http_status_retryable(getattr(exc, "status_code", None))
    return True


_qdrant_retry_policy = RetryPolicy(
    max_retries=settings.qdrant_max_retries,
    base_delay_seconds=1.0,
    max_delay_seconds=30.0,
)

VECTOR_DIMENSION = 384  # all-MiniLM-L6-v2
QDRANT_UPSERT_BATCH_SIZE = 64


class VectorStoreError(Exception):
    """Base class for vector store failures."""


class VectorStoreConnectionError(VectorStoreError):
    """Raised when the vector store cannot be reached."""


class VectorStoreOperationError(VectorStoreError):
    """Raised when a vector store operation fails."""


class VectorStore(ABC):
    """Abstract interface for a vector storage backend."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connectivity and verify the service is reachable."""
        ...

    @abstractmethod
    async def health_check(self) -> dict:
        """Return a dictionary with connectivity, version, and collection info."""
        ...

    @abstractmethod
    async def create_collection(self) -> None:
        """Create the configured collection if it does not already exist."""
        ...

    @abstractmethod
    async def delete_collection(self) -> None:
        """Remove the configured collection."""
        ...

    @abstractmethod
    async def collection_exists(self) -> bool:
        """Return whether the configured collection exists."""
        ...

    @abstractmethod
    async def upsert_vectors(
        self,
        vectors: list[dict],
    ) -> int:
        """Upsert a batch of vectors with payloads. Returns the count upserted."""
        ...

    @abstractmethod
    async def delete_vectors_by_document(
        self,
        document_id: UUID,
    ) -> int:
        """Delete all vectors belonging to a document. Returns the count deleted."""
        ...

    @abstractmethod
    async def delete_vectors_by_ids(
        self,
        point_ids: list[str],
    ) -> int:
        """Delete specific vectors by their point IDs. Returns the count deleted."""
        ...

    @abstractmethod
    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        query_filter: Filter | None = None,
        offset: int = 0,
    ) -> list[dict]:
        """Search for nearest vectors. Returns list of dicts with score and payload."""
        ...

    @abstractmethod
    async def create_fulltext_index(self) -> None:
        """Create a full-text index on the content field for keyword search."""
        ...

    @abstractmethod
    async def fulltext_search(
        self,
        query_text: str,
        top_k: int = 10,
        query_filter: Filter | None = None,
        offset: int = 0,
    ) -> list[dict]:
        """Search using full-text (BM25) matching. Returns list of dicts with score and payload."""
        ...

    @abstractmethod
    async def update_document_payload(
        self,
        document_id: UUID,
        payload: dict,
    ) -> int:
        """Update payload fields for all points belonging to a document without touching vectors."""
        ...

    @abstractmethod
    async def hybrid_search(
        self,
        query_vector: list[float],
        query_text: str,
        top_k: int = 10,
        query_filter: Filter | None = None,
    ) -> list[dict]:
        """Combine vector similarity and keyword BM25 search with RRF fusion."""
        ...


# Keyword matching is a filter, not a ranker, so results are re-scored
# locally; fetch a wider set than requested to rank across it.
FULLTEXT_OVERFETCH = 3

# Re-exported so keyword search and graph entity lookup tokenize queries
# identically; ``tests/test_query_terms.py`` also reaches them through here.
from app.core.query_terms import (  # noqa: E402
    MAX_QUERY_TERMS,
    MIN_QUERY_TERM_LEN,
    _extract_query_terms,
    _term_rank,
)

def _term_coverage(terms: list[str], content: str) -> float:
    """Fraction of query *terms* present in *content*, as a 0-1 score.

    Qdrant returns a uniform score for filter-only queries, so without this
    every keyword hit would tie and the fusion step would order them
    arbitrarily.
    """
    if not terms:
        return 0.0
    haystack = (content or "").casefold()
    matched = sum(1 for term in terms if term.casefold() in haystack)
    return matched / len(terms)


_CLIENT: QdrantClient | None = None
import asyncio
_CLIENT_LOCK = asyncio.Lock()


async def _get_client() -> QdrantClient:
    global _CLIENT
    if _CLIENT is None:
        async with _CLIENT_LOCK:
            if _CLIENT is None:
                _CLIENT = QdrantClient(
                    url=settings.qdrant_url,
                    api_key=settings.qdrant_api_key,
                    timeout=settings.qdrant_timeout_seconds,
                    prefer_grpc=False,
                )
    return _CLIENT


class QdrantVectorStore(VectorStore):

    async def connect(self) -> None:
        try:
            client = await _get_client()
            retry_sync(
                client.get_collections,
                _qdrant_retry_policy,
                _is_qdrant_retryable,
                "Qdrant connect",
            )
            logger.info("Qdrant connected to %s", settings.qdrant_url)
        except Exception as exc:
            raise VectorStoreConnectionError(
                f"Cannot reach Qdrant at {settings.qdrant_url}"
            ) from exc

    async def health_check(self) -> dict:
        client = await _get_client()
        try:
            cluster_info = retry_sync(
                client.get_collections,
                _qdrant_retry_policy,
                _is_qdrant_retryable,
                "Qdrant health check",
            )
            version = getattr(cluster_info, "time", None)
        except Exception as exc:
            raise VectorStoreConnectionError("Qdrant health check failed") from exc

        exists = await self.collection_exists()
        vector_count = 0
        if exists:
            try:
                count_result = retry_sync(
                    client.count,
                    _qdrant_retry_policy,
                    _is_qdrant_retryable,
                    "Qdrant count",
                    collection_name=settings.qdrant_collection_name,
                    exact=True,
                )
                vector_count = count_result.count
            except Exception:
                pass

        return {
            "connected": True,
            "collection_exists": exists,
            "vector_count": vector_count,
            "qdrant_version": version or "unknown",
        }

    async def create_collection(self) -> None:
        client = await _get_client()
        if await self.collection_exists():
            logger.info(
                "Collection '%s' already exists", settings.qdrant_collection_name
            )
            return

        try:
            retry_sync(
                client.create_collection,
                _qdrant_retry_policy,
                _is_qdrant_retryable,
                "Qdrant create_collection",
                collection_name=settings.qdrant_collection_name,
                vectors_config=VectorParams(
                    size=VECTOR_DIMENSION,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(
                "Collection '%s' created (dim=%d, distance=cosine)",
                settings.qdrant_collection_name,
                VECTOR_DIMENSION,
            )
        except Exception as exc:
            raise VectorStoreOperationError(
                f"Failed to create collection '{settings.qdrant_collection_name}'"
            ) from exc

    async def delete_collection(self) -> None:
        client = await _get_client()
        if not await self.collection_exists():
            return
        try:
            retry_sync(
                client.delete_collection,
                _qdrant_retry_policy,
                _is_qdrant_retryable,
                "Qdrant delete_collection",
                collection_name=settings.qdrant_collection_name,
            )
            logger.info("Collection '%s' deleted", settings.qdrant_collection_name)
        except Exception as exc:
            raise VectorStoreOperationError(
                f"Failed to delete collection '{settings.qdrant_collection_name}'"
            ) from exc

    async def collection_exists(self) -> bool:
        client = await _get_client()
        try:
            collections = client.get_collections().collections
            return any(
                c.name == settings.qdrant_collection_name for c in collections
            )
        except UnexpectedResponse as exc:
            logger.warning("Qdrant API error checking collection existence: %s", exc)
            return False
        except Exception as exc:
            logger.warning("Unexpected error checking collection existence: %s", exc)
            return False

    async def upsert_vectors(
        self,
        vectors: list[dict],
    ) -> int:
        client = await _get_client()
        total = 0
        for i in range(0, len(vectors), QDRANT_UPSERT_BATCH_SIZE):
            batch = vectors[i : i + QDRANT_UPSERT_BATCH_SIZE]
            points = [
                PointStruct(
                    id=v["point_id"],
                    vector=v["vector"],
                    payload=v["payload"],
                )
                for v in batch
            ]
            try:
                retry_sync(
                    client.upsert,
                    _qdrant_retry_policy,
                    _is_qdrant_retryable,
                    "Qdrant upsert",
                    collection_name=settings.qdrant_collection_name,
                    points=points,
                )
                total += len(points)
            except Exception as exc:
                raise VectorStoreOperationError(
                    f"Qdrant batch upsert failed at offset {i}: {exc}"
                ) from exc
        return total

    async def delete_vectors_by_document(
        self,
        document_id: UUID,
    ) -> int:
        client = await _get_client()
        try:
            result = retry_sync(
                client.delete,
                _qdrant_retry_policy,
                _is_qdrant_retryable,
                "Qdrant delete_vectors_by_document",
                collection_name=settings.qdrant_collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=str(document_id)),
                        ),
                    ],
                ),
            )
            count = getattr(result, "count", 0)
            logger.info(
                "Deleted %d vectors for document_id=%s", count, document_id
            )
            return count
        except Exception as exc:
            raise VectorStoreOperationError(
                f"Failed to delete vectors for document {document_id}: {exc}"
            ) from exc

    async def count_vectors_by_document(
        self,
        document_id: UUID,
    ) -> int:
        """Number of vectors currently stored for a document.

        Lets callers tell "already indexed" apart from "chunked in Postgres
        but missing from Qdrant" — the state left behind when the collection
        is recreated or the cluster is replaced while the relational rows
        survive.
        """
        client = await _get_client()
        try:
            result = retry_sync(
                client.count,
                _qdrant_retry_policy,
                _is_qdrant_retryable,
                "Qdrant count_vectors_by_document",
                collection_name=settings.qdrant_collection_name,
                count_filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=str(document_id)),
                        ),
                    ],
                ),
                exact=True,
            )
            return int(getattr(result, "count", 0))
        except Exception as exc:
            raise VectorStoreOperationError(
                f"Failed to count vectors for document {document_id}: {exc}"
            ) from exc

    async def update_document_payload(
        self,
        document_id: UUID,
        payload: dict,
    ) -> int:
        client = await _get_client()
        try:
            result = retry_sync(
                client.set_payload,
                _qdrant_retry_policy,
                _is_qdrant_retryable,
                "Qdrant update_document_payload",
                collection_name=settings.qdrant_collection_name,
                payload=payload,
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=str(document_id)),
                        ),
                    ],
                ),
            )
            count = getattr(result, "count", 0)
            logger.info(
                "Updated payload for %d points document_id=%s", count, document_id
            )
            return count
        except Exception as exc:
            raise VectorStoreOperationError(
                f"Failed to update payload for document {document_id}: {exc}"
            ) from exc

    async def delete_vectors_by_ids(
        self,
        point_ids: list[str],
    ) -> int:
        client = await _get_client()
        try:
            result = retry_sync(
                client.delete,
                _qdrant_retry_policy,
                _is_qdrant_retryable,
                "Qdrant delete_vectors_by_ids",
                collection_name=settings.qdrant_collection_name,
                points_selector=point_ids,
            )
            count = getattr(result, "count", 0)
            logger.info("Deleted %d vectors by IDs", count)
            return count
        except Exception as exc:
            raise VectorStoreOperationError(
                f"Failed to delete vectors by IDs: {exc}"
            ) from exc

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        query_filter: Filter | None = None,
        offset: int = 0,
    ) -> list[dict]:
        import time
        from app.core.observability import metrics
        start_time = time.perf_counter()
        from app.core.cache import cache_manager
        import hashlib
        import json
        
        # Build cache key for query_vector
        filter_dict = query_filter.dict() if hasattr(query_filter, "dict") else {}
        cache_key = f"qdrant_search:{hashlib.md5((json.dumps(query_vector) + json.dumps(filter_dict) + str(top_k) + str(offset)).encode()).hexdigest()}"
        cached_res = await cache_manager.get(cache_key)
        if cached_res is not None:
            metrics.record_histogram("vector.query.time", time.perf_counter() - start_time)
            return cached_res

        client = await _get_client()
        try:
            results = retry_sync(
                client.query_points,
                _qdrant_retry_policy,
                _is_qdrant_retryable,
                "Qdrant search",
                collection_name=settings.qdrant_collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=top_k,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            data = [
                {
                    "id": str(hit.id),
                    "score": hit.score,
                    "payload": hit.payload,
                }
                for hit in results.points
            ]
            await cache_manager.set(cache_key, data, ttl=3600)
            metrics.record_histogram("vector.query.time", time.perf_counter() - start_time)
            return data
        except Exception as exc:
            raise VectorStoreOperationError(
                f"Qdrant search failed: {exc}"
            ) from exc

    async def create_fulltext_index(self) -> None:
        client = await _get_client()
        for field_name, field_schema in (
            ("content", TextIndexParams(
                type=PayloadSchemaType.TEXT,
                tokenizer=TokenizerType.WORD,
                min_token_len=2,
                max_token_len=20,
            )),
            ("document_id", PayloadSchemaType.KEYWORD),
        ):
            try:
                client.create_payload_index(
                    collection_name=settings.qdrant_collection_name,
                    field_name=field_name,
                    field_schema=field_schema,
                )
                logger.info("Payload index created on '%s' field", field_name)
            except Exception as exc:
                logger.info(
                    "Payload index on '%s' already exists or creation skipped: %s",
                    field_name,
                    exc,
                )

    async def fulltext_search(
        self,
        query_text: str,
        top_k: int = 10,
        query_filter: Filter | None = None,
        offset: int = 0,
    ) -> list[dict]:
        """Keyword search over the ``content`` full-text payload index.

        This previously issued ``query_points(query=<raw string>,
        using="fulltext")``. ``using`` names a *vector* in the collection and
        no such vector is configured — ``create_collection`` defines a single
        unnamed dense vector — so the server rejected every call with HTTP
        400. ``hybrid_search`` catches that and falls back to vector-only
        results, so hybrid retrieval silently was never hybrid.

        Qdrant's ``MatchText`` ANDs the tokens it is given, which means
        passing a whole question matches nothing: "Why did pump P-101 fail?"
        requires "why" and "did" to appear too. The query is therefore split
        into terms combined with ``should`` (OR) for recall, and results are
        ranked by how many distinct query terms each chunk contains, since a
        filter-only query assigns every hit the same score.
        """
        terms = _extract_query_terms(query_text)
        if not terms:
            return []

        text_condition = Filter(
            should=[
                FieldCondition(key="content", match=MatchText(text=term))
                for term in terms
            ]
        )
        # Preserve any caller-supplied filter (document scoping, permissions)
        # by requiring it alongside the keyword match.
        combined = (
            Filter(must=[query_filter, text_condition])
            if query_filter is not None
            else text_condition
        )

        client = await _get_client()
        try:
            points, _ = retry_sync(
                client.scroll,
                _qdrant_retry_policy,
                _is_qdrant_retryable,
                "Qdrant fulltext_search",
                collection_name=settings.qdrant_collection_name,
                scroll_filter=combined,
                # Over-fetch so ranking happens across the whole match set
                # rather than an arbitrary page of it.
                limit=(top_k + offset) * FULLTEXT_OVERFETCH,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            raise VectorStoreOperationError(
                f"Qdrant fulltext search failed: {exc}"
            ) from exc

        scored = [
            {
                "id": str(point.id),
                "score": _term_coverage(terms, (point.payload or {}).get("content", "")),
                "payload": point.payload,
            }
            for point in points
        ]
        scored.sort(key=lambda hit: hit["score"], reverse=True)
        return scored[offset : offset + top_k]

    async def hybrid_search(
        self,
        query_vector: list[float],
        query_text: str,
        top_k: int = 10,
        query_filter: Filter | None = None,
    ) -> list[dict]:
        limit_factor = 2
        fetch_k = top_k * limit_factor

        vector_results: list[dict] = []
        vector_failed = False
        try:
            vector_results = await self.search(query_vector, fetch_k, query_filter)
        except VectorStoreOperationError as exc:
            vector_failed = True
            logger.warning("Vector search in hybrid mode failed: %s", exc)

        text_results: list[dict] = []
        text_failed = False
        try:
            text_results = await self.fulltext_search(query_text, fetch_k, query_filter)
        except VectorStoreOperationError as exc:
            text_failed = True
            logger.warning("Full-text search in hybrid mode failed: %s", exc)

        # One arm failing is a degradation: the other still answers the query.
        # Both failing is an outage, and returning an empty list would be
        # indistinguishable from "nothing matched" — the caller would report
        # no results found while the store was simply unreachable.
        if vector_failed and text_failed:
            raise VectorStoreOperationError(
                "Hybrid search failed: neither vector nor keyword search could "
                "reach the vector store"
            )

        if not vector_results and not text_results:
            return []

        if not text_results:
            return vector_results[:top_k]

        if not vector_results:
            return text_results[:top_k]

        rank_constant = 60
        rrf_scores: dict[str, float] = {}
        payloads: dict[str, dict] = {}

        for rank, hit in enumerate(vector_results):
            pid = hit["payload"].get("chunk_id", "")
            if not pid:
                continue
            rrf_scores[pid] = rrf_scores.get(pid, 0) + 1.0 / (rank_constant + rank + 1)
            if pid not in payloads:
                payloads[pid] = hit["payload"]

        for rank, hit in enumerate(text_results):
            pid = hit["payload"].get("chunk_id", "")
            if not pid:
                continue
            rrf_scores[pid] = rrf_scores.get(pid, 0) + 1.0 / (rank_constant + rank + 1)
            if pid not in payloads:
                payloads[pid] = hit["payload"]

        sorted_ids = sorted(
            rrf_scores.keys(),
            key=lambda x: rrf_scores[x],
            reverse=True,
        )[:top_k]

        # ``pid`` is the point id. Both arms return it as "id" and callers rely
        # on that key to identify a chunk, so fusion has to put it back —
        # dropping it here is what made hybrid results the only ones without an
        # identifiable chunk.
        return [
            {"id": pid, "score": rrf_scores[pid], "payload": payloads[pid]}
            for pid in sorted_ids
        ]
