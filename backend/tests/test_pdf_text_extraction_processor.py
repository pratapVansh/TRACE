import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import fitz
import pytest

from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.services.document_processing_exceptions import PdfTextExtractionError
from app.services.processing_status import ProcessingStage
from app.services.processors.pdf_text_extraction import PdfTextExtractionProcessor
from app.services.processors.base import ProcessingContext


def _build_text_pdf(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    content = document.tobytes()
    document.close()
    return content


@pytest.fixture
def pdf_bytes() -> bytes:
    return _build_text_pdf("Processor test content")


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
        extra_metadata={},
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
def mock_repository() -> AsyncMock:
    repository = AsyncMock()
    repository.upsert_extracted_text.return_value = MagicMock()
    repository.update_document_version.return_value = MagicMock()
    repository.update_document.return_value = MagicMock()
    repository.update_ingestion_job.return_value = MagicMock()
    return repository


@pytest.fixture
def processor(mock_storage: MagicMock, mock_repository: AsyncMock) -> PdfTextExtractionProcessor:
    return PdfTextExtractionProcessor(
        storage=mock_storage,
        document_repository=mock_repository,
    )


@pytest.mark.asyncio
async def test_pdf_processor_extracts_and_persists_text(
    processor: PdfTextExtractionProcessor,
    mock_storage: MagicMock,
    mock_repository: AsyncMock,
    processing_context: ProcessingContext,
) -> None:
    await processor.process(processing_context)

    mock_storage.read.assert_called_once_with(processing_context.version.storage_uri)
    mock_repository.update_ingestion_job.assert_awaited_with(
        processing_context.job.id,
        stage=ProcessingStage.TEXT_EXTRACTION.value,
    )
    mock_repository.upsert_extracted_text.assert_awaited_once()
    saved_payload = mock_repository.upsert_extracted_text.await_args.kwargs
    assert saved_payload["document_version_id"] == processing_context.version.id
    assert "Processor test content" in saved_payload["full_text"]
    assert saved_payload["requires_ocr"] is False
    mock_repository.update_document_version.assert_awaited_with(
        processing_context.version.id,
        page_count=1,
    )


@pytest.mark.asyncio
async def test_pdf_processor_skips_non_pdf_documents(
    processor: PdfTextExtractionProcessor,
    mock_storage: MagicMock,
    mock_repository: AsyncMock,
    processing_context: ProcessingContext,
) -> None:
    processing_context.version.file_extension = "txt"

    await processor.process(processing_context)

    mock_storage.read.assert_not_called()
    mock_repository.upsert_extracted_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_pdf_processor_marks_scanned_pdf_for_ocr(
    processor: PdfTextExtractionProcessor,
    mock_storage: MagicMock,
    mock_repository: AsyncMock,
    processing_context: ProcessingContext,
) -> None:
    blank_pdf = fitz.open()
    blank_pdf.new_page()
    mock_storage.read.return_value = blank_pdf.tobytes()
    blank_pdf.close()

    await processor.process(processing_context)

    saved_payload = mock_repository.upsert_extracted_text.await_args.kwargs
    assert saved_payload["requires_ocr"] is True
    metadata_update = mock_repository.update_document.await_args.kwargs
    assert metadata_update["extra_metadata"]["requires_ocr"] is True


@pytest.mark.asyncio
async def test_pdf_processor_raises_when_storage_read_fails(
    processor: PdfTextExtractionProcessor,
    mock_storage: MagicMock,
    processing_context: ProcessingContext,
) -> None:
    from app.core.storage.exceptions import StorageError

    mock_storage.read.side_effect = StorageError("missing")

    with pytest.raises(PdfTextExtractionError, match="Failed to read stored PDF"):
        await processor.process(processing_context)
