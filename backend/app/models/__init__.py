"""SQLAlchemy ORM models."""

from app.db.base import Base
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_extracted_text import DocumentExtractedText
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.user import User

# Register ProcessingJob model with Base.metadata for Alembic detection.
from app.processing.models import ProcessingJob  # noqa: F401, E402

__all__ = [
    "AuditLog",
    "Base",
    "Document",
    "DocumentChunk",
    "DocumentExtractedText",
    "DocumentVersion",
    "IngestionJob",
    "ProcessingJob",
    "RefreshToken",
    "Role",
    "User",
]
