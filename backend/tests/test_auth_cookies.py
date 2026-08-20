"""Tests for httpOnly refresh-token cookie handling.

The refresh token (7-day lifetime, mints access tokens) used to be
returned in the JSON body and stored in ``localStorage`` by the frontend,
so any XSS could steal it. It is now delivered as an httpOnly cookie
scoped to ``/api/auth`` and must never appear in a response body.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_auth_service, get_current_user
from app.core.config import settings
from app.main import app
from app.schemas.auth import LoginResponse, UserMeResponse
from app.services.exceptions import InvalidRefreshTokenError

ACCESS_TOKEN = "access-token-value"
REFRESH_TOKEN = "refresh-token-value"
ROTATED_REFRESH_TOKEN = "rotated-refresh-token-value"
COOKIE = settings.refresh_cookie_name


@pytest.fixture
def auth_user() -> UserMeResponse:
    return UserMeResponse(
        id=uuid.uuid4(),
        email="engineer@example.com",
        full_name="Test Engineer",
        role="Engineer",
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_auth_service() -> AsyncMock:
    service = AsyncMock()
    service.login_user.return_value = LoginResponse(
        access_token=ACCESS_TOKEN, refresh_token=REFRESH_TOKEN
    )
    service.refresh_tokens.return_value = LoginResponse(
        access_token=ACCESS_TOKEN, refresh_token=ROTATED_REFRESH_TOKEN
    )
    service.logout_user.return_value = None
    return service


@pytest.fixture
def client(mock_auth_service: AsyncMock, auth_user: UserMeResponse):
    app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
    app.dependency_overrides[get_current_user] = lambda: auth_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _login(client: TestClient):
    return client.post(
        "/api/auth/login", json={"email": "a@b.com", "password": "password123"}
    )


class TestLogin:
    def test_refresh_token_absent_from_response_body(self, client):
        """The regression: the body must not leak the long-lived token."""
        body = _login(client).json()
        assert body["access_token"] == ACCESS_TOKEN
        assert "refresh_token" not in body
        assert REFRESH_TOKEN not in str(body)

    def test_sets_refresh_cookie(self, client):
        response = _login(client)
        assert response.cookies.get(COOKIE) == REFRESH_TOKEN

    def test_cookie_is_httponly_and_scoped(self, client):
        raw = _login(client).headers["set-cookie"].lower()
        assert "httponly" in raw
        assert f"path={settings.refresh_cookie_path.lower()}" in raw
        assert f"samesite={settings.refresh_cookie_samesite.lower()}" in raw


class TestRefresh:
    def test_uses_cookie_without_request_body(self, client, mock_auth_service):
        client.cookies.set(COOKIE, REFRESH_TOKEN, path=settings.refresh_cookie_path)
        response = client.post("/api/auth/refresh")

        assert response.status_code == 200
        assert response.json()["access_token"] == ACCESS_TOKEN
        forwarded = mock_auth_service.refresh_tokens.call_args.args[0]
        assert forwarded.refresh_token == REFRESH_TOKEN

    def test_rotated_token_written_back_to_cookie(self, client):
        client.cookies.set(COOKIE, REFRESH_TOKEN, path=settings.refresh_cookie_path)
        response = client.post("/api/auth/refresh")

        assert response.cookies.get(COOKIE) == ROTATED_REFRESH_TOKEN
        assert "refresh_token" not in response.json()

    def test_body_still_supported_for_non_browser_clients(
        self, client, mock_auth_service
    ):
        response = client.post(
            "/api/auth/refresh", json={"refresh_token": REFRESH_TOKEN}
        )

        assert response.status_code == 200
        forwarded = mock_auth_service.refresh_tokens.call_args.args[0]
        assert forwarded.refresh_token == REFRESH_TOKEN

    def test_cookie_takes_precedence_over_body(self, client, mock_auth_service):
        client.cookies.set(COOKIE, REFRESH_TOKEN, path=settings.refresh_cookie_path)
        client.post("/api/auth/refresh", json={"refresh_token": "stale-body-token"})

        forwarded = mock_auth_service.refresh_tokens.call_args.args[0]
        assert forwarded.refresh_token == REFRESH_TOKEN

    def test_missing_token_is_unauthorized(self, client):
        response = client.post("/api/auth/refresh")
        assert response.status_code == 401
        assert "Missing refresh token" in response.json()["detail"]

    def test_invalid_token_is_unauthorized(self, client, mock_auth_service):
        mock_auth_service.refresh_tokens.side_effect = InvalidRefreshTokenError()
        client.cookies.set(COOKIE, "bad", path=settings.refresh_cookie_path)

        assert client.post("/api/auth/refresh").status_code == 401


class TestLogout:
    def test_reads_cookie_and_clears_it(self, client, mock_auth_service):
        client.cookies.set(COOKIE, REFRESH_TOKEN, path=settings.refresh_cookie_path)
        response = client.post("/api/auth/logout")

        assert response.status_code == 200
        forwarded = mock_auth_service.logout_user.call_args.args[1]
        assert forwarded.refresh_token == REFRESH_TOKEN
        # Expiring the cookie is what actually logs the browser out.
        assert 'max-age=0' in response.headers["set-cookie"].lower()

    def test_missing_token_is_unauthorized(self, client):
        assert client.post("/api/auth/logout").status_code == 401
