"""Document management foundation — documents, document versions, ingestion jobs."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004_document_foundation"
down_revision: Union[str, None] = "003_super_admin_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("doc_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documents_status"), "documents", ["status"], unique=False)
    op.create_index(
        op.f("ix_documents_uploaded_by"),
        "documents",
        ["uploaded_by"],
        unique=False,
    )

    op.create_table(
        "document_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_extension", sa.String(length=16), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column(
            "is_latest",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "version_no",
            name="uq_document_versions_document_id_version_no",
        ),
    )
    op.create_index(
        op.f("ix_document_versions_checksum_sha256"),
        "document_versions",
        ["checksum_sha256"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_versions_document_id"),
        "document_versions",
        ["document_id"],
        unique=False,
    )

    op.create_table(
        "ingestion_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ingestion_jobs_document_id"),
        "ingestion_jobs",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ingestion_jobs_status"),
        "ingestion_jobs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ingestion_jobs_status"), table_name="ingestion_jobs")
    op.drop_index(op.f("ix_ingestion_jobs_document_id"), table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")

    op.drop_index(
        op.f("ix_document_versions_document_id"),
        table_name="document_versions",
    )
    op.drop_index(
        op.f("ix_document_versions_checksum_sha256"),
        table_name="document_versions",
    )
    op.drop_table("document_versions")

    op.drop_index(op.f("ix_documents_uploaded_by"), table_name="documents")
    op.drop_index(op.f("ix_documents_status"), table_name="documents")
    op.drop_table("documents")
