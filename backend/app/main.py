from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.core.config import settings
from app.core.logging import logger
from app.db.session import close_database_connection, verify_database_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s", settings.app_name)
    db_ok = await verify_database_connection()
    if not db_ok:
        logger.warning(
            "Database unavailable at startup — API will run but DB features are disabled"
        )
    app.state.db_connected = db_ok
    yield
    await close_database_connection()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Technical Records & Asset Compliance Engine API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")

    return app


app = create_app()
