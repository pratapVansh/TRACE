import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.core.logging import logger, request_id_var


def setup_correlation_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request_id_var.set(request_id)

        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error(
                "Unhandled exception request_id=%s", request_id, exc_info=exc,
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": request_id},
            )

        response.headers["X-Request-ID"] = request_id
        return response
