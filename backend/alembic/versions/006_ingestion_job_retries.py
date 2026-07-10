"""Add retry tracking fields to ingestion jobs for background processing."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_ingestion_job_retries"
down_revision: Union[str, None] = "005_document_extracted_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "retry_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "max_retries",
            sa.Integer(),
            server_default=sa.text("3"),
            nullable=False,
        ),
    )
    op.add_column(
        "ingestion_jobs",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_ingestion_jobs_next_retry_at"),
        "ingestion_jobs",
        ["next_retry_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ingestion_jobs_next_retry_at"), table_name="ingestion_jobs")
    op.drop_column("ingestion_jobs", "next_retry_at")
    op.drop_column("ingestion_jobs", "max_retries")
    op.drop_column("ingestion_jobs", "retry_count")
