"""Security-boundary tests for TRACE's role/permission matrix."""

import uuid
from datetime import UTC, datetime

import pytest

from app.api.authorization import require_permission
from app.core.authorization import (
    ALL_PERMISSIONS,
    PERMISSIONS,
    PermissionDeniedError,
    get_permissions_for_role,
    has_permission,
)
from app.core.authorization.user_management_policy import (
    can_assign_role,
    creatable_roles_for,
)
from app.schemas.auth import UserMeResponse


EXPECTED_ROLE_PERMISSIONS = {
    "Viewer": {
        PERMISSIONS.DASHBOARD,
        PERMISSIONS.DOCUMENTS_READ,
        PERMISSIONS.SEARCH,
    },
    "Operator": {
        PERMISSIONS.DASHBOARD,
        PERMISSIONS.DOCUMENTS_READ,
        PERMISSIONS.SEARCH,
        PERMISSIONS.COPILOT,
        PERMISSIONS.MAINTENANCE,
    },
    "Engineer": {
        PERMISSIONS.DASHBOARD,
        PERMISSIONS.DOCUMENTS_READ,
        PERMISSIONS.DOCUMENTS_UPLOAD,
        PERMISSIONS.SEARCH,
        PERMISSIONS.COPILOT,
        PERMISSIONS.KNOWLEDGE_GRAPH,
        PERMISSIONS.ASSETS_READ,
        PERMISSIONS.ASSETS_WRITE,
        PERMISSIONS.MAINTENANCE,
        PERMISSIONS.COMPLIANCE,
        PERMISSIONS.SOP_LIBRARY,
    },
    "Admin": set(ALL_PERMISSIONS),
    "SuperAdmin": set(ALL_PERMISSIONS),
}


@pytest.mark.parametrize("role, expected", EXPECTED_ROLE_PERMISSIONS.items())
def test_role_permission_matrix_is_explicit_and_stable(role, expected):
    assert set(get_permissions_for_role(role)) == expected


def test_unknown_and_case_mismatched_roles_have_no_permissions():
    assert get_permissions_for_role("Unknown") == frozenset()
    assert get_permissions_for_role("admin") == frozenset()


@pytest.mark.parametrize(
    "role, permission, allowed",
    [
        ("Viewer", PERMISSIONS.SEARCH, True),
        ("Viewer", PERMISSIONS.DOCUMENTS_UPLOAD, False),
        ("Operator", PERMISSIONS.COPILOT, True),
        ("Operator", PERMISSIONS.KNOWLEDGE_GRAPH, False),
        ("Engineer", PERMISSIONS.DOCUMENTS_UPLOAD, True),
        ("Engineer", PERMISSIONS.USER_MANAGEMENT, False),
        ("Admin", PERMISSIONS.USER_MANAGEMENT, True),
        ("SuperAdmin", PERMISSIONS.SYSTEM_SETTINGS, True),
    ],
)
def test_high_value_permission_boundaries(role, permission, allowed):
    assert has_permission(role, permission) is allowed


def test_viewer_remains_a_private_admin_assigned_read_only_role():
    assert can_assign_role("Admin", "Viewer") is True
    assert can_assign_role("SuperAdmin", "Viewer") is True
    assert get_permissions_for_role("Viewer") == frozenset(
        {
            PERMISSIONS.DASHBOARD,
            PERMISSIONS.DOCUMENTS_READ,
            PERMISSIONS.SEARCH,
        }
    )


def test_only_administrative_roles_can_create_users():
    assert creatable_roles_for("Viewer") == frozenset()
    assert creatable_roles_for("Operator") == frozenset()
    assert creatable_roles_for("Engineer") == frozenset()
    assert creatable_roles_for("Admin") == frozenset(
        {"Engineer", "Operator", "Viewer"}
    )
    assert creatable_roles_for("SuperAdmin") == frozenset(
        {"SuperAdmin", "Admin", "Engineer", "Operator", "Viewer"}
    )


def _user(role: str) -> UserMeResponse:
    return UserMeResponse(
        id=uuid.uuid4(),
        email=f"{role.casefold()}@example.com",
        full_name=f"Test {role}",
        role=role,
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_permission_dependency_returns_authorized_user():
    user = _user("Engineer")
    dependency = require_permission(PERMISSIONS.DOCUMENTS_UPLOAD)

    assert await dependency(current_user=user) is user


@pytest.mark.asyncio
async def test_permission_dependency_denies_before_route_handler_runs():
    dependency = require_permission(PERMISSIONS.USER_MANAGEMENT)

    with pytest.raises(PermissionDeniedError, match="Viewer"):
        await dependency(current_user=_user("Viewer"))
