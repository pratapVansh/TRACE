"""Add composite and partial indexes for document listing, job polling, version lookup, and user status queries."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_performance_indexes_ii"
down_revision: Union[str, None] = "009_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Partial index: default document listing always filters deleted_at IS NULL
    # and orders by created_at DESC.  A partial index is smaller and faster than
    # a full-table index on created_at alone.
    op.create_index(
        "ix_documents_active_listing",
        "documents",
        ["created_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Composite index: worker polls ingestion_jobs WHERE status='pending'
    # AND (next_retry_at IS NULL OR next_retry_at <= now()) ORDER BY created_at ASC.
    op.create_index(
        "ix_ingestion_jobs_polling",
        "ingestion_jobs",
        ["status", "next_retry_at", "created_at"],
    )

    # Partial index: version resolution queries often filter is_latest = true.
    op.create_index(
        "ix_document_versions_latest",
        "document_versions",
        ["document_id"],
        postgresql_where=sa.text("is_latest IS TRUE"),
    )

    # B-tree index: login flow checks users.is_active.
    op.create_index(
        op.f("ix_users_is_active"),
        "users",
        ["is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_documents_active_listing", table_name="documents")
    op.drop_index("ix_ingestion_jobs_polling", table_name="ingestion_jobs")
    op.drop_index("ix_document_versions_latest", table_name="document_versions")
    op.drop_index(op.f("ix_users_is_active"), table_name="users")
