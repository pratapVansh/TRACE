import uuid
from unittest.mock import AsyncMock, MagicMock

import fitz
import pytest

from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.services.document_processing_exceptions import MetadataExtractionError
from app.services.metadata_extraction import FILE_METADATA_KEY
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext
from app.services.processors.metadata_extraction import MetadataExtractionProcessor


def _build_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Metadata processor test")
    document.set_metadata({"author": "Processor Author"})
    content = document.tobytes()
    document.close()
    return content


@pytest.fixture
def pdf_bytes() -> bytes:
    return _build_pdf()


@pytest.fixture
def processing_context() -> ProcessingContext:
    document_id = uuid.uuid4()
    version_id = uuid.uuid4()
    document = Document(
        id=document_id,
        title="Manual",
        original_filename="manual.pdf",
        doc_type="manual",
        status="processing",
        uploaded_by=None,
        extra_metadata={"department": "Engineering"},
    )
    version = DocumentVersion(
        id=version_id,
        document_id=document_id,
        version_no=1,
        storage_uri="documents/test/v1/manual.pdf",
        checksum_sha256="abc123",
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=1024,
        is_latest=True,
    )
    job = IngestionJob(
        id=uuid.uuid4(),
        document_id=document_id,
        status="processing",
        stage=ProcessingStage.PROCESSING.value,
    )
    return ProcessingContext(document=document, version=version, job=job)


@pytest.fixture
def mock_storage(pdf_bytes: bytes) -> MagicMock:
    storage = MagicMock()
    storage.read.return_value = pdf_bytes
    return storage


@pytest.fixture
def mock_repository(processing_context: ProcessingContext) -> AsyncMock:
    repository = AsyncMock()
    repository.get_document_by_id.return_value = processing_context.document
    repository.update_document.return_value = MagicMock()
    repository.update_document_version.return_value = MagicMock()
    repository.update_ingestion_job.return_value = MagicMock()
    return repository


@pytest.fixture
def processor(mock_storage: MagicMock, mock_repository: AsyncMock) -> MetadataExtractionProcessor:
    return MetadataExtractionProcessor(
        storage=mock_storage,
        document_repository=mock_repository,
    )


@pytest.mark.asyncio
async def test_metadata_processor_persists_file_metadata(
    processor: MetadataExtractionProcessor,
    mock_storage: MagicMock,
    mock_repository: AsyncMock,
    processing_context: ProcessingContext,
) -> None:
    await processor.process(processing_context)

    mock_storage.read.assert_called_once_with(processing_context.version.storage_uri)
    mock_repository.update_ingestion_job.assert_awaited_with(
        processing_context.job.id,
        stage=ProcessingStage.METADATA_EXTRACTION.value,
    )
    metadata_update = mock_repository.update_document.await_args.kwargs
    file_metadata = metadata_update["extra_metadata"][FILE_METADATA_KEY]
    assert file_metadata["author"] == "Processor Author"
    assert file_metadata["file_type"] == "application/pdf"
    assert file_metadata["file_extension"] == "pdf"
    assert file_metadata["page_count"] == 1
    assert metadata_update["extra_metadata"]["department"] == "Engineering"
    mock_repository.update_document_version.assert_awaited_with(
        processing_context.version.id,
        page_count=1,
    )


@pytest.mark.asyncio
async def test_metadata_processor_does_not_overwrite_existing_page_count(
    processor: MetadataExtractionProcessor,
    mock_repository: AsyncMock,
    processing_context: ProcessingContext,
) -> None:
    processing_context.version.page_count = 9

    await processor.process(processing_context)

    mock_repository.update_document_version.assert_not_awaited()
    file_metadata = mock_repository.update_document.await_args.kwargs["extra_metadata"][
        FILE_METADATA_KEY
    ]
    assert file_metadata["page_count"] == 9


@pytest.mark.asyncio
async def test_metadata_processor_raises_when_storage_read_fails(
    processor: MetadataExtractionProcessor,
    mock_storage: MagicMock,
    processing_context: ProcessingContext,
) -> None:
    from app.core.storage.exceptions import StorageError

    mock_storage.read.side_effect = StorageError("missing")

    with pytest.raises(MetadataExtractionError, match="Failed to read stored file"):
        await processor.process(processing_context)
