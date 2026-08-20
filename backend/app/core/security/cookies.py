"""Refresh-token cookie handling.

The refresh token is the long-lived credential (7 days) and can mint new
access tokens, so it must never be reachable from JavaScript. It is sent
as an ``httpOnly`` cookie scoped to the auth routes; the short-lived
access token is returned in the response body and held in memory by the
client.

CSRF: the cookie is ``SameSite=lax``, so browsers will not attach it to
cross-site POST requests — which is what ``/auth/refresh`` and
``/auth/logout`` are. Deployments that set ``samesite="none"`` (frontend
on a different registrable domain) lose that protection and must add an
explicit CSRF token.
"""

from datetime import timedelta

from fastapi import Response

from app.core.config import settings
from app.core.security.jwt import REFRESH_TOKEN_EXPIRE_DAYS

REFRESH_COOKIE_MAX_AGE = int(timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())


def _cookie_kwargs() -> dict:
    kwargs = {
        "key": settings.refresh_cookie_name,
        "path": settings.refresh_cookie_path,
        "httponly": True,
        "secure": settings.refresh_cookie_secure,
        "samesite": settings.refresh_cookie_samesite,
    }
    if settings.refresh_cookie_domain:
        kwargs["domain"] = settings.refresh_cookie_domain
    return kwargs


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Attach the refresh token to *response* as an httpOnly cookie."""
    response.set_cookie(
        value=refresh_token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        **_cookie_kwargs(),
    )


def clear_refresh_cookie(response: Response) -> None:
    """Expire the refresh cookie (logout, or a rejected refresh attempt)."""
    response.delete_cookie(**_cookie_kwargs())


def read_refresh_cookie(request) -> str | None:
    """Return the refresh token from the request cookies, if present."""
    return request.cookies.get(settings.refresh_cookie_name)
