import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_audit_service, get_current_user
from app.main import app
from app.models.audit_log import AuditLog
from app.schemas.auth import UserMeResponse
from app.services.audit_service import AuditService


def _user(role: str) -> UserMeResponse:
    return UserMeResponse(
        id=uuid.uuid4(),
        email=f"{role.lower()}@example.com",
        full_name=f"Test {role}",
        role=role,
        is_active=True,
        created_at=datetime.now(UTC),
    )


def _log(**overrides) -> AuditLog:
    defaults = {
        "id": uuid.uuid4(),
        "timestamp": datetime.now(UTC),
        "user_id": uuid.uuid4(),
        "username": "engineer@example.com",
        "action": "login",
        "entity_type": "user",
        "entity_id": None,
        "ip_address": "10.0.0.1",
        "status": "success",
        "error_message": None,
    }
    defaults.update(overrides)
    return AuditLog(**defaults)


@pytest.fixture
def mock_audit_repository() -> AsyncMock:
    repository = AsyncMock()
    repository.list_audit_logs.return_value = [_log()]
    repository.count_audit_logs.return_value = 1
    return repository


@pytest.fixture
def audit_client(mock_audit_repository: AsyncMock):
    """Client authenticated as an Engineer, who holds COMPLIANCE."""
    service = AuditService(
        session=AsyncMock(),
        audit_repository=mock_audit_repository,
    )
    app.dependency_overrides[get_current_user] = lambda: _user("Engineer")
    app.dependency_overrides[get_audit_service] = lambda: service
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_list_audit_logs_returns_entries(audit_client: TestClient):
    response = audit_client.get("/api/audit-logs")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["action"] == "login"
    assert body["items"][0]["status"] == "success"
    assert body["items"][0]["ip_address"] == "10.0.0.1"


def test_list_audit_logs_paginates(
    audit_client: TestClient,
    mock_audit_repository: AsyncMock,
):
    mock_audit_repository.count_audit_logs.return_value = 55

    response = audit_client.get("/api/audit-logs", params={"skip": 20, "limit": 20})

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 2
    assert body["page_size"] == 20
    assert body["total_pages"] == 3
    assert body["has_next"] is True
    assert body["has_previous"] is True

    kwargs = mock_audit_repository.list_audit_logs.await_args.kwargs
    assert kwargs["skip"] == 20
    assert kwargs["limit"] == 20


def test_list_audit_logs_rejects_out_of_range_limit(audit_client: TestClient):
    assert audit_client.get("/api/audit-logs", params={"limit": 501}).status_code == 422
    assert audit_client.get("/api/audit-logs", params={"skip": -1}).status_code == 422


def test_list_audit_logs_passes_user_filter(
    audit_client: TestClient,
    mock_audit_repository: AsyncMock,
):
    response = audit_client.get("/api/audit-logs", params={"user": "engineer"})

    assert response.status_code == 200
    assert mock_audit_repository.list_audit_logs.await_args.kwargs["user"] == "engineer"
    assert mock_audit_repository.count_audit_logs.await_args.kwargs["user"] == "engineer"


def test_list_audit_logs_passes_action_and_date_filters(
    audit_client: TestClient,
    mock_audit_repository: AsyncMock,
):
    date_from = datetime.now(UTC) - timedelta(days=7)
    date_to = datetime.now(UTC)

    response = audit_client.get(
        "/api/audit-logs",
        params={
            "action": "failed_login",
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        },
    )

    assert response.status_code == 200
    kwargs = mock_audit_repository.list_audit_logs.await_args.kwargs
    assert kwargs["action"] == "failed_login"
    assert kwargs["date_from"] == date_from
    assert kwargs["date_to"] == date_to


def test_list_audit_logs_omits_unset_filters(
    audit_client: TestClient,
    mock_audit_repository: AsyncMock,
):
    audit_client.get("/api/audit-logs")

    kwargs = mock_audit_repository.list_audit_logs.await_args.kwargs
    assert kwargs["user"] is None
    assert kwargs["action"] is None
    assert kwargs["date_from"] is None
    assert kwargs["date_to"] is None


@pytest.mark.parametrize("role", ["Viewer", "Operator"])
def test_list_audit_logs_forbidden_without_compliance_permission(
    role: str,
    mock_audit_repository: AsyncMock,
):
    """Viewer and Operator lack COMPLIANCE, so the trail must stay closed."""
    service = AuditService(
        session=AsyncMock(),
        audit_repository=mock_audit_repository,
    )
    app.dependency_overrides[get_current_user] = lambda: _user(role)
    app.dependency_overrides[get_audit_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/audit-logs")

    app.dependency_overrides.clear()

    assert response.status_code == 403
    mock_audit_repository.list_audit_logs.assert_not_awaited()


@pytest.mark.parametrize("role", ["Admin", "SuperAdmin", "Engineer"])
def test_list_audit_logs_allowed_for_compliance_roles(
    role: str,
    mock_audit_repository: AsyncMock,
):
    service = AuditService(
        session=AsyncMock(),
        audit_repository=mock_audit_repository,
    )
    app.dependency_overrides[get_current_user] = lambda: _user(role)
    app.dependency_overrides[get_audit_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/audit-logs")

    app.dependency_overrides.clear()

    assert response.status_code == 200
