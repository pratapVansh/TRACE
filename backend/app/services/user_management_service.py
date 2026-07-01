from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization.user_management_policy import (
    can_assign_role,
    can_manage_user,
)
from app.core.security import hash_password
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
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


class UserManagementService:
    def __init__(
        self,
        session: AsyncSession,
        user_repository: UserRepository,
        role_repository: RoleRepository,
        refresh_token_repository: RefreshTokenRepository,
    ) -> None:
        self._session = session
        self._user_repository = user_repository
        self._role_repository = role_repository
        self._refresh_token_repository = refresh_token_repository

    async def list_users(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> AdminUserListResponse:
        users = await self._user_repository.list_users(skip=skip, limit=limit)
        total = await self._user_repository.count_users()
        return AdminUserListResponse(
            items=[self._to_response(user) for user in users],
            total=total,
        )

    async def create_user(
        self,
        actor: UserMeResponse,
        data: CreateAdminUserRequest,
    ) -> AdminUserResponse:
        if not can_assign_role(actor.role, data.role):
            raise InvalidRoleAssignmentError(
                f"Role '{actor.role}' cannot create users with role '{data.role}'",
            )

        existing_user = await self._user_repository.get_user_by_email(data.email)
        if existing_user is not None:
            raise EmailAlreadyRegisteredError()

        role = await self._role_repository.get_role_by_name(data.role)
        if role is None:
            raise RoleNotFoundError(data.role)

        user = await self._user_repository.create_user(
            full_name=data.full_name,
            email=data.email,
            password_hash=hash_password(data.password),
            role_id=role.id,
        )
        await self._session.commit()

        loaded_user = await self._user_repository.get_user_by_id(user.id)
        if loaded_user is None:
            raise ManagedUserNotFoundError()
        return self._to_response(loaded_user)

    async def update_user_role(
        self,
        actor: UserMeResponse,
        user_id: UUID,
        data: UpdateUserRoleRequest,
    ) -> AdminUserResponse:
        target_user = await self._get_manageable_user(actor, user_id)

        if actor.id == user_id:
            raise SelfModificationForbiddenError("You cannot change your own role")

        if not can_assign_role(actor.role, data.role):
            raise InvalidRoleAssignmentError(
                f"Role '{actor.role}' cannot assign role '{data.role}'",
            )

        role = await self._role_repository.get_role_by_name(data.role)
        if role is None:
            raise RoleNotFoundError(data.role)

        await self._user_repository.update_user_role(target_user.id, role.id)
        await self._session.commit()

        updated_user = await self._user_repository.get_user_by_id(user_id)
        if updated_user is None:
            raise ManagedUserNotFoundError()
        return self._to_response(updated_user)

    async def update_user_status(
        self,
        actor: UserMeResponse,
        user_id: UUID,
        data: UpdateUserStatusRequest,
    ) -> AdminUserResponse:
        target_user = await self._get_manageable_user(actor, user_id)

        if actor.id == user_id and not data.is_active:
            raise SelfModificationForbiddenError("You cannot deactivate your own account")

        await self._user_repository.update_user_is_active(target_user.id, data.is_active)
        if not data.is_active:
            await self._refresh_token_repository.delete_refresh_tokens_for_user(target_user.id)
        await self._session.commit()

        updated_user = await self._user_repository.get_user_by_id(user_id)
        if updated_user is None:
            raise ManagedUserNotFoundError()
        return self._to_response(updated_user)

    async def reset_user_password(
        self,
        actor: UserMeResponse,
        user_id: UUID,
        data: ResetUserPasswordRequest,
    ) -> AdminUserResponse:
        target_user = await self._get_manageable_user(actor, user_id)

        await self._user_repository.update_user_password(
            target_user.id,
            hash_password(data.new_password),
        )
        await self._refresh_token_repository.delete_refresh_tokens_for_user(target_user.id)
        await self._session.commit()

        updated_user = await self._user_repository.get_user_by_id(user_id)
        if updated_user is None:
            raise ManagedUserNotFoundError()
        return self._to_response(updated_user)

    async def _get_manageable_user(self, actor: UserMeResponse, user_id: UUID) -> User:
        target_user = await self._user_repository.get_user_by_id(user_id)
        if target_user is None:
            raise ManagedUserNotFoundError()

        if not can_manage_user(actor.role, target_user.role.name):
            raise ForbiddenUserManagementActionError(
                f"Role '{actor.role}' cannot manage users with role '{target_user.role.name}'",
            )
        return target_user

    @staticmethod
    def _to_response(user: User) -> AdminUserResponse:
        return AdminUserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.name,
            is_active=user.is_active,
            created_at=user.created_at,
        )
