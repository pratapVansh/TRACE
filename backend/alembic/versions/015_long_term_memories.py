"""Add memories table for persistent long-term memory storage.

Revision ID: 015_long_term_memories
Revises: 15910303c2ce
Create Date: 2026-07-19 12:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "015_long_term_memories"
down_revision: Union[str, None] = "15910303c2ce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("type", sa.String(50), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=True),

        sa.Column("importance", sa.Float, nullable=False,
                  server_default=sa.text("0.5")),
        sa.Column("confidence", sa.Float, nullable=False,
                  server_default=sa.text("0.5")),

        sa.Column("embedding", postgresql.JSONB, nullable=True),

        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'active'"), index=True),
        sa.Column("source", sa.String(255), nullable=True),

        sa.Column("metadata", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),

        sa.Column("last_accessed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    op.create_index(op.f("ix_memories_user_type"), "memories",
                    ["user_id", "type"], postgresql_using="btree")


def downgrade() -> None:
    op.drop_index(op.f("ix_memories_user_type"), table_name="memories")
    op.drop_table("memories")
