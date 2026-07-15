"""Service that indexes embedded chunks into Qdrant."""

import asyncio
from uuid import UUID

from app.core.config import settings
from app.core.logging import logger
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.vector_store import (
    QDRANT_UPSERT_BATCH_SIZE,
    VectorStore,
    VectorStoreOperationError,
)


class QdrantIndexingService:
    """Upserts document chunk embeddings into Qdrant with retry logic."""

    def __init__(self, vector_store: VectorStore) -> None:
        self._vector_store = vector_store

    async def index_document_chunks(
        self,
        chunks: list[DocumentChunk],
        document: Document,
    ) -> int:
        """Index all completed chunks of a document into Qdrant.

        Builds payloads and upserts in batches with retry.
        Returns the number of vectors indexed.
        """
        await self.delete_document_vectors(document.id)

        vectors = []
        for chunk in chunks:
            if not chunk.embedding:
                continue
            vectors.append(self._build_point(chunk, document))

        if not vectors:
            logger.info(
                "No vectors to index document_id=%s", document.id
            )
            return 0

        total = await self._upsert_with_retry(vectors)
        logger.info(
            "Indexed %d/%d vectors document_id=%s",
            total,
            len(chunks),
            document.id,
        )
        return total

    async def delete_document_vectors(self, document_id: UUID) -> int:
        """Delete all Qdrant vectors for a document."""
        return await self._vector_store.delete_vectors_by_document(document_id)

    def _build_point(
        self,
        chunk: DocumentChunk,
        document: Document,
    ) -> dict:
        payload: dict = {
            "chunk_id": str(chunk.id),
            "document_id": str(document.id),
            "filename": document.original_filename,
            "content": chunk.content,
            "document_type": document.doc_type,
            "metadata": chunk.extra_metadata,
        }

        if chunk.page_number is not None:
            payload["page_number"] = chunk.page_number

        payload["chunk_index"] = chunk.chunk_index

        if document.uploaded_by is not None:
            payload["uploaded_by"] = str(document.uploaded_by)

        if document.created_at is not None:
            payload["upload_date"] = document.created_at.timestamp()

        if chunk.created_at is not None:
            payload["created_at"] = chunk.created_at.isoformat()

        return {
            "point_id": str(chunk.id),
            "vector": chunk.embedding,
            "payload": payload,
        }

    async def _upsert_with_retry(
        self,
        vectors: list[dict],
    ) -> int:
        last_exc: Exception | None = None
        max_attempts = settings.embedding_retry_attempts

        for attempt in range(1, max_attempts + 1):
            try:
                return await self._vector_store.upsert_vectors(vectors)
            except (VectorStoreOperationError, Exception) as exc:
                last_exc = exc
                if attempt < max_attempts:
                    delay = 2.0 ** attempt
                    logger.warning(
                        "Qdrant upsert attempt %d/%d failed, retrying in %.1fs: %s",
                        attempt,
                        max_attempts,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Qdrant upsert failed after %d attempts: %s",
                        max_attempts,
                        exc,
                    )

        raise last_exc  # type: ignore[misc]
