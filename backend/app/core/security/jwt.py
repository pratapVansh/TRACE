from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import settings
from app.core.security.exceptions import InvalidTokenError, TokenExpiredError
from app.core.security.types import AccessTokenClaims, RefreshTokenClaims

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

# Refresh tokens live longer than access tokens; rotation is enforced at the API layer.
REFRESH_TOKEN_EXPIRE_DAYS = 7


def _normalize_user_id(user_id: UUID | str) -> str:
    return str(user_id)


def _encode_token(
    *,
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    role: str | None = None,
) -> str:
    now = datetime.now(UTC)
    expire = now + expires_delta
    payload: dict[str, str | int] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if role is not None:
        payload["role"] = role

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(user_id: UUID | str, role: str) -> str:
    """Create a short-lived JWT access token for the given user and role."""
    expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    return _encode_token(
        subject=_normalize_user_id(user_id),
        token_type=TOKEN_TYPE_ACCESS,
        expires_delta=expires_delta,
        role=role,
    )


def create_refresh_token(user_id: UUID | str) -> str:
    """Create a long-lived JWT refresh token for the given user."""
    expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return _encode_token(
        subject=_normalize_user_id(user_id),
        token_type=TOKEN_TYPE_REFRESH,
        expires_delta=expires_delta,
    )


def _decode_token(token: str, *, expected_type: str) -> dict[str, str | int]:
    if not token or not token.strip():
        raise InvalidTokenError("Token is missing or empty")

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired") from exc
    except JWTError as exc:
        raise InvalidTokenError("Token is invalid") from exc

    token_type = payload.get("type")
    if token_type != expected_type:
        raise InvalidTokenError(f"Expected {expected_type} token, got {token_type!r}")

    subject = payload.get("sub")
    if not subject or not isinstance(subject, str):
        raise InvalidTokenError("Token subject is missing or invalid")

    return payload


def decode_access_token(token: str) -> AccessTokenClaims:
    """Decode and validate an access token, returning structured claims."""
    payload = _decode_token(token, expected_type=TOKEN_TYPE_ACCESS)

    role = payload.get("role")
    if not role or not isinstance(role, str):
        raise InvalidTokenError("Access token role is missing or invalid")

    return AccessTokenClaims(user_id=payload["sub"], role=role)


def decode_refresh_token(token: str) -> RefreshTokenClaims:
    """Decode and validate a refresh token, returning structured claims."""
    payload = _decode_token(token, expected_type=TOKEN_TYPE_REFRESH)
    return RefreshTokenClaims(user_id=payload["sub"])
