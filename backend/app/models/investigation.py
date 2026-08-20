"""Investigation records — persisted outcomes of completed RCA analyses."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class InvestigationRecord(Base, TimestampMixin):
    __tablename__ = "investigations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    conversation_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True,
    )

    problem: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False, default="")
    actions: Mapped[str] = mapped_column(Text, nullable=False, default="")

    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    success: Mapped[bool] = mapped_column(nullable=False, default=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence_evolution: Mapped[list[dict]] = mapped_column(
        JSONB, default=list, nullable=False,
    )

    citations: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    graph_citations: Mapped[list[dict]] = mapped_column(
        JSONB, default=list, nullable=False,
    )
    tools_used: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<InvestigationRecord id={self.id} "
            f"problem={self.problem[:60]}… "
            f"success={self.success} "
            f"confidence={self.confidence:.2f}>"
        )
