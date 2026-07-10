from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.pagination import PaginatedResponse


class UpdateDocumentRequest(BaseModel):
    title: str | None = Field(default=None, max_length=512)
    doc_type: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, max_length=32)
    source: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=128)
    document_category: str | None = Field(default=None, max_length=64)
    equipment_ids: list[str] | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be empty")
        return stripped

    @field_validator("doc_type")
    @classmethod
    def validate_doc_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip().lower()
        return stripped or None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip().lower()
        return stripped or None

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("department")
    @classmethod
    def validate_department(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class UploadDocumentRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=512)
    content: bytes
    title: str | None = Field(default=None, max_length=512)
    doc_type: str | None = Field(default=None, max_length=64)
    source: str | None = Field(default=None, max_length=255)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("filename must not be empty")
        return stripped

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("doc_type")
    @classmethod
    def validate_doc_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip().lower()
        return stripped or None

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    original_filename: str
    doc_type: str
    status: str
    mime_type: str
    file_extension: str
    file_size_bytes: int
    uploaded_by: UUID | None
    job_id: UUID
    department: str | None = None
    document_category: str | None = None
    equipment_ids: list[str] | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListItemResponse(BaseModel):
    id: UUID
    title: str
    original_filename: str
    doc_type: str
    status: str
    mime_type: str
    file_extension: str
    file_size_bytes: int
    version_no: int
    uploaded_by: UUID | None
    uploaded_by_name: str | None
    metadata: dict
    department: str | None = None
    document_category: str | None = None
    equipment_ids: list[str] | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(PaginatedResponse[DocumentListItemResponse]):
    pass


class DocumentDetailResponse(BaseModel):
    id: UUID
    title: str
    original_filename: str
    doc_type: str
    status: str
    mime_type: str
    file_extension: str
    file_size_bytes: int
    version_no: int
    uploaded_by: UUID | None
    uploaded_by_name: str | None
    metadata: dict
    department: str | None = None
    document_category: str | None = None
    equipment_ids: list[str] | None = None
    created_at: datetime
    updated_at: datetime


class DocumentFileContent(BaseModel):
    document_id: UUID
    filename: str
    mime_type: str
    content: bytes


class DocumentProcessingStatusResponse(BaseModel):
    document_id: UUID
    job_id: UUID
    status: str
    stage: str
    document_status: str
    error: str | None
    retry_count: int
    max_retries: int
    next_retry_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime
