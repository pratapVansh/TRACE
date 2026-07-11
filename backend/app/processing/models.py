from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import CreatedAtMixin


class ProcessingJobStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingJobStep(StrEnum):
    QUEUED = "queued"
    LOADING_DOCUMENT = "loading_document"
    SELECTING_PROCESSOR = "selecting_processor"
    PROCESSING = "processing"
    SAVING_RESULTS = "saving_results"
    COMPLETED = "completed"
    FAILED = "failed"


PROCESSING_STEPS = frozenset(step.value for step in ProcessingJobStep)


class ProcessingJob(Base, CreatedAtMixin):
    __tablename__ = "processing_jobs"

    id: Mapped[UUID] = mapped_column(
        PUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    document_id: Mapped[UUID] = mapped_column(
        PUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_version_id: Mapped[UUID] = mapped_column(
        PUUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        default=ProcessingJobStatus.PENDING.value,
    )
    progress: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
    )
    current_step: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=ProcessingJobStep.QUEUED.value,
    )
    retries: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        server_default=text("3"),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )




@dataclass
class ProcessingResult:
    success: bool
    document_id: UUID
    extracted_text: str = ""
    metadata: dict = field(default_factory=dict)
    processing_time: timedelta | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
