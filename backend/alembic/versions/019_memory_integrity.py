"""Restore memory and snapshot integrity constraints.

Revision ID: 019_memory_integrity
Revises: 018_drop_orphan_investigations
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "019_memory_integrity"
down_revision: Union[str, None] = "018_drop_orphan_investigations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep the newest row if an affected database accepted duplicate snapshots
    # while the unique index was absent.
    op.execute(
        """
        DELETE FROM conversation_snapshots older
        USING conversation_snapshots newer
        WHERE older.conversation_id = newer.conversation_id
          AND older.turn_index = newer.turn_index
          AND (older.created_at, older.id) < (newer.created_at, newer.id)
        """
    )
    op.create_unique_constraint(
        "uq_conversation_snapshots_conversation_turn",
        "conversation_snapshots",
        ["conversation_id", "turn_index"],
    )
    op.create_index(
        "ix_conversations_status", "conversations", ["status"], unique=False
    )

    op.add_column(
        "memories",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_memories_conversation_id_conversations",
        "memories",
        "conversations",
        ["conversation_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_memories_conversation_id", "memories", ["conversation_id"], unique=False
    )
    op.create_index(
        "ix_memories_expires_at", "memories", ["expires_at"], unique=False
    )
    op.create_index(
        "ix_memories_user_type", "memories", ["user_id", "type"], unique=False
    )

    # Preserve provenance for memories created by the existing consolidation
    # path, but only when the encoded UUID still names a real conversation.
    op.execute(
        """
        UPDATE memories m
        SET conversation_id = c.id
        FROM conversations c
        WHERE m.source = 'conversation:' || c.id::text
        """
    )

    op.drop_constraint("memories_user_id_fkey", "memories", type_="foreignkey")
    op.create_foreign_key(
        "memories_user_id_fkey",
        "memories",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("memories_user_id_fkey", "memories", type_="foreignkey")
    op.create_foreign_key(
        "memories_user_id_fkey", "memories", "users", ["user_id"], ["id"]
    )
    op.drop_index("ix_memories_user_type", table_name="memories")
    op.drop_index("ix_memories_expires_at", table_name="memories")
    op.drop_index("ix_memories_conversation_id", table_name="memories")
    op.drop_constraint(
        "fk_memories_conversation_id_conversations", "memories", type_="foreignkey"
    )
    op.drop_column("memories", "conversation_id")
    op.drop_index("ix_conversations_status", table_name="conversations")
    op.drop_constraint(
        "uq_conversation_snapshots_conversation_turn",
        "conversation_snapshots",
        type_="unique",
    )
