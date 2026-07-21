from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import LLMProvider, NullLLMProvider
from app.core.config import settings
from app.core.dependencies import get_db
from app.repositories.conversation_repository import ConversationRepository
from app.services.prompt_builder import PromptBuilder
from app.core.security import InvalidTokenError, TokenExpiredError, decode_access_token
from app.core.storage import create_storage_service
from app.repositories.audit_repository import AuditRepository
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserMeResponse
from app.processing.dependencies import get_processing_queue_service
from app.processing.service import ProcessingQueueService
from app.services.audit_service import AuditService
from app.services.qdrant_indexing_service import QdrantIndexingService
from app.services.chat_service import ChatService
from app.services.rag_service import RagService
from app.services.retriever_service import RetrieverService
from app.graph.base import GraphStore
from app.graph.neo4j_graph_store import Neo4jGraphStore
from app.services.vector_store import QdrantVectorStore, VectorStore
from app.services.auth_service import AuthService
from app.services.chunk_index_service import ChunkIndexService
from app.services.document_processing_queue import DocumentProcessingQueueService
from app.services.ranking_service import RankingService
from app.services.document_processing_service import DocumentProcessingService
from app.services.document_service import DocumentService
from app.services.exceptions import InactiveAccountError, UserNotFoundError
from app.services.processing_factory import create_document_processing_service
from app.services.user_management_service import UserManagementService

bearer_scheme = HTTPBearer(auto_error=False)


async def get_audit_service(
    session: AsyncSession = Depends(get_db),
) -> AuditService:
    return AuditService(
        session=session,
        audit_repository=AuditRepository(session),
    )


async def get_auth_service(
    session: AsyncSession = Depends(get_db),
    audit_service: AuditService = Depends(get_audit_service),
) -> AuthService:
    return AuthService(
        session=session,
        user_repository=UserRepository(session),
        role_repository=RoleRepository(session),
        refresh_token_repository=RefreshTokenRepository(session),
        audit_service=audit_service,
    )


async def get_user_management_service(
    session: AsyncSession = Depends(get_db),
    audit_service: AuditService = Depends(get_audit_service),
) -> UserManagementService:
    return UserManagementService(
        session=session,
        user_repository=UserRepository(session),
        role_repository=RoleRepository(session),
        refresh_token_repository=RefreshTokenRepository(session),
        audit_service=audit_service,
    )


def get_graph_store(request: Request) -> GraphStore:
    store: GraphStore | None = getattr(request.app.state, "neo4j_store", None)
    if store is not None:
        return store
    from fastapi import HTTPException, status
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Neo4j graph store is not configured or unavailable",
    )


def get_graph_store_optional(request: Request) -> GraphStore | None:
    store: GraphStore | None = getattr(request.app.state, "neo4j_store", None)
    if store is not None:
        return store
    return None


async def get_document_processing_service(
    session: AsyncSession = Depends(get_db),
    graph_store: GraphStore | None = Depends(get_graph_store_optional),
) -> DocumentProcessingService:
    repository = DocumentRepository(session)
    storage = create_storage_service()
    audit_service = AuditService(
        session=session,
        audit_repository=AuditRepository(session),
    )
    return create_document_processing_service(
        session, repository, storage, audit_service,
        graph_store=graph_store,
    )


async def get_document_processing_queue(
    session: AsyncSession = Depends(get_db),
    processing_service: DocumentProcessingService = Depends(get_document_processing_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> DocumentProcessingQueueService:
    return DocumentProcessingQueueService(
        session=session,
        processing_service=processing_service,
        document_repository=DocumentRepository(session),
        audit_service=audit_service,
    )


async def get_processing_service(
    session: AsyncSession = Depends(get_db),
) -> ProcessingQueueService:
    from app.processing.repository import ProcessingJobRepository
    from app.processing.queue import ProcessingQueue

    repository = ProcessingJobRepository(session)
    queue = ProcessingQueue(repository)
    return ProcessingQueueService(
        session=session,
        repository=repository,
        queue=queue,
    )


async def get_chunk_repository(
    session: AsyncSession = Depends(get_db),
) -> DocumentChunkRepository:
    return DocumentChunkRepository(session)


async def get_chunk_index_service(
    session: AsyncSession = Depends(get_db),
) -> ChunkIndexService:
    return ChunkIndexService(
        chunk_repository=DocumentChunkRepository(session),
    )


def get_vector_store(request: Request) -> VectorStore:
    store: VectorStore | None = getattr(request.app.state, "qdrant_store", None)
    if store is not None:
        return store
    return QdrantVectorStore()


async def get_document_service(
    session: AsyncSession = Depends(get_db),
    processing_queue: DocumentProcessingQueueService = Depends(get_document_processing_queue),
    audit_service: AuditService = Depends(get_audit_service),
    vector_store: VectorStore = Depends(get_vector_store),
    graph_store: GraphStore | None = Depends(get_graph_store_optional),
) -> DocumentService:
    indexing_service = QdrantIndexingService(vector_store=vector_store)
    return DocumentService(
        session=session,
        document_repository=DocumentRepository(session),
        storage=create_storage_service(),
        audit_service=audit_service,
        processing_queue=processing_queue,
        indexing_service=indexing_service,
        graph_store=graph_store,
    )


def get_graph_query_service(
    store: GraphStore = Depends(get_graph_store),
) -> "GraphQueryService":
    from app.graph.graph_query import GraphQueryService
    return GraphQueryService(graph_store=store)


def get_graph_query_optional(
    store: GraphStore | None = Depends(get_graph_store_optional),
) -> "GraphQueryService | None":
    if store is None:
        return None
    from app.graph.graph_query import GraphQueryService
    return GraphQueryService(graph_store=store)


def get_ranking_service(
    vector_store: VectorStore = Depends(get_vector_store),
) -> RankingService:
    return RankingService(vector_store=vector_store)


def get_retriever_service(
    vector_store: VectorStore = Depends(get_vector_store),
) -> RetrieverService:
    return RetrieverService(vector_store=vector_store)


def get_hybrid_retriever(
    vector_store: VectorStore = Depends(get_vector_store),
    graph_svc: "GraphQueryService | None" = Depends(get_graph_query_optional),
) -> "HybridRetriever":
    from app.services.hybrid_retriever import (
        ContextMerger,
        GraphRetriever,
        HybridRetriever,
        VectorRetriever,
    )
    return HybridRetriever(
        vector_retriever=VectorRetriever(vector_store=vector_store),
        graph_retriever=GraphRetriever(graph_query_service=graph_svc) if graph_svc else None,
        context_merger=ContextMerger(),
    )


def get_llm_provider(request: Request) -> LLMProvider:
    provider: LLMProvider | None = getattr(request.app.state, "llm_provider", None)
    if provider is not None:
        return provider
    return NullLLMProvider()


def get_rag_service(
    retriever: RetrieverService = Depends(get_retriever_service),
    llm: LLMProvider = Depends(get_llm_provider),
) -> RagService:
    return RagService(
        retriever=retriever,
        prompt_builder=PromptBuilder(),
        llm=llm,
    )


def get_graph_rag_service(
    hybrid_retriever: "HybridRetriever" = Depends(get_hybrid_retriever),
    retriever: RetrieverService = Depends(get_retriever_service),
    llm: LLMProvider = Depends(get_llm_provider),
) -> "GraphRagService":
    from app.services.rag_service import GraphRagService
    return GraphRagService(
        hybrid_retriever=hybrid_retriever,
        retriever=retriever,
        prompt_builder=PromptBuilder(),
        llm=llm,
    )


async def get_chat_service(
    graph_rag: "GraphRagService" = Depends(get_graph_rag_service),
    rag: RagService = Depends(get_rag_service),
    session: AsyncSession = Depends(get_db),
    graph_store: GraphStore | None = Depends(get_graph_store_optional),
    llm: LLMProvider = Depends(get_llm_provider),
) -> ChatService:
    from app.services.memory_service import MemoryService
    from app.services.embedding_service import _encode_batch_async
    from app.repositories.memory_repository import MemoryRepository
    from app.services.user_graph_service import UserGraphService

    memory_repo = MemoryRepository(session)
    memory_service = MemoryService(
        repository=memory_repo,
        embed_fn=_encode_batch_async,
        llm=llm if not isinstance(llm, NullLLMProvider) else None,
    )
    user_graph_service = UserGraphService(graph_store=graph_store) if graph_store else None

    return ChatService(
        rag=graph_rag,
        rag_fallback=rag,
        conversation_repository=ConversationRepository(session),
        session=session,
        memory_service=memory_service,
        user_graph_service=user_graph_service,
        llm=llm if not isinstance(llm, NullLLMProvider) else None,
    )


def _extract_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client is not None else None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserMeResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
        )

    try:
        claims = decode_access_token(credentials.credentials)
    except TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expired token",
        ) from exc
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    try:
        return await auth_service.get_current_user(claims.user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc
    except InactiveAccountError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        ) from exc




# ── Agent Framework (Milestone 10) Dependencies ────────────────


def get_framework_agent_registry(request: Request) -> "AgentRegistry":
    """Return the framework AgentRegistry from application state."""
    from app.agents.framework.registry import AgentRegistry
    registry: AgentRegistry | None = getattr(
        request.app.state, "framework_agent_registry", None
    )
    if registry is not None:
        return registry
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Framework agent registry is not configured",
    )


async def get_agent_factory(
    request: Request,
    registry: "AgentRegistry" = Depends(get_framework_agent_registry),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    graph_svc: "GraphQueryService | None" = Depends(get_graph_query_optional),
    session: AsyncSession = Depends(get_db),
) -> "AgentFactory":
    """Create an AgentFactory wired to the current request context."""
    from app.agents.framework.factory import AgentFactory
    return AgentFactory(
        registry=registry,
        llm_provider=llm_provider,
        vector_store=vector_store,
        graph_query_service=graph_svc,
        session=session,
    )


# ── Agent Memory (Milestone 10 Prompt 2) Dependencies ──────────
# NOTE: these must be defined BEFORE get_ai_orchestrator because
# FastAPI evaluates default-argument expressions at definition time.


async def get_conversation_memory(
    session: AsyncSession = Depends(get_db),
) -> "ConversationMemory":
    """Create a ConversationMemory backed by the existing repository."""
    from app.agents.framework.memory.conversation_memory import ConversationMemory
    return ConversationMemory(
        repository=ConversationRepository(session),
    )


def get_working_memory() -> "WorkingMemory":
    """Create a fresh WorkingMemory for a single request cycle."""
    from app.agents.framework.memory.working_memory import WorkingMemory
    return WorkingMemory()


async def get_memory_repository(
    session: AsyncSession = Depends(get_db),
) -> "MemoryRepository":
    from app.repositories.memory_repository import MemoryRepository
    return MemoryRepository(session)


async def get_memory_service(
    repository: "MemoryRepository" = Depends(get_memory_repository),
    llm: LLMProvider = Depends(get_llm_provider),
) -> "MemoryService":
    from app.services.memory_service import MemoryService
    from app.services.embedding_service import _encode_batch_async
    return MemoryService(
        repository=repository,
        embed_fn=_encode_batch_async,
        llm=llm if not isinstance(llm, NullLLMProvider) else None,
    )


async def get_memory_manager(
    conversation_memory: "ConversationMemory" = Depends(get_conversation_memory),
    working_memory: "WorkingMemory" = Depends(get_working_memory),
    memory_service: "MemoryService | None" = Depends(get_memory_service),
) -> "MemoryManager":
    """Create a MemoryManager wired to the current request context."""
    from app.agents.framework.memory.manager import MemoryManager
    return MemoryManager(
        conversation_memory=conversation_memory,
        working_memory=working_memory,
        memory_service=memory_service,
    )


async def get_ai_orchestrator(
    registry: "AgentRegistry" = Depends(get_framework_agent_registry),
    factory: "AgentFactory" = Depends(get_agent_factory),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    memory_manager: "MemoryManager | None" = Depends(get_memory_manager),
) -> "AIOrchestrator":
    """Create the AIOrchestrator wired to the current agent infrastructure.

    Includes full multi-agent support via ``MultiAgentExecutor``.
    """
    from app.agents.framework.orchestrator import AIOrchestrator
    from app.agents.framework.workflow import AgentRouter, MultiAgentExecutor

    multi_executor = MultiAgentExecutor(
        registry=registry,
        factory=factory,
        router=AgentRouter(registry),
        memory_manager=memory_manager,
    )

    return AIOrchestrator(
        registry=registry,
        factory=factory,
        llm_provider=llm_provider,
        memory_manager=memory_manager,
        multi_executor=multi_executor,
    )


# ── Tool Framework (Milestone 10 Prompt 3) Dependencies ────────


def get_framework_tool_registry(request: Request) -> "ToolRegistry":
    """Return the framework ToolRegistry from application state."""
    from app.agents.framework.tools.registry import ToolRegistry
    registry: ToolRegistry | None = getattr(
        request.app.state, "framework_tool_registry", None
    )
    if registry is not None:
        return registry
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Framework tool registry is not configured",
    )


def get_tool_executor(
    registry: "ToolRegistry" = Depends(get_framework_tool_registry),
) -> "ToolExecutor":
    """Create a ToolExecutor wired to the current tool registry."""
    from app.agents.framework.tools.executor import ToolExecutor
    return ToolExecutor(registry=registry)
