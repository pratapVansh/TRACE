"""Unit tests for ChunkingProcessor."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.models.document_extracted_text import DocumentExtractedText
from app.services.document_processing_exceptions import ChunkingError
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext
from app.services.processors.chunking_processor import ChunkingProcessor


@pytest.fixture
def document_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_document(document_id: uuid.UUID) -> Document:
    doc = Document(
        id=document_id,
        title="Test Doc",
        original_filename="test.pdf",
        doc_type="manual",
        status="processing",
        extra_metadata={
            "detected_language": {"code": "en", "confidence": 0.95},
        },
    )
    doc.created_at = datetime.now(UTC)
    doc.updated_at = datetime.now(UTC)
    return doc


@pytest.fixture
def sample_version(document_id: uuid.UUID) -> DocumentVersion:
    version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=document_id,
        version_no=1,
        storage_uri="test.pdf",
        checksum_sha256="abc123",
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=100,
        is_latest=True,
    )
    version.created_at = datetime.now(UTC)
    return version


@pytest.fixture
def sample_job(document_id: uuid.UUID) -> IngestionJob:
    job = IngestionJob(
        id=uuid.uuid4(),
        document_id=document_id,
        status="processing",
        stage="text_extraction",
    )
    job.created_at = datetime.now(UTC)
    return job


@pytest.fixture
def context(
    sample_document: Document,
    sample_version: DocumentVersion,
    sample_job: IngestionJob,
) -> ProcessingContext:
    return ProcessingContext(
        document=sample_document,
        version=sample_version,
        job=sample_job,
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_document_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_chunk_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def processor(
    mock_session: AsyncMock,
    mock_document_repo: AsyncMock,
    mock_chunk_repo: AsyncMock,
) -> ChunkingProcessor:
    return ChunkingProcessor(
        session=mock_session,
        document_repository=mock_document_repo,
        document_chunk_repository=mock_chunk_repo,
    )


@pytest.mark.asyncio
async def test_processor_name(processor: ChunkingProcessor) -> None:
    assert processor.name == "chunking"


@pytest.mark.asyncio
async def test_process_no_extracted_text(
    processor: ChunkingProcessor,
    mock_document_repo: AsyncMock,
    context: ProcessingContext,
) -> None:
    mock_document_repo.get_extracted_text_by_version_id.return_value = None

    await processor.process(context)

    mock_document_repo.update_ingestion_job.assert_awaited_with(
        context.job.id,
        stage=ProcessingStage.CHUNKING.value,
    )


@pytest.mark.asyncio
async def test_process_whitespace_only_text(
    processor: ChunkingProcessor,
    mock_document_repo: AsyncMock,
    context: ProcessingContext,
) -> None:
    extracted = AsyncMock(spec=DocumentExtractedText)
    extracted.full_text = "   \n   \n  "
    extracted.pages = []
    mock_document_repo.get_extracted_text_by_version_id.return_value = extracted

    await processor.process(context)

    mock_document_repo.update_ingestion_job.assert_awaited()


@pytest.mark.asyncio
async def test_process_success(
    processor: ChunkingProcessor,
    mock_document_repo: AsyncMock,
    mock_chunk_repo: AsyncMock,
    context: ProcessingContext,
) -> None:
    extracted = AsyncMock(spec=DocumentExtractedText)
    extracted.full_text = "Hello world. " * 500
    extracted.pages = []
    mock_document_repo.get_extracted_text_by_version_id.return_value = extracted
    mock_document_repo.get_document_by_id.return_value = context.document

    mock_chunk_repo.create_chunks_bulk.return_value = [
        AsyncMock(chunk_index=0),
        AsyncMock(chunk_index=1),
    ]

    await processor.process(context)

    mock_document_repo.update_ingestion_job.assert_awaited_with(
        context.job.id,
        stage=ProcessingStage.CHUNKING.value,
    )
    mock_chunk_repo.create_chunks_bulk.assert_awaited()


@pytest.mark.asyncio
async def test_process_uses_language_from_metadata(
    processor: ChunkingProcessor,
    mock_document_repo: AsyncMock,
    mock_chunk_repo: AsyncMock,
    context: ProcessingContext,
) -> None:
    extracted = AsyncMock(spec=DocumentExtractedText)
    extracted.full_text = "Hello world. " * 500
    extracted.pages = []
    mock_document_repo.get_extracted_text_by_version_id.return_value = extracted
    mock_document_repo.get_document_by_id.return_value = context.document
    mock_chunk_repo.create_chunks_bulk.return_value = [AsyncMock(chunk_index=0)]

    await processor.process(context)

    call_kwargs = mock_chunk_repo.create_chunks_bulk.await_args[0][0]
    for chunk in call_kwargs:
        assert chunk["extra_metadata"]["language"] == "en"


@pytest.mark.asyncio
async def test_process_raises_chunking_error(
    processor: ChunkingProcessor,
    mock_document_repo: AsyncMock,
    context: ProcessingContext,
) -> None:
    extracted = AsyncMock(spec=DocumentExtractedText)
    extracted.full_text = "Some text"
    extracted.pages = []
    mock_document_repo.get_extracted_text_by_version_id.return_value = extracted
    mock_document_repo.get_document_by_id.side_effect = RuntimeError("DB error")

    with pytest.raises(ChunkingError, match="DB error"):
        await processor.process(context)
