from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage.base import StorageBackend
from app.graph.base import GraphStore
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.audit_service import AuditService
from app.services.document_processing_service import DocumentProcessingService
from app.services.embedding_service import EmbeddingService
from app.services.processors.chunking_processor import ChunkingProcessor
from app.services.processors.docx_text_extraction import DocxTextExtractionProcessor
from app.services.processors.embedding_processor import EmbeddingProcessor
from app.services.processors.graph_processor import GraphProcessor
from app.services.processors.image_ocr_extraction import ImageOcrExtractionProcessor
from app.services.processors.indexing_processor import IndexingProcessor
from app.services.processors.language_detection import LanguageDetectionProcessor
from app.services.processors.metadata_extraction import MetadataExtractionProcessor
from app.services.processors.pdf_text_extraction import PdfTextExtractionProcessor
from app.services.processors.scanned_pdf_ocr_extraction import ScannedPdfOcrProcessor
from app.services.processors.pptx_text_extraction import PptxTextExtractionProcessor
from app.services.processors.txt_text_extraction import TxtTextExtractionProcessor
from app.services.processors.xlsx_text_extraction import XlsxTextExtractionProcessor
from app.services.qdrant_indexing_service import QdrantIndexingService
from app.services.vector_store import QdrantVectorStore


def create_document_processing_service(
    session: AsyncSession,
    document_repository: DocumentRepository,
    storage: StorageBackend,
    audit_service: AuditService,
    graph_store: GraphStore | None = None,
) -> DocumentProcessingService:
    """Build a fully wired document processing service."""
    chunk_repository = DocumentChunkRepository(session)
    embedding_service = EmbeddingService(
        session=session,
        chunk_repository=chunk_repository,
    )
    vector_store = QdrantVectorStore()
    indexing_service = QdrantIndexingService(vector_store=vector_store)

    processors = [
        PdfTextExtractionProcessor(
            storage=storage,
            document_repository=document_repository,
        ),
        ScannedPdfOcrProcessor(
            storage=storage,
            document_repository=document_repository,
        ),
        DocxTextExtractionProcessor(
            storage=storage,
            document_repository=document_repository,
        ),
        PptxTextExtractionProcessor(
            storage=storage,
            document_repository=document_repository,
        ),
        TxtTextExtractionProcessor(
            storage=storage,
            document_repository=document_repository,
        ),
        XlsxTextExtractionProcessor(
            storage=storage,
            document_repository=document_repository,
        ),
        ImageOcrExtractionProcessor(
            storage=storage,
            document_repository=document_repository,
        ),
        LanguageDetectionProcessor(
            document_repository=document_repository,
        ),
        MetadataExtractionProcessor(
            storage=storage,
            document_repository=document_repository,
        ),
        ChunkingProcessor(
            session=session,
            document_repository=document_repository,
            document_chunk_repository=chunk_repository,
        ),
    ]

    if graph_store is not None:
        processors.append(
            GraphProcessor(
                session=session,
                document_repository=document_repository,
                document_chunk_repository=chunk_repository,
                graph_store=graph_store,
            ),
        )

    processors.extend([
        EmbeddingProcessor(
            session=session,
            document_repository=document_repository,
            chunk_repository=chunk_repository,
            embedding_service=embedding_service,
        ),
        IndexingProcessor(
            session=session,
            document_repository=document_repository,
            chunk_repository=chunk_repository,
            indexing_service=indexing_service,
        ),
    ])

    return DocumentProcessingService(
        session=session,
        document_repository=document_repository,
        audit_service=audit_service,
        processors=processors,
    )
