"""Store extracted document text from processing pipeline."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005_document_extracted_text"
down_revision: Union[str, None] = "004_document_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_extracted_text",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_text", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "pages",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("extraction_method", sa.String(length=64), nullable=False),
        sa.Column(
            "requires_ocr",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_version_id",
            name="uq_document_extracted_text_document_version_id",
        ),
    )
    op.create_index(
        op.f("ix_document_extracted_text_document_version_id"),
        "document_extracted_text",
        ["document_version_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_document_extracted_text_document_version_id"),
        table_name="document_extracted_text",
    )
    op.drop_table("document_extracted_text")
