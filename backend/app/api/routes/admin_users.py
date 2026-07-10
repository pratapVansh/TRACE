from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.authorization import require_permission
from app.api.deps import _extract_ip, get_user_management_service
from app.core.authorization import PERMISSIONS
from app.schemas.admin_users import (
    AdminUserListResponse,
    AdminUserResponse,
    CreateAdminUserRequest,
    ResetUserPasswordRequest,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
)
from app.schemas.auth import UserMeResponse
from app.services.exceptions import EmailAlreadyRegisteredError
from app.services.user_management_exceptions import (
    ForbiddenUserManagementActionError,
    InvalidRoleAssignmentError,
    ManagedUserNotFoundError,
    RoleNotFoundError,
    SelfModificationForbiddenError,
)
from app.services.user_management_service import UserManagementService

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("", response_model=AdminUserListResponse)
async def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.USER_MANAGEMENT)),
    user_management_service: UserManagementService = Depends(get_user_management_service),
) -> AdminUserListResponse:
    return await user_management_service.list_users(skip=skip, limit=limit)


@router.post(
    "",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    request: Request,
    payload: CreateAdminUserRequest,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.USER_MANAGEMENT)),
    user_management_service: UserManagementService = Depends(get_user_management_service),
) -> AdminUserResponse:
    try:
        return await user_management_service.create_user(
            current_user, payload, ip_address=_extract_ip(request),
        )
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc
    except RoleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except InvalidRoleAssignmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@router.patch("/{user_id}/role", response_model=AdminUserResponse)
async def update_user_role(
    request: Request,
    user_id: UUID,
    payload: UpdateUserRoleRequest,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.USER_MANAGEMENT)),
    user_management_service: UserManagementService = Depends(get_user_management_service),
) -> AdminUserResponse:
    try:
        return await user_management_service.update_user_role(
            current_user, user_id, payload, ip_address=_extract_ip(request),
        )
    except ManagedUserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc
    except RoleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except SelfModificationForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ForbiddenUserManagementActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except InvalidRoleAssignmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@router.patch("/{user_id}/status", response_model=AdminUserResponse)
async def update_user_status(
    request: Request,
    user_id: UUID,
    payload: UpdateUserStatusRequest,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.USER_MANAGEMENT)),
    user_management_service: UserManagementService = Depends(get_user_management_service),
) -> AdminUserResponse:
    try:
        return await user_management_service.update_user_status(
            current_user, user_id, payload, ip_address=_extract_ip(request),
        )
    except ManagedUserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc
    except SelfModificationForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ForbiddenUserManagementActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@router.patch("/{user_id}/password", response_model=AdminUserResponse)
async def reset_user_password(
    request: Request,
    user_id: UUID,
    payload: ResetUserPasswordRequest,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.USER_MANAGEMENT)),
    user_management_service: UserManagementService = Depends(get_user_management_service),
) -> AdminUserResponse:
    try:
        return await user_management_service.reset_user_password(
            current_user, user_id, payload, ip_address=_extract_ip(request),
        )
    except ManagedUserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc
    except ForbiddenUserManagementActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
