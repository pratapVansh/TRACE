from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ProcessingJobResponse(BaseModel):
    job_id: UUID
    document_id: UUID
    document_version_id: UUID
    status: str
    progress: int
    current_step: str
    retries: int
    max_retries: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime


class ProcessingJobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    progress: int
    current_step: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class ProcessingRetryResponse(BaseModel):
    job_id: UUID
    status: str
    retries: int
    max_retries: int
    message: str
