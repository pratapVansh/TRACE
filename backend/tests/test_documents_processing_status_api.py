import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.schemas.documents import DocumentProcessingStatusResponse


def test_get_processing_status_endpoint(
    api_client: TestClient,
    mock_document_service: AsyncMock,
    engineer_user,
) -> None:
    document_id = uuid.uuid4()
    now = datetime.now(UTC)
    mock_document_service.get_processing_status.return_value = DocumentProcessingStatusResponse(
        document_id=document_id,
        job_id=uuid.uuid4(),
        status="processing",
        stage="text_extraction",
        document_status="processing",
        error=None,
        retry_count=0,
        max_retries=3,
        next_retry_at=None,
        started_at=now,
        finished_at=None,
        updated_at=now,
    )

    response = api_client.get(f"/api/documents/{document_id}/processing-status")

    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    assert response.json()["stage"] == "text_extraction"
    mock_document_service.get_processing_status.assert_awaited_once()
