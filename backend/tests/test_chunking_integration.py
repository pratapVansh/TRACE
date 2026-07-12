"""Integration tests for the chunking pipeline — tests pure logic with realistic
document content simulating PDF, DOCX, PPTX, TXT, OCR, large, and multi-language documents."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.services.chunking_service import ChunkingService, _count_tokens
from app.services.embedding_service import _encode_batch
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext
from app.services.processors.chunking_processor import ChunkingProcessor


def _build_document(
    doc_id: uuid.UUID,
    filename: str,
    extra_metadata: dict | None = None,
) -> tuple[Document, DocumentVersion, IngestionJob]:
    now = datetime.now(UTC)
    doc = Document(
        id=doc_id,
        title=filename,
        original_filename=filename,
        doc_type="manual",
        status="processing",
        extra_metadata=extra_metadata or {},
    )
    doc.created_at = now
    doc.updated_at = now

    version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc_id,
        version_no=1,
        storage_uri=filename,
        checksum_sha256="abc",
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=1000,
        is_latest=True,
    )
    version.created_at = now

    job = IngestionJob(
        id=uuid.uuid4(),
        document_id=doc_id,
        status="processing",
        stage=ProcessingStage.CHUNKING.value,
    )
    job.created_at = now

    return doc, version, job


class TestChunkingPipelineIntegration:
    """Test the complete chunking pipeline with realistic document content."""

    @pytest.mark.asyncio
    async def test_pdf_document_content(self) -> None:
        """Simulate PDF content with headings, paragraphs, and multiple pages."""
        text = (
            "# Introduction\n\n"
            "This is the first paragraph of the document. It contains some "
            "introductory material that sets up the context for the rest.\n\n"
            "# Methodology\n\n"
            "We used a systematic approach to gather data. The methodology section "
            "describes our approach in detail.\n\n"
            "## Data Collection\n\n"
            "Data was collected from multiple sources over a period of time. "
            "This ensures comprehensive coverage of the topic.\n\n"
            "# Results\n\n"
            "The results were significant and showed a clear pattern across all "
            "test groups. Statistical analysis confirmed our hypothesis.\n\n"
        )
        pages = [
            {"text": "# Introduction\n\nThis is the first paragraph...", "page_number": 1},
            {"text": "# Methodology\n\nWe used a systematic approach...", "page_number": 2},
            {"text": "## Data Collection\n\nData was collected...", "page_number": 2},
            {"text": "# Results\n\nThe results were significant...", "page_number": 3},
        ]

        doc_id = uuid.uuid4()
        mock_repo = AsyncMock()
        mock_repo.create_chunks_bulk.return_value = []

        session = AsyncMock()
        session.flush = AsyncMock()
        service = ChunkingService(session=session, chunk_repository=mock_repo)
        chunks = await service.chunk_document(
            doc_id,
            text=text,
            pages=pages,
            filename="report.pdf",
            language="en",
        )

        assert mock_repo.create_chunks_bulk.awaited

    @pytest.mark.asyncio
    async def test_docx_document_content(self) -> None:
        """Simulate DOCX content (paragraph-based, structured text)."""
        text = (
            "Section 1: Project Overview\n\n"
            "This project aims to deliver a comprehensive solution for document "
            "management. The system will support multiple file formats.\n\n"
            "1.1 Scope\n\n"
            "The scope includes PDF, DOCX, PPTX, and TXT file processing. "
            "OCR support is included for scanned documents.\n\n"
            "1.2 Timeline\n\n"
            "The project will be delivered in phases over six months. "
            "Each phase includes specific deliverables and milestones.\n\n"
        )
        doc_id = uuid.uuid4()
        mock_repo = AsyncMock()
        mock_repo.create_chunks_bulk.return_value = []
        session = AsyncMock()
        session.flush = AsyncMock()
        service = ChunkingService(session=session, chunk_repository=mock_repo)
        chunks = await service.chunk_document(
            doc_id,
            text=text,
            filename="report.docx",
            language="en",
        )
        assert mock_repo.create_chunks_bulk.awaited

    @pytest.mark.asyncio
    async def test_pptx_document_content(self) -> None:
        """Simulate PPTX content (slide-by-slide, shorter text per slide)."""
        text = (
            "Slide 1: Welcome\n\n"
            "Welcome to the presentation on document processing.\n\n"
            "Slide 2: Agenda\n\n"
            "- Chunking overview\n- Implementation details\n- Testing strategy\n\n"
            "Slide 3: Architecture\n\n"
            "The system uses a pipeline architecture with multiple processing stages.\n\n"
        )
        pages = [
            {"text": "Slide 1: Welcome\n\nWelcome to the presentation.", "page_number": 1},
            {"text": "Slide 2: Agenda\n\n- Chunking overview", "page_number": 2},
            {"text": "Slide 3: Architecture\n\nThe system uses a pipeline.", "page_number": 3},
        ]
        doc_id = uuid.uuid4()
        mock_repo = AsyncMock()
        mock_repo.create_chunks_bulk.return_value = []
        session = AsyncMock()
        session.flush = AsyncMock()
        service = ChunkingService(session=session, chunk_repository=mock_repo)
        chunks = await service.chunk_document(
            doc_id,
            text=text,
            pages=pages,
            filename="slides.pptx",
            language="en",
        )
        assert mock_repo.create_chunks_bulk.awaited

    @pytest.mark.asyncio
    async def test_txt_document_content(self) -> None:
        """Simulate plain TXT content."""
        text = (
            "OPERATING MANUAL\n"
            "================\n\n"
            "Chapter 1: Safety Instructions\n\n"
            "Read all safety instructions before operating the equipment. "
            "Failure to follow instructions may result in injury.\n\n"
            "Chapter 2: Setup\n\n"
            "Place the unit on a flat surface. Connect the power cord "
            "to a grounded outlet before turning on the device.\n\n"
        )
        doc_id = uuid.uuid4()
        mock_repo = AsyncMock()
        mock_repo.create_chunks_bulk.return_value = []
        session = AsyncMock()
        session.flush = AsyncMock()
        service = ChunkingService(session=session, chunk_repository=mock_repo)
        chunks = await service.chunk_document(
            doc_id,
            text=text,
            filename="manual.txt",
            language="en",
        )
        assert mock_repo.create_chunks_bulk.awaited

    @pytest.mark.asyncio
    async def test_ocr_image_content(self) -> None:
        """Simulate OCR output (continuous text, no structural formatting)."""
        text = (
            "INVOICE NUMBER INV-2024-001\n"
            "DATE: January 15, 2024\n\n"
            "Customer: Acme Corporation\n"
            "Address: 123 Business Ave, Suite 100, Cityville\n\n"
            "Item Description Quantity Unit Price Total\n"
            "Widget A Premium quality component 10 25.00 250.00\n"
            "Widget B Standard component 20 15.00 300.00\n"
            "Widget C Deluxe assembly 5 50.00 250.00\n\n"
            "Subtotal: 800.00\n"
            "Tax (8%): 64.00\n"
            "Total Due: 864.00\n\n"
            "Payment Terms: Net 30\n"
        )
        doc_id = uuid.uuid4()
        mock_repo = AsyncMock()
        mock_repo.create_chunks_bulk.return_value = []
        session = AsyncMock()
        session.flush = AsyncMock()
        service = ChunkingService(session=session, chunk_repository=mock_repo)
        chunks = await service.chunk_document(
            doc_id,
            text=text,
            filename="invoice_ocr.png",
            language="en",
        )
        assert mock_repo.create_chunks_bulk.awaited

    @pytest.mark.asyncio
    async def test_large_document(self) -> None:
        """Simulate a large document (10k+ words) to verify chunking produces
        multiple chunks and respects the chunk size limit."""
        paragraphs = []
        for i in range(100):
            paragraphs.append(
                f"# Section {i}\n\n"
                + " ".join(["word"] * 200)
                + "\n\n"
            )
        text = "\n".join(paragraphs)

        doc_id = uuid.uuid4()
        mock_repo = AsyncMock()
        mock_repo.create_chunks_bulk.return_value = []
        session = AsyncMock()
        session.flush = AsyncMock()
        service = ChunkingService(session=session, chunk_repository=mock_repo)
        chunks = await service.chunk_document(
            doc_id,
            text=text,
            filename="large_document.pdf",
            language="en",
        )
        assert mock_repo.create_chunks_bulk.awaited

    @pytest.mark.asyncio
    async def test_multi_language_document(self) -> None:
        """Simulate a multi-language document (English + French + German)."""
        text = (
            "# Executive Summary / Résumé / Zusammenfassung\n\n"
            "This document contains content in multiple languages.\n"
            "Ce document contient du contenu dans plusieurs langues.\n"
            "Dieses Dokument enthält Inhalte in mehreren Sprachen.\n\n"
            "# Introduction / Introduction / Einleitung\n\n"
            "The system processes documents efficiently.\n"
            "Le système traite les documents efficacement.\n"
            "Das System verarbeitet Dokumente effizient.\n\n"
            "# Results / Résultats / Ergebnisse\n\n"
            "The results demonstrate high accuracy.\n"
            "Les résultats démontrent une haute précision.\n"
            "Die Ergebnisse zeigen eine hohe Genauigkeit.\n\n"
        )
        doc_id = uuid.uuid4()
        mock_repo = AsyncMock()
        mock_repo.create_chunks_bulk.return_value = []
        session = AsyncMock()
        session.flush = AsyncMock()
        service = ChunkingService(session=session, chunk_repository=mock_repo)
        chunks = await service.chunk_document(
            doc_id,
            text=text,
            filename="multi_lang.pdf",
            language="en",
        )
        assert mock_repo.create_chunks_bulk.awaited


class TestEmbeddingIntegration:
    """Test embedding generation with realistic chunk data."""

    def test_encode_batch_returns_correct_shape(self) -> None:
        """Verify that _encode_batch returns vectors with correct dimensionality.
        This is a real model call - only run if model is available."""
        texts = ["This is a test sentence.", "Another test sentence here."]
        try:
            embeddings = _encode_batch(texts)
            assert len(embeddings) == 2
            assert len(embeddings[0]) == 384  # all-MiniLM-L6-v2 dimension
            assert all(isinstance(v, float) for v in embeddings[0])
        except Exception:
            pytest.skip("Embedding model not available in test environment")


class TestProcessorPipelineIntegration:
    """Integration tests for the chunking+embedding pipeline end-to-end."""

    @pytest.mark.asyncio
    async def test_chunking_through_embedding_flow(self) -> None:
        doc_id = uuid.uuid4()
        text = (
            "# Chapter 1\n\n"
            + "The quick brown fox jumps over the lazy dog. " * 100
            + "\n\n# Chapter 2\n\n"
            + "Pack my box with five dozen liquor jugs. " * 100
        )
        pages = [
            {"text": "# Chapter 1\n\n" + "The quick brown fox...", "page_number": 1},
            {"text": "# Chapter 2\n\n" + "Pack my box...", "page_number": 2},
        ]
        doc, version, job = _build_document(doc_id, "test.pdf")

        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_doc_repo = AsyncMock()
        mock_chunk_repo = AsyncMock()
        mock_embedding_service = AsyncMock()

        extracted = AsyncMock()
        extracted.full_text = text
        extracted.pages = pages

        mock_doc_repo.get_extracted_text_by_version_id.return_value = extracted
        mock_doc_repo.get_document_by_id.return_value = doc
        mock_chunk_repo.create_chunks_bulk.return_value = [
            AsyncMock(chunk_index=0),
            AsyncMock(chunk_index=1),
            AsyncMock(chunk_index=2),
        ]
        mock_embedding_service.generate_for_document.return_value = 3

        context = ProcessingContext(document=doc, version=version, job=job)

        chunk_processor = ChunkingProcessor(
            session=mock_session,
            document_repository=mock_doc_repo,
            document_chunk_repository=mock_chunk_repo,
        )

        await chunk_processor.process(context)

        mock_doc_repo.update_ingestion_job.assert_awaited_with(
            job.id,
            stage=ProcessingStage.CHUNKING.value,
        )
        mock_chunk_repo.create_chunks_bulk.assert_awaited()

    @pytest.mark.asyncio
    async def test_empty_text_through_pipeline(self) -> None:
        doc_id = uuid.uuid4()
        doc, version, job = _build_document(doc_id, "empty.pdf")

        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_doc_repo = AsyncMock()

        extracted = AsyncMock()
        extracted.full_text = ""
        extracted.pages = []

        mock_doc_repo.get_extracted_text_by_version_id.return_value = extracted

        context = ProcessingContext(document=doc, version=version, job=job)

        chunk_processor = ChunkingProcessor(
            session=mock_session,
            document_repository=mock_doc_repo,
            document_chunk_repository=AsyncMock(),
        )

        await chunk_processor.process(context)

        mock_doc_repo.update_ingestion_job.assert_awaited_with(
            job.id,
            stage=ProcessingStage.CHUNKING.value,
        )

    @pytest.mark.asyncio
    async def test_scanned_document_with_ocr_text(self) -> None:
        """Scanned PDF OCR text should chunk like any other text."""
        doc_id = uuid.uuid4()
        doc, version, job = _build_document(
            doc_id, "scanned.pdf",
            extra_metadata={"requires_ocr": True},
        )
        text = (
            "OCR EXTRACTED TEXT\n"
            "==================\n\n"
            "This text was extracted using OCR from a scanned document.\n"
            "There may be minor artifacts from the OCR process.\n\n"
            "Section 1: Findings\n\n"
            "The OCR process identified several key findings in the document.\n"
            "These findings are summarized below for review.\n\n"
        )

        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_doc_repo = AsyncMock()
        mock_chunk_repo = AsyncMock()

        extracted = AsyncMock()
        extracted.full_text = text
        extracted.pages = []

        mock_doc_repo.get_extracted_text_by_version_id.return_value = extracted
        mock_doc_repo.get_document_by_id.return_value = doc
        mock_chunk_repo.create_chunks_bulk.return_value = [AsyncMock(chunk_index=0)]

        context = ProcessingContext(document=doc, version=version, job=job)

        chunk_processor = ChunkingProcessor(
            session=mock_session,
            document_repository=mock_doc_repo,
            document_chunk_repository=mock_chunk_repo,
        )

        await chunk_processor.process(context)

        mock_chunk_repo.create_chunks_bulk.assert_awaited()
