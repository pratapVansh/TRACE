"""Regression tests for TRACE's private, administrator-provisioned access model."""

from fastapi.testclient import TestClient

from app.main import app


def test_public_registration_is_not_part_of_the_api() -> None:
    assert "/api/auth/register" not in app.openapi()["paths"]


def test_public_registration_request_returns_not_found() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/register",
            json={
                "email": "outsider@example.com",
                "password": "not-an-invitation",
                "full_name": "Outsider",
            },
        )

    assert response.status_code == 404
