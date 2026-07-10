import os

os.environ.setdefault("PROCESSING_QUEUE_WORKER_ENABLED", "false")

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_document_service
from app.main import app
from app.schemas.auth import UserMeResponse
from app.schemas.pagination import build_pagination_metadata
from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentListItemResponse,
    DocumentListResponse,
    DocumentResponse,
)


@pytest.fixture
def engineer_user() -> UserMeResponse:
    return UserMeResponse(
        id=uuid.uuid4(),
        email="engineer@example.com",
        full_name="Test Engineer",
        role="Engineer",
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_document_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def api_client(engineer_user: UserMeResponse, mock_document_service: AsyncMock):
    app.dependency_overrides[get_current_user] = lambda: engineer_user
    app.dependency_overrides[get_document_service] = lambda: mock_document_service
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_document_response() -> DocumentResponse:
    now = datetime.now(UTC)
    return DocumentResponse(
        id=uuid.uuid4(),
        title="Test Manual",
        original_filename="manual.pdf",
        doc_type="manual",
        status="queued",
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=1024,
        uploaded_by=uuid.uuid4(),
        job_id=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_list_response(sample_document_response: DocumentResponse) -> DocumentListResponse:
    item = DocumentListItemResponse(
        id=sample_document_response.id,
        title=sample_document_response.title,
        original_filename=sample_document_response.original_filename,
        doc_type=sample_document_response.doc_type,
        status=sample_document_response.status,
        mime_type=sample_document_response.mime_type,
        file_extension=sample_document_response.file_extension,
        file_size_bytes=sample_document_response.file_size_bytes,
        version_no=1,
        uploaded_by=sample_document_response.uploaded_by,
        uploaded_by_name="Test Engineer",
        metadata={"department": "Engineering"},
        created_at=sample_document_response.created_at,
        updated_at=sample_document_response.updated_at,
    )
    return DocumentListResponse(
        items=[item],
        **build_pagination_metadata(total=1, skip=0, limit=100),
    )


@pytest.fixture
def sample_detail_response(sample_document_response: DocumentResponse) -> DocumentDetailResponse:
    return DocumentDetailResponse(
        id=sample_document_response.id,
        title=sample_document_response.title,
        original_filename=sample_document_response.original_filename,
        doc_type=sample_document_response.doc_type,
        status=sample_document_response.status,
        mime_type=sample_document_response.mime_type,
        file_extension=sample_document_response.file_extension,
        file_size_bytes=sample_document_response.file_size_bytes,
        version_no=1,
        uploaded_by=sample_document_response.uploaded_by,
        uploaded_by_name="Test Engineer",
        metadata={"department": "Engineering"},
        created_at=sample_document_response.created_at,
        updated_at=sample_document_response.updated_at,
    )
