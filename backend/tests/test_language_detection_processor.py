import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.document import Document
from app.models.document_extracted_text import DocumentExtractedText
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.services.language_detection import DETECTED_LANGUAGE_KEY
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext
from app.services.processors.language_detection import LanguageDetectionProcessor


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
def mock_repository(processing_context: ProcessingContext) -> AsyncMock:
    repository = AsyncMock()
    repository.get_document_by_id.return_value = processing_context.document
    repository.get_extracted_text_by_version_id.return_value = DocumentExtractedText(
        id=uuid.uuid4(),
        document_version_id=processing_context.version.id,
        full_text=(
            "This safety procedure describes the inspection steps for pressure relief "
            "valves and associated piping systems."
        ),
        pages=[],
        extraction_method="pymupdf",
        requires_ocr=False,
    )
    repository.update_document.return_value = MagicMock()
    repository.update_ingestion_job.return_value = MagicMock()
    return repository


@pytest.fixture
def processor(mock_repository: AsyncMock) -> LanguageDetectionProcessor:
    return LanguageDetectionProcessor(document_repository=mock_repository)


@pytest.mark.asyncio
async def test_language_detection_processor_persists_detected_language(
    processor: LanguageDetectionProcessor,
    mock_repository: AsyncMock,
    processing_context: ProcessingContext,
) -> None:
    await processor.process(processing_context)

    mock_repository.update_ingestion_job.assert_awaited_with(
        processing_context.job.id,
        stage=ProcessingStage.LANGUAGE_DETECTION.value,
    )
    metadata_update = mock_repository.update_document.await_args.kwargs
    detected = metadata_update["extra_metadata"][DETECTED_LANGUAGE_KEY]
    assert detected["code"] == "en"
    assert detected["confidence"] is not None
    assert metadata_update["extra_metadata"]["department"] == "Engineering"


@pytest.mark.asyncio
async def test_language_detection_processor_handles_missing_extracted_text(
    processor: LanguageDetectionProcessor,
    mock_repository: AsyncMock,
    processing_context: ProcessingContext,
) -> None:
    mock_repository.get_extracted_text_by_version_id.return_value = None

    await processor.process(processing_context)

    detected = mock_repository.update_document.await_args.kwargs["extra_metadata"][
        DETECTED_LANGUAGE_KEY
    ]
    assert detected["code"] == "unknown"
    assert detected["confidence"] is None


@pytest.mark.asyncio
async def test_language_detection_processor_handles_empty_extracted_text(
    processor: LanguageDetectionProcessor,
    mock_repository: AsyncMock,
    processing_context: ProcessingContext,
) -> None:
    mock_repository.get_extracted_text_by_version_id.return_value = DocumentExtractedText(
        id=uuid.uuid4(),
        document_version_id=processing_context.version.id,
        full_text="",
        pages=[],
        extraction_method="pymupdf",
        requires_ocr=True,
    )

    await processor.process(processing_context)

    detected = mock_repository.update_document.await_args.kwargs["extra_metadata"][
        DETECTED_LANGUAGE_KEY
    ]
    assert detected["code"] == "unknown"
    assert detected["confidence"] is None
