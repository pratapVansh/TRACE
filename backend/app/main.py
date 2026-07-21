from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, HTTPException, Request, status, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.ai.base import LLMConnectionError, LLMConfigurationError
from app.ai.groq_provider import GroqProvider
from app.api.routes import admin_users, agents, auth, chat, chunks, dashboard, demo, documents, graph, health, llm, metrics, observability, processing, rag, search, vector
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

    # Build GraphQueryService singleton from the connected Neo4j store.
    # Stored on app.state so deps.py / per-request DI can reuse it.
    from app.graph.graph_query import GraphQueryService
    from app.services.hybrid_retriever import (
        ContextMerger,
        GraphRetriever,
        HybridRetriever,
        VectorRetriever,
    )

    _graph_svc: GraphQueryService | None = (
        GraphQueryService(graph_store=neo4j_store) if neo4j_store is not None else None
    )
    app.state.graph_query_service = _graph_svc

    # Build HybridRetriever singleton from the connected Qdrant store + graph service.
    # This is the same instance used by GraphRagService (the chat/RAG pipeline).
    _hybrid_retriever = HybridRetriever(
        vector_retriever=VectorRetriever(vector_store=qdrant_store),
        graph_retriever=(
            GraphRetriever(graph_query_service=_graph_svc)
            if _graph_svc is not None else None
        ),
        context_merger=ContextMerger(),
    )
    app.state.hybrid_retriever = _hybrid_retriever

    logger.info(
        "Shared singletons ready — graph_svc=%s, hybrid_retriever=%s",
        "connected" if _graph_svc is not None else "disabled",
        "ready",
    )

    doc_worker_stop_event = asyncio.Event()
    doc_worker_task = None

    if settings.processing_queue_worker_enabled and db_ok:
        doc_worker_task = asyncio.create_task(run_document_processing_worker(doc_worker_stop_event))

    # Initialize agent framework (Milestone 10)
    from app.agents.framework.registry import AgentRegistry as FrameworkAgentRegistry
    
    app.state.framework_agent_registry = FrameworkAgentRegistry()
    logger.info("Agent framework registry initialized")

    # Initialize tool framework (Milestone 10 Prompt 3)
    from app.agents.framework.tools.registry import ToolRegistry as FrameworkToolRegistry
    from app.agents.framework.tools.examples import (
        PingTool,
        CurrentTimeTool,
        SystemInfoTool,
    )

    ft_registry = FrameworkToolRegistry()
    ft_registry.register(PingTool())
    ft_registry.register(CurrentTimeTool())
    ft_registry.register(SystemInfoTool())

    # Register document-analysis tools (Milestone 10 Prompt 4)
    from app.agents.framework.agents.document_tools import (
        DocumentSearchTool,
        DocumentSummaryTool,
        DocumentMetadataTool,
        DocumentComparisonTool,
    )

    ft_registry.register(DocumentSearchTool(hybrid_retriever=_hybrid_retriever))
    ft_registry.register(DocumentSummaryTool(llm_provider=llm_provider))
    ft_registry.register(DocumentMetadataTool(document_service=None))
    ft_registry.register(DocumentComparisonTool(llm_provider=llm_provider))

    app.state.framework_tool_registry = ft_registry
    logger.info("Tool framework initialized with %d tool(s)", len(ft_registry.list_tools()))

    # Register DocumentAnalysisAgent (Milestone 10 Prompt 4)
    from app.agents.framework.agents.document_agent import DocumentAnalysisAgent
    from app.agents.framework.tools.executor import ToolExecutor

    doc_agent = DocumentAnalysisAgent(
        tool_executor=ToolExecutor(registry=ft_registry),
        llm_provider=llm_provider,
    )
    app.state.framework_agent_registry.register(doc_agent)
    logger.info("Registered agent: %s (%s)", doc_agent.agent_id, doc_agent.name)

    # Register knowledge-graph tools (Milestone 10 Prompt 5)
    from app.agents.framework.agents.graph_tools import (
        GraphNeighborTool,
        GraphPathTool,
        GraphSearchTool,
        GraphStatisticsTool,
    )

    graph_svc = _graph_svc
    ft_registry.register(GraphSearchTool(graph_query_service=graph_svc))
    ft_registry.register(GraphNeighborTool(graph_query_service=graph_svc))
    ft_registry.register(GraphPathTool(graph_query_service=graph_svc))
    ft_registry.register(GraphStatisticsTool(graph_query_service=graph_svc))

    # Register KnowledgeGraphAgent (Milestone 10 Prompt 5)
    from app.agents.framework.agents.graph_agent import KnowledgeGraphAgent

    graph_agent = KnowledgeGraphAgent(
        tool_executor=ToolExecutor(registry=ft_registry),
        llm_provider=llm_provider,
    )
    app.state.framework_agent_registry.register(graph_agent)
    logger.info("Registered agent: %s (%s)", graph_agent.agent_id, graph_agent.name)

    # Register maintenance tools (Milestone 10 Prompt 6)
    from app.agents.framework.agents.maintenance_tools import (
        MaintenanceChecklistTool,
        MaintenanceHistoryTool,
        MaintenanceRecommendationTool,
        MaintenanceRiskAssessmentTool,
        MaintenanceSearchTool,
    )

    hybrid = _hybrid_retriever
    ft_registry.register(MaintenanceSearchTool(hybrid_retriever=hybrid, graph_query_service=graph_svc))
    ft_registry.register(MaintenanceRecommendationTool(llm_provider=llm_provider))
    ft_registry.register(MaintenanceHistoryTool(graph_query_service=graph_svc))
    ft_registry.register(MaintenanceChecklistTool(llm_provider=llm_provider, hybrid_retriever=hybrid))
    ft_registry.register(MaintenanceRiskAssessmentTool(llm_provider=llm_provider))

    # Register MaintenanceAgent (Milestone 10 Prompt 6)
    from app.agents.framework.agents.maintenance_agent import MaintenanceAgent

    maint_agent = MaintenanceAgent(
        tool_executor=ToolExecutor(registry=ft_registry),
        llm_provider=llm_provider,
    )
    app.state.framework_agent_registry.register(maint_agent)
    logger.info("Registered agent: %s (%s)", maint_agent.agent_id, maint_agent.name)

    # Register compliance tools (Milestone 10 Prompt 7)
    from app.agents.framework.agents.compliance_tools import (
        ComplianceCheckTool,
        ComplianceGapTool,
        ComplianceRecommendationTool,
        ComplianceSearchTool,
    )

    doc_svc = None  # document_service is not a startup singleton; tools gracefully handle None
    ft_registry.register(ComplianceSearchTool(hybrid_retriever=hybrid, graph_query_service=graph_svc))
    ft_registry.register(ComplianceCheckTool(
        hybrid_retriever=hybrid, graph_query_service=graph_svc, llm_provider=llm_provider,
    ))
    ft_registry.register(ComplianceGapTool(
        graph_query_service=graph_svc, hybrid_retriever=hybrid,
        document_service=doc_svc, llm_provider=llm_provider,
    ))
    ft_registry.register(ComplianceRecommendationTool(llm_provider=llm_provider))

    # Register ComplianceAgent (Milestone 10 Prompt 7)
    from app.agents.framework.agents.compliance_agent import ComplianceAgent

    comp_agent = ComplianceAgent(
        tool_executor=ToolExecutor(registry=ft_registry),
        llm_provider=llm_provider,
    )
    app.state.framework_agent_registry.register(comp_agent)
    logger.info("Registered agent: %s (%s)", comp_agent.agent_id, comp_agent.name)

    # Register asset-intelligence tools (Milestone 10 Prompt 8)
    from app.agents.framework.agents.asset_tools import (
        AssetMaintenanceTool,
        AssetRelationshipTool,
        AssetRiskTool,
        AssetSearchTool,
        AssetSummaryTool,
    )

    ft_registry.register(AssetSearchTool(graph_query_service=graph_svc, hybrid_retriever=hybrid))
    ft_registry.register(AssetRelationshipTool(graph_query_service=graph_svc))
    ft_registry.register(AssetRiskTool(
        graph_query_service=graph_svc, hybrid_retriever=hybrid, llm_provider=llm_provider,
    ))
    ft_registry.register(AssetMaintenanceTool(
        graph_query_service=graph_svc, hybrid_retriever=hybrid, llm_provider=llm_provider,
    ))
    ft_registry.register(AssetSummaryTool(
        graph_query_service=graph_svc, hybrid_retriever=hybrid, llm_provider=llm_provider,
    ))

    # Register AssetIntelligenceAgent (Milestone 10 Prompt 8)
    from app.agents.framework.agents.asset_agent import AssetIntelligenceAgent

    asset_agent = AssetIntelligenceAgent(
        tool_executor=ToolExecutor(registry=ft_registry),
        llm_provider=llm_provider,
    )
    app.state.framework_agent_registry.register(asset_agent)
    logger.info("Registered agent: %s (%s)", asset_agent.agent_id, asset_agent.name)

    # Register RCA tools (Prompt 9)
    from app.agents.framework.agents.rca_tools import (
        EvidenceCollectionTool,
        IncidentSearchTool,
        RootCauseTool,
        SimilarIncidentTool,
    )

    ft_registry.register(IncidentSearchTool(graph_query_service=graph_svc, hybrid_retriever=hybrid))
    ft_registry.register(EvidenceCollectionTool(graph_query_service=graph_svc, hybrid_retriever=hybrid))
    ft_registry.register(RootCauseTool(llm_provider=llm_provider))
    ft_registry.register(SimilarIncidentTool(graph_query_service=graph_svc, hybrid_retriever=hybrid))

    # Register RootCauseAnalysisAgent (Prompt 9)
    from app.agents.framework.agents.rca_agent import RootCauseAnalysisAgent

    rca_agent = RootCauseAnalysisAgent(
        tool_executor=ToolExecutor(registry=ft_registry),
        llm_provider=llm_provider,
    )
    app.state.framework_agent_registry.register(rca_agent)
    logger.info("Registered agent: %s (%s)", rca_agent.agent_id, rca_agent.name)

    # Register Report tools (Prompt 9)
    from app.agents.framework.agents.report_tools import (
        ExecutiveSummaryTool,
        MarkdownReportTool,
        ReportGenerationTool,
    )

    ft_registry.register(ReportGenerationTool(llm_provider=llm_provider))
    ft_registry.register(ExecutiveSummaryTool(llm_provider=llm_provider))
    ft_registry.register(MarkdownReportTool(llm_provider=llm_provider))

    # Register ReportGenerationAgent (Prompt 9)
    from app.agents.framework.agents.report_agent import ReportGenerationAgent

    report_agent = ReportGenerationAgent(
        tool_executor=ToolExecutor(registry=ft_registry),
        llm_provider=llm_provider,
    )
    app.state.framework_agent_registry.register(report_agent)
    logger.info("Registered agent: %s (%s)", report_agent.agent_id, report_agent.name)

    # Register System tools
    from app.agents.framework.agents.system_tools import DashboardTool, ConversationHistoryTool
    ft_registry.register(DashboardTool())
    ft_registry.register(ConversationHistoryTool())

    # Register Workspace tools and agent
    from app.agents.framework.agents.workspace_tools import (
        WorkspaceListTool,
        WorkspaceReadTool,
        WorkspaceWriteTool,
        WorkspaceDeleteTool,
    )
    
    ft_registry.register(WorkspaceListTool())
    ft_registry.register(WorkspaceReadTool())
    ft_registry.register(WorkspaceWriteTool())
    ft_registry.register(WorkspaceDeleteTool())

    # Register Industrial & Data tools
    from app.agents.framework.agents.data_tools import SqlTool, CsvTool, ExcelTool
    ft_registry.register(SqlTool())
    ft_registry.register(CsvTool())
    ft_registry.register(ExcelTool())

    from app.agents.framework.agents.integration_tools import EmailTool, PiHistorianTool, SapTool, RestTool
    ft_registry.register(EmailTool())
    ft_registry.register(PiHistorianTool())
    ft_registry.register(SapTool())
    ft_registry.register(RestTool())

    from app.agents.framework.agents.python_tools import PythonExecutionTool, ChartsTool
    ft_registry.register(PythonExecutionTool())
    ft_registry.register(ChartsTool())

    from app.agents.framework.agents.reporting_tools import ReportsTool, PdfGenerationTool
    ft_registry.register(ReportsTool())
    ft_registry.register(PdfGenerationTool())

    from app.agents.framework.agents.workspace_agent import WorkspaceAgent
    
    workspace_agent = WorkspaceAgent(
        tool_executor=ToolExecutor(registry=ft_registry),
        llm_provider=llm_provider,
    )
    app.state.framework_agent_registry.register(workspace_agent)
    logger.info("Registered agent: %s (%s)", workspace_agent.agent_id, workspace_agent.name)

    # Register ConversationAgent
    from app.agents.framework.agents.conversation_agent import ConversationAgent
    conversation_agent = ConversationAgent(
        tool_executor=ToolExecutor(registry=ft_registry),
        llm_provider=llm_provider,
    )
    app.state.framework_agent_registry.register(conversation_agent)
    logger.info("Registered agent: %s (%s)", conversation_agent.agent_id, conversation_agent.name)

    # Register SearchAgent
    from app.agents.framework.agents.search_agent import SearchAgent
    search_agent = SearchAgent(
        tool_executor=ToolExecutor(registry=ft_registry),
        llm_provider=llm_provider,
    )
    app.state.framework_agent_registry.register(search_agent)
    logger.info("Registered agent: %s (%s)", search_agent.agent_id, search_agent.name)

    yield

    if doc_worker_task is not None:
        doc_worker_stop_event.set()
        try:
            await asyncio.wait_for(doc_worker_task, timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
    if neo4j_store is not None:
        await neo4j_store.close()
    await close_database_connection()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    dependencies = []
    if settings.global_rate_limit_enabled:
        from app.middleware.rate_limit import RateLimiter
        dependencies.append(Depends(RateLimiter(
            max_requests=settings.global_rate_limit_max,
            window_seconds=settings.global_rate_limit_window_seconds,
        )))

    app = FastAPI(
        title=settings.app_name,
        description="Technical Records & Asset Compliance Engine API",
        version="0.1.0",
        lifespan=lifespan,
        dependencies=dependencies,
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
    app.include_router(observability.router, prefix="/api")
    app.include_router(metrics.router, prefix="/api")
    app.include_router(agents.router, prefix="/api")

    return app


app = create_app()
