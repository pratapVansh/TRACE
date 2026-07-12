"""Unit tests for EmbeddingProcessor."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.services.document_processing_exceptions import EmbeddingError
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext
from app.services.processors.embedding_processor import EmbeddingProcessor


@pytest.fixture
def document_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_document(document_id: uuid.UUID) -> Document:
    doc = Document(
        id=document_id,
        title="Test",
        original_filename="test.pdf",
        doc_type="manual",
        status="processing",
        extra_metadata={},
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
        checksum_sha256="abc",
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
        stage="chunking",
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
def mock_embedding_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def processor(
    mock_session: AsyncMock,
    mock_document_repo: AsyncMock,
    mock_chunk_repo: AsyncMock,
    mock_embedding_service: AsyncMock,
) -> EmbeddingProcessor:
    return EmbeddingProcessor(
        session=mock_session,
        document_repository=mock_document_repo,
        chunk_repository=mock_chunk_repo,
        embedding_service=mock_embedding_service,
    )


@pytest.mark.asyncio
async def test_processor_name(processor: EmbeddingProcessor) -> None:
    assert processor.name == "embedding"


@pytest.mark.asyncio
async def test_process_success(
    processor: EmbeddingProcessor,
    mock_document_repo: AsyncMock,
    mock_embedding_service: AsyncMock,
    context: ProcessingContext,
) -> None:
    mock_embedding_service.generate_for_document.return_value = 3

    await processor.process(context)

    mock_document_repo.update_ingestion_job.assert_awaited_with(
        context.job.id,
        stage=ProcessingStage.EMBEDDING.value,
    )
    mock_embedding_service.generate_for_document.assert_awaited_with(
        context.document.id,
    )


@pytest.mark.asyncio
async def test_process_no_chunks_to_embed(
    processor: EmbeddingProcessor,
    mock_document_repo: AsyncMock,
    mock_embedding_service: AsyncMock,
    context: ProcessingContext,
) -> None:
    mock_embedding_service.generate_for_document.return_value = 0

    await processor.process(context)

    mock_embedding_service.generate_for_document.assert_awaited_with(
        context.document.id,
    )


@pytest.mark.asyncio
async def test_process_raises_embedding_error(
    processor: EmbeddingProcessor,
    mock_document_repo: AsyncMock,
    mock_embedding_service: AsyncMock,
    context: ProcessingContext,
) -> None:
    mock_embedding_service.generate_for_document.side_effect = RuntimeError("Model crash")

    with pytest.raises(EmbeddingError, match="Model crash"):
        await processor.process(context)

    mock_document_repo.update_ingestion_job.assert_awaited()
