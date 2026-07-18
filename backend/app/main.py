from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.ai.base import LLMConnectionError, LLMConfigurationError
from app.ai.groq_provider import GroqProvider
from app.api.routes import admin_users, auth, chat, chunks, dashboard, demo, documents, graph, health, llm, processing, rag, search, vector
from app.core.authorization import PermissionDeniedError
from app.core.config import settings
from app.core.logging import logger
from app.db.session import close_database_connection, verify_database_connection
from app.middleware.correlation import setup_correlation_middleware
from app.middleware.security_headers import setup_security_headers_middleware
from app.graph.base import GraphStoreConnectionError, GraphStoreConfigurationError
from app.graph.neo4j_graph_store import Neo4jGraphStore
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

    neo4j_store: Neo4jGraphStore | None = None
    if settings.neo4j_uri:
        try:
            store = Neo4jGraphStore()
            await store.connect()
            neo4j_store = store
            logger.info("Neo4j initialized — uri=%s", settings.neo4j_uri)
        except (GraphStoreConnectionError, GraphStoreConfigurationError) as exc:
            logger.warning("Neo4j unavailable at startup: %s", exc)
    else:
        logger.info("Neo4j not configured — skipping graph store initialization")
    app.state.neo4j_store = neo4j_store

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
    if neo4j_store is not None:
        await neo4j_store.close()
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

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            "Validation error %s %s: %s",
            request.method, request.url.path, exc.errors(),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "detail": exc.errors(),
                "request_id": request_id,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            "HTTP %s %s %s: %s",
            exc.status_code, request.method, request.url.path, exc.detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "request_id": request_id,
            },
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.exception(
            "Unhandled exception %s %s: %s",
            request.method, request.url.path, exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "request_id": request_id,
            },
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
    app.include_router(graph.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")

    return app


app = create_app()
