"""Add status, metadata to conversations, tool_outputs to messages, and snapshots table.

Revision ID: 016_conversation_persistence
Revises: 015_long_term_memories
Create Date: 2026-07-19 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "016_conversation_persistence"
down_revision: Union[str, None] = "015_long_term_memories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── conversations: add status + metadata_ columns ──────────
    op.add_column(
        "conversations",
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'active'")),
    )
    op.add_column(
        "conversations",
        sa.Column("metadata_", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_conversations_status", "conversations", ["status"])

    # ── messages: add tool_outputs column ──────────────────────
    op.add_column(
        "messages",
        sa.Column("tool_outputs", postgresql.JSONB, nullable=True),
    )

    # ── conversation_snapshots table ───────────────────────────
    op.create_table(
        "conversation_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("turn_index", sa.Integer, nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("working_memory", postgresql.JSONB, nullable=True),
        sa.Column("tool_outputs", postgresql.JSONB, nullable=True),
        sa.Column("agent_results", postgresql.JSONB, nullable=True),
        sa.Column("timeline", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_snapshots_conv_turn",
        "conversation_snapshots",
        ["conversation_id", "turn_index"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("conversation_snapshots")
    op.drop_column("messages", "tool_outputs")
    op.drop_index("ix_conversations_status", table_name="conversations")
    op.drop_column("conversations", "metadata_")
    op.drop_column("conversations", "status")
