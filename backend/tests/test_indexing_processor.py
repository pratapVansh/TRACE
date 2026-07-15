"""Unit tests for IndexingProcessor."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.services.document_processing_exceptions import IndexingError
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext
from app.services.processors.indexing_processor import IndexingProcessor


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
        stage="embedding",
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
def mock_indexing_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def processor(
    mock_session: AsyncMock,
    mock_document_repo: AsyncMock,
    mock_chunk_repo: AsyncMock,
    mock_indexing_service: AsyncMock,
) -> IndexingProcessor:
    return IndexingProcessor(
        session=mock_session,
        document_repository=mock_document_repo,
        chunk_repository=mock_chunk_repo,
        indexing_service=mock_indexing_service,
    )


@pytest.mark.asyncio
async def test_processor_name(processor: IndexingProcessor) -> None:
    assert processor.name == "indexing"


@pytest.mark.asyncio
async def test_process_success(
    processor: IndexingProcessor,
    mock_document_repo: AsyncMock,
    mock_chunk_repo: AsyncMock,
    mock_indexing_service: AsyncMock,
    context: ProcessingContext,
) -> None:
    document_id = context.document.id
    mock_chunk_repo.get_chunks_by_document.return_value = [
        DocumentChunk(
            id=uuid.uuid4(),
            document_id=document_id,
            chunk_index=0,
            content="chunk content",
            embedding=[0.1] * 384,
            embedding_status="completed",
        ),
    ]
    mock_indexing_service.index_document_chunks.return_value = 1

    await processor.process(context)

    mock_document_repo.update_ingestion_job.assert_awaited_with(
        context.job.id,
        stage=ProcessingStage.INDEXING.value,
    )
    mock_chunk_repo.get_chunks_by_document.assert_awaited_with(
        document_id,
        embedding_status="completed",
    )
    mock_indexing_service.index_document_chunks.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_no_chunks(
    processor: IndexingProcessor,
    mock_chunk_repo: AsyncMock,
    mock_indexing_service: AsyncMock,
    context: ProcessingContext,
) -> None:
    mock_chunk_repo.get_chunks_by_document.return_value = []

    await processor.process(context)

    mock_indexing_service.index_document_chunks.assert_not_called()


@pytest.mark.asyncio
async def test_process_raises_indexing_error(
    processor: IndexingProcessor,
    mock_chunk_repo: AsyncMock,
    mock_indexing_service: AsyncMock,
    context: ProcessingContext,
) -> None:
    document_id = context.document.id
    mock_chunk_repo.get_chunks_by_document.return_value = [
        DocumentChunk(
            id=uuid.uuid4(),
            document_id=document_id,
            chunk_index=0,
            content="chunk content",
            embedding=[0.1] * 384,
            embedding_status="completed",
        ),
    ]
    mock_indexing_service.index_document_chunks.side_effect = RuntimeError("Qdrant down")

    with pytest.raises(IndexingError, match="Qdrant down"):
        await processor.process(context)
