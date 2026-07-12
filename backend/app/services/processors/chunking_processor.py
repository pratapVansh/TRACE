"""Document processor that generates chunks from extracted text."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.chunking_service import ChunkingService
from app.services.document_processing_exceptions import ChunkingError
from app.services.language_detection import DETECTED_LANGUAGE_KEY, UNKNOWN_LANGUAGE_CODE
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext


class ChunkingProcessor:
    """Split extracted document text into chunks and persist them."""

    name = "chunking"

    def __init__(
        self,
        session: AsyncSession,
        document_repository: DocumentRepository,
        document_chunk_repository: DocumentChunkRepository,
    ) -> None:
        self._session = session
        self._document_repository = document_repository
        self._chunking_service = ChunkingService(session, document_chunk_repository)

    async def process(self, context: ProcessingContext) -> None:
        await self._document_repository.update_ingestion_job(
            context.job.id,
            stage=ProcessingStage.CHUNKING.value,
        )
        await self._session.flush()

        logger.info(
            "Chunking started document_id=%s version_id=%s",
            context.document.id,
            context.version.id,
        )

        extracted = await self._document_repository.get_extracted_text_by_version_id(
            context.version.id,
        )
        if extracted is None or not extracted.full_text.strip():
            logger.info(
                "No extracted text to chunk document_id=%s version_id=%s",
                context.document.id,
                context.version.id,
            )
            return

        filename = context.document.original_filename

        try:
            language = None
            doc = await self._document_repository.get_document_by_id(context.document.id)
            if doc is not None:
                lang_info = doc.extra_metadata.get(DETECTED_LANGUAGE_KEY)
                if lang_info and isinstance(lang_info, dict):
                    code = lang_info.get("code")
                    if code and code != UNKNOWN_LANGUAGE_CODE:
                        language = code

            chunks = await self._chunking_service.chunk_document(
                context.document.id,
                text=extracted.full_text,
                pages=extracted.pages,
                filename=filename,
                language=language,
            )
        except Exception as exc:
            raise ChunkingError(f"Chunking failed: {exc}") from exc

        logger.info(
            "Chunking completed document_id=%s version_id=%s chunks=%d",
            context.document.id,
            context.version.id,
            len(chunks),
        )
