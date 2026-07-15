"""Document processor that indexes embedded chunks into Qdrant."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.document_processing_exceptions import IndexingError
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext
from app.services.qdrant_indexing_service import QdrantIndexingService


class IndexingProcessor:
    """Index completed embeddings into Qdrant."""

    name = "indexing"

    def __init__(
        self,
        session: AsyncSession,
        document_repository: DocumentRepository,
        chunk_repository: DocumentChunkRepository,
        indexing_service: QdrantIndexingService,
    ) -> None:
        self._session = session
        self._document_repository = document_repository
        self._chunk_repository = chunk_repository
        self._indexing_service = indexing_service

    async def process(self, context: ProcessingContext) -> None:
        await self._document_repository.update_ingestion_job(
            context.job.id,
            stage=ProcessingStage.INDEXING.value,
        )
        await self._session.flush()

        chunks = await self._chunk_repository.get_chunks_by_document(
            context.document.id,
            embedding_status="completed",
        )
        if not chunks:
            logger.info(
                "No completed chunks to index document_id=%s",
                context.document.id,
            )
            return

        logger.info(
            "Indexing started document_id=%s chunks=%d",
            context.document.id,
            len(chunks),
        )

        try:
            indexed = await self._indexing_service.index_document_chunks(
                chunks=chunks,
                document=context.document,
            )
        except Exception as exc:
            raise IndexingError(f"Qdrant indexing failed: {exc}") from exc

        logger.info(
            "Indexing completed document_id=%s chunks=%d indexed=%d",
            context.document.id,
            len(chunks),
            indexed,
        )
