"""Chunk indexing service — validates chunk integrity and prepares data for M7."""

from uuid import UUID

from app.core.logging import logger
from app.repositories.document_chunk_repository import DocumentChunkRepository


class ChunkIndexService:
    def __init__(
        self,
        chunk_repository: DocumentChunkRepository,
    ) -> None:
        self._chunk_repository = chunk_repository

    async def get_document_index_status(
        self,
        document_id: UUID,
    ) -> dict:
        chunks = await self._chunk_repository.get_chunks_by_document(document_id)
        total = len(chunks)
        if total == 0:
            return {
                "document_id": str(document_id),
                "total_chunks": 0,
                "pending_embedding": 0,
                "completed_embedding": 0,
                "failed_embedding": 0,
                "has_metadata": False,
                "has_embeddings": False,
                "index_ready": False,
            }

        pending = sum(1 for c in chunks if c.embedding_status == "pending")
        completed = sum(1 for c in chunks if c.embedding_status == "completed")
        failed = sum(1 for c in chunks if c.embedding_status == "failed")
        has_metadata = all(
            bool(c.extra_metadata)
            for c in chunks
        )
        has_embeddings = completed == total

        return {
            "document_id": str(document_id),
            "total_chunks": total,
            "pending_embedding": pending,
            "completed_embedding": completed,
            "failed_embedding": failed,
            "has_metadata": has_metadata,
            "has_embeddings": has_embeddings,
            "index_ready": has_metadata and has_embeddings,
        }

    async def verify_chunk_integrity(
        self,
        document_id: UUID,
    ) -> list[str]:
        chunks = await self._chunk_repository.get_chunks_by_document(document_id)
        warnings: list[str] = []

        if not chunks:
            warnings.append("No chunks found for document")
            return warnings

        for chunk in chunks:
            if not chunk.content.strip():
                warnings.append(
                    f"Chunk #{chunk.chunk_index} ({chunk.id}) has empty content",
                )
            if not chunk.extra_metadata:
                warnings.append(
                    f"Chunk #{chunk.chunk_index} ({chunk.id}) is missing metadata",
                )
            if chunk.token_count <= 0:
                warnings.append(
                    f"Chunk #{chunk.chunk_index} ({chunk.id}) has zero token_count",
                )

        has_embeddings = all(c.embedding_status == "completed" for c in chunks)
        if not has_embeddings:
            pending = [c.chunk_index for c in chunks if c.embedding_status != "completed"]
            warnings.append(
                f"Embeddings pending/missing for chunk indices: {pending}",
            )

        if not warnings:
            logger.info(
                "Chunk integrity verified document_id=%s chunks=%d",
                document_id,
                len(chunks),
            )

        return warnings

    async def get_index_summary(
        self,
        document_id: UUID,
    ) -> dict:
        chunks = await self._chunk_repository.get_chunks_by_document(document_id)
        total = len(chunks)

        if total == 0:
            return {
                "document_id": str(document_id),
                "total_chunks": 0,
                "total_tokens": 0,
                "avg_tokens_per_chunk": 0.0,
                "min_tokens": 0,
                "max_tokens": 0,
                "page_range": None,
                "languages": [],
                "processing_timestamp": None,
            }

        tokens = [c.token_count for c in chunks]
        total_tokens = sum(tokens)

        page_numbers = [
            c.page_number for c in chunks if c.page_number is not None
        ]

        languages = set()
        timestamps = set()
        for c in chunks:
            md = c.extra_metadata or {}
            lang = md.get("language")
            if lang:
                languages.add(str(lang))
            ts = md.get("processing_timestamp")
            if ts:
                timestamps.add(str(ts))

        return {
            "document_id": str(document_id),
            "total_chunks": total,
            "total_tokens": total_tokens,
            "avg_tokens_per_chunk": round(total_tokens / total, 1),
            "min_tokens": min(tokens),
            "max_tokens": max(tokens),
            "page_range": (
                f"{min(page_numbers)}–{max(page_numbers)}"
                if len(page_numbers) >= 2
                else str(page_numbers[0]) if len(page_numbers) == 1 else None
            ),
            "languages": sorted(languages),
            "processing_timestamp": max(timestamps) if timestamps else None,
        }
