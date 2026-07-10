import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.document_version import DocumentVersion


class DocumentExtractedText(Base, CreatedAtMixin):
    __tablename__ = "document_extracted_text"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id",
            name="uq_document_extracted_text_document_version_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    full_text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    pages: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    requires_ocr: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )

    document_version: Mapped["DocumentVersion"] = relationship(
        "DocumentVersion",
        back_populates="extracted_text",
    )
