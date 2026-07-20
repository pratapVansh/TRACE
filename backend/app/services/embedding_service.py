"""Embedding generation service using Sentence Transformers."""

import asyncio
from collections.abc import Sequence
from typing import Any
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.document_chunk import DocumentChunk
from app.repositories.document_chunk_repository import DocumentChunkRepository

_EXECUTOR = ThreadPoolExecutor(max_workers=1)
_MODEL: Any = None


def _get_model() -> Any:
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        model_name = settings.embedding_model_name
        logger.info("Loading embedding model: %s", model_name)
        _MODEL = SentenceTransformer(model_name)
    return _MODEL


def _encode_batch(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()


async def _encode_batch_async(texts: list[str]) -> list[list[float]]:
    from app.core.cache import cache_manager
    import hashlib
    
    loop = asyncio.get_event_loop()
    
    # Check cache first
    results = [None] * len(texts)
    
    unique_texts = {}
    
    for i, text in enumerate(texts):
        key = f"embed:{hashlib.md5(text.encode('utf-8')).hexdigest()}"
        cached = await cache_manager.get(key)
        if cached:
            results[i] = cached
        else:
            if text not in unique_texts:
                unique_texts[text] = []
            unique_texts[text].append(i)
            
    hits = len(texts) - sum(len(indices) for indices in unique_texts.values())
    misses = len(texts) - hits
    logger.info("Embedding cache metrics — hits=%d misses=%d", hits, misses)
            
    if unique_texts:
        uncached_texts = list(unique_texts.keys())
        new_embeddings = await loop.run_in_executor(_EXECUTOR, _encode_batch, uncached_texts)
        for text, emb in zip(uncached_texts, new_embeddings):
            key = f"embed:{hashlib.md5(text.encode('utf-8')).hexdigest()}"
            await cache_manager.set(key, emb, ttl=86400) # cache for 1 day
            for idx in unique_texts[text]:
                results[idx] = emb
            
    return results


class EmbeddingService:
    def __init__(
        self,
        session: AsyncSession,
        chunk_repository: DocumentChunkRepository,
    ) -> None:
        self._session = session
        self._chunk_repository = chunk_repository

    async def generate_for_document(
        self,
        document_id: UUID,
    ) -> int:
        """Generate and store embeddings for all pending chunks of a document.

        Returns the number of chunks processed. Raises on fatal errors.
        """
        chunks = await self._chunk_repository.get_pending_embedding_chunks(document_id)
        if not chunks:
            logger.info(
                "No pending chunks to embed document_id=%s",
                document_id,
            )
            return 0

        logger.info(
            "Embedding started document_id=%s chunks=%d",
            document_id,
            len(chunks),
        )

        texts = [chunk.content for chunk in chunks]
        embeddings = await self._embed_with_retry(texts)

        updates = [
            {
                "id": chunk.id,
                "embedding": emb,
                "embedding_status": "completed",
            }
            for chunk, emb in zip(chunks, embeddings)
        ]
        await self._chunk_repository.update_chunks_embedding_bulk(updates)

        logger.info(
            "Embedding completed document_id=%s chunks=%d",
            document_id,
            len(chunks),
        )
        return len(chunks)

    async def _embed_with_retry(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        batches = [
            texts[i:i + settings.embedding_batch_size]
            for i in range(0, len(texts), settings.embedding_batch_size)
        ]

        all_embeddings: list[list[float]] = []
        for batch in batches:
            embeddings = await self._embed_batch_with_retry(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

    async def _embed_batch_with_retry(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        last_exc: Exception | None = None
        max_attempts = settings.embedding_retry_attempts

        for attempt in range(1, max_attempts + 1):
            try:
                return await _encode_batch_async(texts)
            except Exception as exc:
                last_exc = exc
                if attempt < max_attempts:
                    delay = 2.0 ** attempt
                    logger.warning(
                        "Embedding attempt %d/%d failed, retrying in %.1fs: %s",
                        attempt,
                        max_attempts,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Embedding failed after %d attempts: %s",
                        max_attempts,
                        exc,
                    )

        raise last_exc  # type: ignore[misc]
