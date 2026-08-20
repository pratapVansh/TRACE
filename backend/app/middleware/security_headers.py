from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


def _build_connect_src() -> str:
    """Build the CSP ``connect-src`` directive from configured origins.

    Previously hardcoded to ``http://localhost:3000``/``:8000``, which
    silently broke any non-local deployment. Derived from
    ``BACKEND_CORS_ORIGINS`` so it follows the environment.
    """
    origins = [origin for origin in settings.cors_origins if origin and origin != "*"]
    return " ".join(["'self'", *dict.fromkeys(origins)])


def setup_security_headers_middleware(app: FastAPI) -> None:
    connect_src = _build_connect_src()

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), interest-cohort=()"
        )

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            f"connect-src {connect_src}; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "base-uri 'self'"
        )

        if settings.security_headers_hsts_enabled:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )

        return response
