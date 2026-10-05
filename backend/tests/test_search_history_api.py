import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_search_history_repository
from app.main import app
from app.schemas.auth import UserMeResponse


@pytest.fixture
def user() -> UserMeResponse:
    return UserMeResponse(
        id=uuid.uuid4(),
        email="history@example.com",
        full_name="History User",
        role="Viewer",
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def repository() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(user: UserMeResponse, repository: AsyncMock):
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_search_history_repository] = lambda: repository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _row(user_id: uuid.UUID):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        query="pump seal",
        result_count=3,
        filters={"document_type": "manual"},
        searched_at=datetime.now(UTC),
    )


def test_record_history_is_scoped_to_current_user(
    client: TestClient, user: UserMeResponse, repository: AsyncMock
) -> None:
    repository.record.return_value = _row(user.id)

    response = client.post(
        "/api/search/history",
        json={"query": "pump seal", "result_count": 3},
    )

    assert response.status_code == 201
    assert repository.record.await_args.kwargs["user_id"] == user.id


def test_delete_one_uses_current_user_id(
    client: TestClient, user: UserMeResponse, repository: AsyncMock
) -> None:
    history_id = uuid.uuid4()
    repository.delete_one.return_value = True

    response = client.delete(f"/api/search/history/{history_id}")

    assert response.status_code == 204
    repository.delete_one.assert_awaited_once_with(history_id, user.id)


def test_delete_other_users_item_returns_not_found(
    client: TestClient, repository: AsyncMock
) -> None:
    repository.delete_one.return_value = False

    response = client.delete(f"/api/search/history/{uuid.uuid4()}")

    assert response.status_code == 404


def test_clear_all_is_scoped_to_current_user(
    client: TestClient, user: UserMeResponse, repository: AsyncMock
) -> None:
    repository.clear_for_user.return_value = 4

    response = client.delete("/api/search/history")

    assert response.json() == {"deleted": 4}
    repository.clear_for_user.assert_awaited_once_with(user.id)
