from fastapi import APIRouter, Depends

from app.api.authorization import require_permission
from app.api.deps import get_graph_rag_service, get_rag_service, get_retriever_service
from app.core.authorization import PERMISSIONS
from app.core.config import settings
from app.middleware.rate_limit import RateLimiter
from app.schemas.auth import UserMeResponse
from app.schemas.rag import GraphRagQueryRequest, GraphRagResponse, RagQueryRequest, RagQueryResponse
from app.schemas.retrieval import RetrievalRequest, RetrievalResult
from app.services.rag_service import GraphRagService, RagService
from app.services.retriever_service import RetrieverService

router = APIRouter(prefix="/rag", tags=["rag"])

rag_rate_limiter = RateLimiter(
    max_requests=settings.rag_rate_limit_max,
    window_seconds=settings.rag_rate_limit_window_seconds,
)


@router.post("/retrieve", response_model=RetrievalResult)
async def retrieve(
    request: RetrievalRequest,
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    retriever: RetrieverService = Depends(get_retriever_service),
) -> RetrievalResult:
    return await retriever.retrieve(
        query=request.query,
        top_k=request.top_k,
        similarity_threshold=request.similarity_threshold,
        filters=request.filters,
    )


@router.post("/query", response_model=RagQueryResponse)
async def rag_query(
    request: RagQueryRequest,
    _rate_limit: None = Depends(rag_rate_limiter),
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    rag: RagService = Depends(get_rag_service),
) -> RagQueryResponse:
    return await rag.query(
        question=request.question,
        top_k=request.top_k,
        similarity_threshold=request.similarity_threshold,
        filters=request.filters,
    )


@router.post("/graph-query", response_model=GraphRagResponse)
async def graph_rag_query(
    request: GraphRagQueryRequest,
    _rate_limit: None = Depends(rag_rate_limiter),
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    graph_rag: GraphRagService = Depends(get_graph_rag_service),
) -> GraphRagResponse:
    return await graph_rag.query(
        question=request.question,
        top_k=request.top_k,
        similarity_threshold=request.similarity_threshold,
        filters=request.filters,
        vector_top_k=request.vector_top_k,
        graph_top_k=request.graph_top_k,
    )
