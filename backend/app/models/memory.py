import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class MemoryModel(Base, TimestampMixin):
    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    importance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)

    embedding: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False, index=True,
    )
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)

    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entities: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    relationships: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    last_accessed: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    user = relationship("User", backref="memories", lazy="joined")
