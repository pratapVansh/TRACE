"""Password hashing and JWT utilities for TRACE authentication."""

from app.core.security.exceptions import InvalidTokenError, TokenError, TokenExpiredError
from app.core.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)
from app.core.security.passwords import hash_password, verify_password
from app.core.security.types import AccessTokenClaims, RefreshTokenClaims

__all__ = [
    "AccessTokenClaims",
    "InvalidTokenError",
    "RefreshTokenClaims",
    "TokenError",
    "TokenExpiredError",
    "create_access_token",
    "create_refresh_token",
    "decode_access_token",
    "decode_refresh_token",
    "hash_password",
    "verify_password",
]
