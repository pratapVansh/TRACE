"""Vector store abstraction and Qdrant implementation."""

import threading
from abc import ABC, abstractmethod
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    Range,
    TextIndexParams,
    TokenizerType,
    VectorParams,
)

from app.core.config import settings
from app.core.logging import logger

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


_CLIENT: QdrantClient | None = None
_CLIENT_LOCK = threading.Lock()


def _get_client() -> QdrantClient:
    global _CLIENT
    if _CLIENT is None:
        with _CLIENT_LOCK:
            if _CLIENT is None:
                _CLIENT = QdrantClient(
                    url=settings.qdrant_url,
                    api_key=settings.qdrant_api_key,
                )
    return _CLIENT


class QdrantVectorStore(VectorStore):

    async def connect(self) -> None:
        try:
            client = _get_client()
            client.get_collections()
            logger.info("Qdrant connected to %s", settings.qdrant_url)
        except Exception as exc:
            raise VectorStoreConnectionError(
                f"Cannot reach Qdrant at {settings.qdrant_url}"
            ) from exc

    async def health_check(self) -> dict:
        client = _get_client()
        try:
            cluster_info = client.get_collections()
            version = getattr(cluster_info, "time", None)
        except Exception as exc:
            raise VectorStoreConnectionError("Qdrant health check failed") from exc

        exists = await self.collection_exists()
        vector_count = 0
        if exists:
            try:
                count_result = client.count(
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
        client = _get_client()
        if await self.collection_exists():
            logger.info(
                "Collection '%s' already exists", settings.qdrant_collection_name
            )
            return

        try:
            client.create_collection(
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
        client = _get_client()
        if not await self.collection_exists():
            return
        try:
            client.delete_collection(collection_name=settings.qdrant_collection_name)
            logger.info("Collection '%s' deleted", settings.qdrant_collection_name)
        except Exception as exc:
            raise VectorStoreOperationError(
                f"Failed to delete collection '{settings.qdrant_collection_name}'"
            ) from exc

    async def collection_exists(self) -> bool:
        client = _get_client()
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
        client = _get_client()
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
                client.upsert(
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
        client = _get_client()
        try:
            result = client.delete(
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

    async def update_document_payload(
        self,
        document_id: UUID,
        payload: dict,
    ) -> int:
        client = _get_client()
        try:
            result = client.set_payload(
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
        client = _get_client()
        try:
            result = client.delete(
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
        client = _get_client()
        try:
            results = client.search(
                collection_name=settings.qdrant_collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=top_k,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            return [
                {
                    "score": hit.score,
                    "payload": hit.payload,
                }
                for hit in results
            ]
        except Exception as exc:
            raise VectorStoreOperationError(
                f"Qdrant search failed: {exc}"
            ) from exc

    async def create_fulltext_index(self) -> None:
        client = _get_client()
        try:
            client.create_payload_index(
                collection_name=settings.qdrant_collection_name,
                field_name="content",
                field_schema=TextIndexParams(
                    type=PayloadSchemaType.TEXT,
                    tokenizer=TokenizerType.WORD,
                    min_token_len=2,
                    max_token_len=20,
                ),
            )
            logger.info("Full-text index created on 'content' field")
        except Exception as exc:
            logger.info(
                "Full-text index on 'content' already exists or creation skipped: %s",
                exc,
            )

    async def fulltext_search(
        self,
        query_text: str,
        top_k: int = 10,
        query_filter: Filter | None = None,
        offset: int = 0,
    ) -> list[dict]:
        client = _get_client()
        try:
            results = client.query_points(
                collection_name=settings.qdrant_collection_name,
                query=query_text,
                using="fulltext",
                query_filter=query_filter,
                limit=top_k,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            return [
                {"score": point.score, "payload": point.payload}
                for point in results.points
            ]
        except Exception as exc:
            raise VectorStoreOperationError(
                f"Qdrant fulltext search failed: {exc}"
            ) from exc

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
        try:
            vector_results = await self.search(query_vector, fetch_k, query_filter)
        except VectorStoreOperationError as exc:
            logger.warning("Vector search in hybrid mode failed: %s", exc)

        text_results: list[dict] = []
        try:
            text_results = await self.fulltext_search(query_text, fetch_k, query_filter)
        except VectorStoreOperationError as exc:
            logger.warning("Full-text search in hybrid mode failed: %s", exc)

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

        return [
            {"score": rrf_scores[pid], "payload": payloads[pid]}
            for pid in sorted_ids
        ]
