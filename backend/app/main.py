from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.ai.base import LLMConnectionError, LLMConfigurationError
from app.ai.groq_provider import GroqProvider
from app.api.routes import admin_users, auth, chat, chunks, demo, documents, health, llm, processing, rag, search, vector
from app.core.authorization import PermissionDeniedError
from app.core.config import settings
from app.core.logging import logger
from app.db.session import close_database_connection, verify_database_connection
from app.middleware.correlation import setup_correlation_middleware
from app.middleware.security_headers import setup_security_headers_middleware
from app.services.vector_store import QdrantVectorStore, VectorStoreConnectionError
from app.tasks.document_processing_worker import run_document_processing_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s", settings.app_name)
    db_ok = await verify_database_connection()
    if not db_ok:
        logger.warning(
            "Database unavailable at startup — API will run but DB features are disabled"
        )
    app.state.db_connected = db_ok

    qdrant_store = QdrantVectorStore()
    qdrant_ok = False
    if settings.qdrant_url:
        try:
            await qdrant_store.connect()
            await qdrant_store.create_collection()
            await qdrant_store.create_fulltext_index()
            qdrant_ok = True
            logger.info("Qdrant initialized successfully")
        except VectorStoreConnectionError as exc:
            logger.warning("Qdrant unavailable at startup: %s", exc)
    else:
        logger.info("Qdrant not configured — skipping vector store initialization")
    app.state.qdrant_connected = qdrant_ok
    app.state.qdrant_store = qdrant_store

    llm_provider: GroqProvider | None = None
    if settings.llm_provider == "groq" and settings.groq_api_key:
        try:
            provider = GroqProvider()
            await provider.initialize()
            llm_provider = provider
            logger.info("LLM provider initialized (groq, model=%s)", settings.groq_model)
        except (LLMConnectionError, LLMConfigurationError) as exc:
            logger.warning("LLM provider unavailable at startup: %s", exc)
    else:
        logger.info("LLM provider not configured — skipping initialization")
    app.state.llm_provider = llm_provider

    doc_worker_stop_event = asyncio.Event()
    doc_worker_task = None

    if settings.processing_queue_worker_enabled and db_ok:
        doc_worker_task = asyncio.create_task(
            run_document_processing_worker(doc_worker_stop_event)
        )

    yield

    if doc_worker_task is not None:
        doc_worker_stop_event.set()
        await doc_worker_task
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

    setup_correlation_middleware(app)
    setup_security_headers_middleware(app)

    @app.exception_handler(PermissionDeniedError)
    async def permission_denied_handler(
        request: Request,
        exc: PermissionDeniedError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": str(exc), "request_id": request_id},
        )

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(admin_users.router, prefix="/api")
    app.include_router(chunks.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(demo.router, prefix="/api")
    app.include_router(processing.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(vector.router, prefix="/api")
    app.include_router(llm.router, prefix="/api")
    app.include_router(rag.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")

    return app


app = create_app()
