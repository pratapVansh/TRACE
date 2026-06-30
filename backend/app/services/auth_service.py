from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    InvalidTokenError,
    TokenExpiredError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.core.security.jwt import REFRESH_TOKEN_EXPIRE_DAYS
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RegisterRequest,
    UserMeResponse,
)
from app.services.exceptions import (
    DefaultRoleNotFoundError,
    EmailAlreadyRegisteredError,
    ExpiredRefreshTokenError,
    InactiveAccountError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RevokedRefreshTokenError,
    UserNotFoundError,
)

VIEWER_ROLE_NAME = "Viewer"


class AuthService:
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

    async def register_user(self, data: RegisterRequest) -> None:
        existing_user = await self._user_repository.get_user_by_email(data.email)
        if existing_user is not None:
            raise EmailAlreadyRegisteredError()

        viewer_role = await self._role_repository.get_role_by_name(VIEWER_ROLE_NAME)
        if viewer_role is None:
            raise DefaultRoleNotFoundError()

        password_hash = hash_password(data.password)
        await self._user_repository.create_user(
            full_name=data.full_name,
            email=data.email,
            password_hash=password_hash,
            role_id=viewer_role.id,
        )
        await self._session.commit()

    async def login_user(self, data: LoginRequest) -> LoginResponse:
        user = await self._user_repository.get_user_by_email(data.email)
        if user is None or not verify_password(data.password, user.password_hash):
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveAccountError()

        access_token = create_access_token(user.id, user.role.name)
        refresh_token = create_refresh_token(user.id)
        expires_at = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        await self._refresh_token_repository.create_refresh_token(
            user_id=user.id,
            token=refresh_token,
            expires_at=expires_at,
        )
        await self._session.commit()

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def refresh_tokens(self, data: RefreshTokenRequest) -> LoginResponse:
        try:
            claims = decode_refresh_token(data.refresh_token)
        except TokenExpiredError as exc:
            raise ExpiredRefreshTokenError() from exc
        except InvalidTokenError as exc:
            raise InvalidRefreshTokenError() from exc

        stored_token = await self._refresh_token_repository.get_refresh_token(data.refresh_token)
        if stored_token is None:
            raise InvalidRefreshTokenError()

        if stored_token.expires_at <= datetime.now(UTC):
            raise ExpiredRefreshTokenError()

        if str(stored_token.user_id) != claims.user_id:
            raise InvalidRefreshTokenError()

        user = stored_token.user
        if not user.is_active:
            raise InvalidRefreshTokenError()

        access_token = create_access_token(user.id, user.role.name)
        new_refresh_token = create_refresh_token(user.id)
        expires_at = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        await self._refresh_token_repository.delete_refresh_token(stored_token)
        await self._refresh_token_repository.create_refresh_token(
            user_id=user.id,
            token=new_refresh_token,
            expires_at=expires_at,
        )
        await self._session.commit()

        return LoginResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
        )

    async def get_current_user(self, user_id: str) -> UserMeResponse:
        user = await self._user_repository.get_user_by_id(UUID(user_id))
        if user is None:
            raise UserNotFoundError()

        if not user.is_active:
            raise InactiveAccountError()

        return UserMeResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.name,
            is_active=user.is_active,
            created_at=user.created_at,
        )

    async def logout_user(self, current_user: UserMeResponse, data: RefreshTokenRequest) -> None:
        stored_token = await self._refresh_token_repository.get_refresh_token(data.refresh_token)
        if stored_token is None:
            raise RevokedRefreshTokenError()

        if stored_token.user_id != current_user.id:
            raise InvalidRefreshTokenError()

        await self._refresh_token_repository.delete_refresh_token(stored_token)
        await self._session.commit()
