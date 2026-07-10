import uuid
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.services.document_processing_exceptions import ImageOcrExtractionError
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext
from app.services.processors.image_ocr_extraction import ImageOcrExtractionProcessor


def _build_png() -> bytes:
    image = Image.new("RGB", (120, 60), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def png_bytes() -> bytes:
    return _build_png()


@pytest.fixture
def processing_context() -> ProcessingContext:
    document_id = uuid.uuid4()
    version_id = uuid.uuid4()
    document = Document(
        id=document_id,
        title="Label Photo",
        original_filename="label.png",
        doc_type="image",
        status="processing",
        uploaded_by=None,
        extra_metadata={},
    )
    version = DocumentVersion(
        id=version_id,
        document_id=document_id,
        version_no=1,
        storage_uri="documents/test/v1/label.png",
        checksum_sha256="abc123",
        mime_type="image/png",
        file_extension="png",
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
def mock_storage(png_bytes: bytes) -> MagicMock:
    storage = MagicMock()
    storage.read.return_value = png_bytes
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
def processor(mock_storage: MagicMock, mock_repository: AsyncMock) -> ImageOcrExtractionProcessor:
    return ImageOcrExtractionProcessor(
        storage=mock_storage,
        document_repository=mock_repository,
    )


@pytest.mark.asyncio
@patch(
    "app.services.image_ocr_extraction.pytesseract.image_to_string",
    return_value="P-101",
)
async def test_image_ocr_processor_extracts_and_persists_text(
    _mock_ocr,
    processor: ImageOcrExtractionProcessor,
    mock_storage: MagicMock,
    mock_repository: AsyncMock,
    processing_context: ProcessingContext,
) -> None:
    await processor.process(processing_context)

    mock_storage.read.assert_called_once_with(processing_context.version.storage_uri)
    mock_repository.update_ingestion_job.assert_awaited_with(
        processing_context.job.id,
        stage=ProcessingStage.OCR.value,
    )
    saved_payload = mock_repository.upsert_extracted_text.await_args.kwargs
    assert saved_payload["full_text"] == "P-101"
    assert saved_payload["extraction_method"] == "tesseract"
    assert saved_payload["requires_ocr"] is False
    mock_repository.update_document_version.assert_awaited_with(
        processing_context.version.id,
        page_count=1,
    )


@pytest.mark.asyncio
async def test_image_ocr_processor_skips_non_image_documents(
    processor: ImageOcrExtractionProcessor,
    mock_storage: MagicMock,
    mock_repository: AsyncMock,
    processing_context: ProcessingContext,
) -> None:
    processing_context.version.file_extension = "pdf"

    await processor.process(processing_context)

    mock_storage.read.assert_not_called()
    mock_repository.upsert_extracted_text.assert_not_awaited()


@pytest.mark.asyncio
@patch(
    "app.services.image_ocr_extraction.pytesseract.image_to_string",
    return_value="",
)
async def test_image_ocr_processor_marks_empty_ocr_for_review(
    _mock_ocr,
    processor: ImageOcrExtractionProcessor,
    mock_repository: AsyncMock,
    processing_context: ProcessingContext,
) -> None:
    await processor.process(processing_context)

    metadata_update = mock_repository.update_document.await_args.kwargs
    assert metadata_update["extra_metadata"]["ocr_no_text"] is True


@pytest.mark.asyncio
async def test_image_ocr_processor_raises_when_storage_read_fails(
    processor: ImageOcrExtractionProcessor,
    mock_storage: MagicMock,
    processing_context: ProcessingContext,
) -> None:
    from app.core.storage.exceptions import StorageError

    mock_storage.read.side_effect = StorageError("missing")

    with pytest.raises(ImageOcrExtractionError, match="Failed to read stored image"):
        await processor.process(processing_context)
