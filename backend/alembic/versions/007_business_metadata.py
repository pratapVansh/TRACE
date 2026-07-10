"""Add department, document_category, equipment_ids to documents table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "007_business_metadata"
down_revision: Union[str, None] = "006_ingestion_job_retries"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("department", sa.String(128), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("document_category", sa.String(64), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "equipment_ids",
            postgresql.ARRAY(sa.String(64)),
            nullable=True,
        ),
    )
    op.create_index(op.f("ix_documents_department"), "documents", ["department"], unique=False)
    op.create_index(
        op.f("ix_documents_document_category"),
        "documents",
        ["document_category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_documents_document_category"), table_name="documents")
    op.drop_index(op.f("ix_documents_department"), table_name="documents")
    op.drop_column("documents", "equipment_ids")
    op.drop_column("documents", "document_category")
    op.drop_column("documents", "department")
