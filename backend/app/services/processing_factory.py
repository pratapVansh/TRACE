from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage.base import StorageBackend
from app.repositories.document_repository import DocumentRepository
from app.services.audit_service import AuditService
from app.services.document_processing_service import DocumentProcessingService
from app.services.processors.docx_text_extraction import DocxTextExtractionProcessor
from app.services.processors.image_ocr_extraction import ImageOcrExtractionProcessor
from app.services.processors.language_detection import LanguageDetectionProcessor
from app.services.processors.metadata_extraction import MetadataExtractionProcessor
from app.services.processors.pdf_text_extraction import PdfTextExtractionProcessor
from app.services.processors.scanned_pdf_ocr_extraction import ScannedPdfOcrProcessor
from app.services.processors.pptx_text_extraction import PptxTextExtractionProcessor
from app.services.processors.txt_text_extraction import TxtTextExtractionProcessor
from app.services.processors.xlsx_text_extraction import XlsxTextExtractionProcessor


def create_document_processing_service(
    session: AsyncSession,
    document_repository: DocumentRepository,
    storage: StorageBackend,
    audit_service: AuditService,
) -> DocumentProcessingService:
    """Build a fully wired document processing service."""
    return DocumentProcessingService(
        session=session,
        document_repository=document_repository,
        audit_service=audit_service,
        processors=[
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
        ],
    )
