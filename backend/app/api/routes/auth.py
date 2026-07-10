from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_auth_service, get_current_user, _extract_ip
from app.core.config import settings
from app.middleware.rate_limit import RateLimiter

auth_rate_limiter = RateLimiter(
    max_requests=settings.auth_rate_limit_max,
    window_seconds=settings.auth_rate_limit_window_seconds,
)
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    UserMeResponse,
)
from app.services.auth_service import AuthService
from app.services.exceptions import (
    DefaultRoleNotFoundError,
    EmailAlreadyRegisteredError,
    ExpiredRefreshTokenError,
    InactiveAccountError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RevokedRefreshTokenError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: Request,
    payload: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
    _rate_limit: None = Depends(auth_rate_limiter),
) -> RegisterResponse:
    try:
        await auth_service.register_user(payload, ip_address=_extract_ip(request))
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc
    except DefaultRoleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration is unavailable",
        ) from exc

    return RegisterResponse()


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
    _rate_limit: None = Depends(auth_rate_limiter),
) -> LoginResponse:
    try:
        return await auth_service.login_user(payload, ip_address=_extract_ip(request))
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from exc
    except InactiveAccountError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        ) from exc


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    request: Request,
    payload: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
    _rate_limit: None = Depends(auth_rate_limiter),
) -> LoginResponse:
    try:
        return await auth_service.refresh_tokens(payload)
    except InvalidRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc
    except ExpiredRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expired refresh token",
        ) from exc


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    current_user: UserMeResponse = Depends(get_current_user),
) -> UserMeResponse:
    return current_user


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    payload: RefreshTokenRequest,
    current_user: UserMeResponse = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> LogoutResponse:
    try:
        await auth_service.logout_user(current_user, payload, ip_address=_extract_ip(request))
    except InvalidRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc
    except RevokedRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Already revoked token",
        ) from exc

    return LogoutResponse()
