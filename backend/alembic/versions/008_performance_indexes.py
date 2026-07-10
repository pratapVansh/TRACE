"""Add performance indexes for document queries — deleted_at, doc_type, equipment_ids GIN."""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008_performance_indexes"
down_revision: Union[str, None] = "007_business_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_documents_deleted_at"),
        "documents",
        ["deleted_at"],
        unique=False,
        postgresql_where=None,
    )
    op.create_index(
        op.f("ix_documents_doc_type"),
        "documents",
        ["doc_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_documents_equipment_ids_gin"),
        "documents",
        ["equipment_ids"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_documents_equipment_ids_gin"), table_name="documents")
    op.drop_index(op.f("ix_documents_doc_type"), table_name="documents")
    op.drop_index(op.f("ix_documents_deleted_at"), table_name="documents")
