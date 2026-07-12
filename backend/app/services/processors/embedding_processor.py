"""Document processor that generates embeddings for document chunks."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.document_processing_exceptions import EmbeddingError
from app.services.embedding_service import EmbeddingService
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext


class EmbeddingProcessor:
    """Generate embeddings for all pending chunks of a document."""

    name = "embedding"

    def __init__(
        self,
        session: AsyncSession,
        document_repository: DocumentRepository,
        chunk_repository: DocumentChunkRepository,
        embedding_service: EmbeddingService,
    ) -> None:
        self._session = session
        self._document_repository = document_repository
        self._embedding_service = embedding_service

    async def process(self, context: ProcessingContext) -> None:
        await self._document_repository.update_ingestion_job(
            context.job.id,
            stage=ProcessingStage.EMBEDDING.value,
        )
        await self._session.flush()

        logger.info(
            "Embedding started document_id=%s version_id=%s",
            context.document.id,
            context.version.id,
        )

        try:
            processed = await self._embedding_service.generate_for_document(
                context.document.id,
            )
        except Exception as exc:
            raise EmbeddingError(f"Embedding generation failed: {exc}") from exc

        logger.info(
            "Embedding completed document_id=%s version_id=%s chunks=%d",
            context.document.id,
            context.version.id,
            processed,
        )
