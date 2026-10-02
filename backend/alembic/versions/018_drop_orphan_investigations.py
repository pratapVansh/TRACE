"""Drop the unused investigations table.

The RCA/agent source, ORM model, repositories, services, and API routes were
removed before this migration. A repository-wide reference audit and the live
Stage 4 database confirmed the table had no consumers and zero rows.

Revision ID: 018_drop_orphan_investigations
Revises: 017_investigations
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "018_drop_orphan_investigations"
down_revision: Union[str, None] = "017_investigations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("investigations")


def downgrade() -> None:
    op.create_table(
        "investigations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", sa.String(length=50), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("problem", sa.Text(), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("actions", sa.Text(), nullable=False),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("confidence_evolution", postgresql.JSONB(), nullable=False),
        sa.Column("citations", postgresql.JSONB(), nullable=False),
        sa.Column("graph_citations", postgresql.JSONB(), nullable=False),
        sa.Column("tools_used", postgresql.JSONB(), nullable=False),
        sa.Column("embedding", postgresql.JSONB(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_investigations_conversation_id"),
        "investigations",
        ["conversation_id"],
    )
    op.create_index(
        op.f("ix_investigations_user_id"),
        "investigations",
        ["user_id"],
    )
