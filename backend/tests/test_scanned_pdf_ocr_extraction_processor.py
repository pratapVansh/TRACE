import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import fitz
import pytest

from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.services.document_processing_exceptions import ScannedPdfOcrExtractionError
from app.services.image_ocr_extraction import ImageOcrExtractionResult
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext
from app.services.processors.scanned_pdf_ocr_extraction import ScannedPdfOcrProcessor
from app.services.scanned_pdf_ocr_extraction import ScannedPdfOcrResult
from app.services.pdf_text_extraction import ExtractedPage


def _build_blank_pdf() -> bytes:
    document = fitz.open()
    document.new_page()
    content = document.tobytes()
    document.close()
    return content


@pytest.fixture
def blank_pdf_bytes() -> bytes:
    return _build_blank_pdf()


@pytest.fixture
def processing_context() -> ProcessingContext:
    document_id = uuid.uuid4()
    version_id = uuid.uuid4()
    document = Document(
        id=document_id,
        title="Scanned Manual",
        original_filename="manual.pdf",
        doc_type="manual",
        status="processing",
        uploaded_by=None,
        extra_metadata={"requires_ocr": True},
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
        stage=ProcessingStage.TEXT_EXTRACTION.value,
    )
    return ProcessingContext(document=document, version=version, job=job)


@pytest.fixture
def mock_storage(blank_pdf_bytes: bytes) -> MagicMock:
    storage = MagicMock()
    storage.read.return_value = blank_pdf_bytes
    return storage


@pytest.fixture
def mock_repository(processing_context: ProcessingContext) -> AsyncMock:
    repository = AsyncMock()
    repository.get_document_by_id.return_value = processing_context.document
    repository.upsert_extracted_text.return_value = MagicMock()
    repository.update_document_version.return_value = MagicMock()
    repository.update_document.return_value = MagicMock()
    repository.update_ingestion_job.return_value = MagicMock()
    return repository


@pytest.fixture
def processor(mock_storage: MagicMock, mock_repository: AsyncMock) -> ScannedPdfOcrProcessor:
    return ScannedPdfOcrProcessor(
        storage=mock_storage,
        document_repository=mock_repository,
    )


@pytest.mark.asyncio
@patch("app.services.processors.scanned_pdf_ocr_extraction.extract_scanned_pdf_text")
async def test_scanned_pdf_processor_persists_merged_ocr_text(
    mock_extract,
    processor: ScannedPdfOcrProcessor,
    mock_storage: MagicMock,
    mock_repository: AsyncMock,
    processing_context: ProcessingContext,
) -> None:
    mock_extract.return_value = ScannedPdfOcrResult(
        pages=(ExtractedPage(page_number=1, text="OCR page text"),),
        full_text="OCR page text",
        page_count=1,
        has_text=True,
    )

    await processor.process(processing_context)

    mock_storage.read.assert_called_once()
    mock_repository.update_ingestion_job.assert_awaited_with(
        processing_context.job.id,
        stage=ProcessingStage.OCR.value,
    )
    saved_payload = mock_repository.upsert_extracted_text.await_args.kwargs
    assert saved_payload["full_text"] == "OCR page text"
    assert saved_payload["extraction_method"] == "pymupdf+tesseract"
    assert saved_payload["requires_ocr"] is False
    metadata_update = mock_repository.update_document.await_args.kwargs
    assert "requires_ocr" not in metadata_update["extra_metadata"]


@pytest.mark.asyncio
@patch(
    "app.services.processors.scanned_pdf_ocr_extraction.extract_scanned_pdf_text",
    return_value=None,
)
async def test_scanned_pdf_processor_skips_text_based_pdf(
    _mock_extract,
    processor: ScannedPdfOcrProcessor,
    mock_repository: AsyncMock,
    processing_context: ProcessingContext,
) -> None:
    await processor.process(processing_context)

    mock_repository.upsert_extracted_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_scanned_pdf_processor_skips_non_pdf_documents(
    processor: ScannedPdfOcrProcessor,
    mock_storage: MagicMock,
    mock_repository: AsyncMock,
    processing_context: ProcessingContext,
) -> None:
    processing_context.version.file_extension = "png"

    await processor.process(processing_context)

    mock_storage.read.assert_not_called()
    mock_repository.upsert_extracted_text.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.services.processors.scanned_pdf_ocr_extraction.extract_scanned_pdf_text")
async def test_scanned_pdf_processor_clears_requires_ocr_after_success(
    mock_extract,
    processor: ScannedPdfOcrProcessor,
    mock_repository: AsyncMock,
    processing_context: ProcessingContext,
) -> None:
    mock_extract.return_value = ScannedPdfOcrResult(
        pages=(ExtractedPage(page_number=1, text="Recovered text"),),
        full_text="Recovered text",
        page_count=1,
        has_text=True,
    )

    await processor.process(processing_context)

    metadata_update = mock_repository.update_document.await_args.kwargs
    assert metadata_update["extra_metadata"].get("requires_ocr") is None
    assert metadata_update["extra_metadata"].get("ocr_no_text") is None


@pytest.mark.asyncio
async def test_scanned_pdf_processor_raises_when_storage_read_fails(
    processor: ScannedPdfOcrProcessor,
    mock_storage: MagicMock,
    processing_context: ProcessingContext,
) -> None:
    from app.core.storage.exceptions import StorageError

    mock_storage.read.side_effect = StorageError("missing")

    with pytest.raises(ScannedPdfOcrExtractionError, match="Failed to read stored PDF"):
        await processor.process(processing_context)
