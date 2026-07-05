from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.security import InvalidTokenError, TokenExpiredError, decode_access_token
from app.core.storage import create_storage_service
from app.repositories.document_repository import DocumentRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserMeResponse
from app.services.auth_service import AuthService
from app.services.document_service import DocumentService
from app.services.exceptions import InactiveAccountError, UserNotFoundError
from app.services.user_management_service import UserManagementService

bearer_scheme = HTTPBearer(auto_error=False)


async def get_auth_service(
    session: AsyncSession = Depends(get_db),
) -> AuthService:
    return AuthService(
        session=session,
        user_repository=UserRepository(session),
        role_repository=RoleRepository(session),
        refresh_token_repository=RefreshTokenRepository(session),
    )


async def get_user_management_service(
    session: AsyncSession = Depends(get_db),
) -> UserManagementService:
    return UserManagementService(
        session=session,
        user_repository=UserRepository(session),
        role_repository=RoleRepository(session),
        refresh_token_repository=RefreshTokenRepository(session),
    )


async def get_document_service(
    session: AsyncSession = Depends(get_db),
) -> DocumentService:
    return DocumentService(
        session=session,
        document_repository=DocumentRepository(session),
        storage=create_storage_service(),
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserMeResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
        )

    try:
        claims = decode_access_token(credentials.credentials)
    except TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expired token",
        ) from exc
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    try:
        return await auth_service.get_current_user(claims.user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc
    except InactiveAccountError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        ) from exc
