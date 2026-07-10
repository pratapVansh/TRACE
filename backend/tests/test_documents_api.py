import uuid
from io import BytesIO
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.schemas.documents import DocumentDetailResponse, DocumentListResponse
from app.services.document_exceptions import DocumentProcessingActiveError


def test_list_documents_supports_search_and_pagination(
    api_client: TestClient,
    mock_document_service: AsyncMock,
    sample_list_response: DocumentListResponse,
) -> None:
    mock_document_service.list_documents.return_value = sample_list_response

    response = api_client.get(
        "/api/documents",
        params={"search": "manual", "skip": 20, "limit": 10, "doc_type": "manual"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    mock_document_service.list_documents.assert_awaited_once_with(
        skip=20,
        limit=10,
        search="manual",
        doc_type="manual",
        status=None,
        department=None,
        document_category=None,
        equipment_id=None,
    )


def test_upload_document_accepts_multipart_file(
    api_client: TestClient,
    mock_document_service: AsyncMock,
    sample_document_response,
    engineer_user,
) -> None:
    mock_document_service.upload_document.return_value = sample_document_response

    response = api_client.post(
        "/api/documents",
        files={"file": ("notes.txt", BytesIO(b"hello world"), "text/plain")},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Test Manual"
    mock_document_service.upload_document.assert_awaited_once()


def test_update_document_returns_detail(
    api_client: TestClient,
    mock_document_service: AsyncMock,
    sample_detail_response: DocumentDetailResponse,
) -> None:
    mock_document_service.update_document.return_value = sample_detail_response

    response = api_client.patch(
        f"/api/documents/{sample_detail_response.id}",
        json={"title": "Updated Title", "status": "indexed"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == sample_detail_response.title
    mock_document_service.update_document.assert_awaited_once()


def test_update_document_requires_fields(
    api_client: TestClient,
    mock_document_service: AsyncMock,
) -> None:
    response = api_client.patch(f"/api/documents/{uuid.uuid4()}", json={})

    assert response.status_code == 422
    mock_document_service.update_document.assert_not_called()


def test_delete_document_returns_no_content(
    api_client: TestClient,
    mock_document_service: AsyncMock,
) -> None:
    document_id = uuid.uuid4()
    mock_document_service.delete_document.return_value = None

    response = api_client.delete(f"/api/documents/{document_id}")

    assert response.status_code == 204
    mock_document_service.delete_document.assert_awaited_once()


def test_delete_document_rejects_during_active_processing(
    api_client: TestClient,
    mock_document_service: AsyncMock,
) -> None:
    document_id = uuid.uuid4()
    mock_document_service.delete_document.side_effect = DocumentProcessingActiveError()

    response = api_client.delete(f"/api/documents/{document_id}")

    assert response.status_code == 409
    assert "being processed" in response.json()["detail"]
    mock_document_service.delete_document.assert_awaited_once()
