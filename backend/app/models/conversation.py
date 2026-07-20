import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


_CONV_STATUS_ACTIVE = "active"
_CONV_STATUS_ARCHIVED = "archived"


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=_CONV_STATUS_ACTIVE, server_default=text("'active'"),
    )
    metadata_: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"),
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    user: Mapped["User"] = relationship("User", lazy="joined")


class Message(Base, CreatedAtMixin):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tool_outputs: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )


class ConversationSnapshot(Base, CreatedAtMixin):
    """Persistent snapshot of WorkingMemory state.

    Captured after each agent execution turn so that the full
    execution context (intermediate reasoning, retrieved documents,
    graph facts, entity mentions, tool outputs) survives a page
    refresh.
    """

    __tablename__ = "conversation_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_index: Mapped[int] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)

    working_memory: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tool_outputs: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    agent_results: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    timeline: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    conversation: Mapped["Conversation"] = relationship("Conversation")
