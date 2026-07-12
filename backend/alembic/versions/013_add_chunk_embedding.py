"""Add embedding vector column to document_chunks table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "013_add_chunk_embedding"
down_revision: Union[str, None] = "012_document_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column("embedding", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "embedding")
