from collections.abc import Callable
from typing import Any

from fastapi import Depends

from app.api.deps import get_current_user
from app.core.authorization import Permission, PermissionDeniedError, has_permission
from app.schemas.auth import UserMeResponse


def require_permission(permission: Permission) -> Callable[..., Any]:
    """
    FastAPI dependency factory that enforces a permission on top of authentication.

    Usage:
        @router.get("/resource")
        async def get_resource(
            current_user: UserMeResponse = Depends(
                require_permission(PERMISSIONS.SEARCH),
            ),
        ):
            ...
    """

    async def _require_permission(
        current_user: UserMeResponse = Depends(get_current_user),
    ) -> UserMeResponse:
        if not has_permission(current_user.role, permission):
            raise PermissionDeniedError(current_user.role, permission)
        return current_user

    return _require_permission
