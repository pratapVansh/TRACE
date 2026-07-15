from fastapi import APIRouter, Depends

from app.api.authorization import require_permission
from app.api.deps import get_rag_service, get_retriever_service
from app.core.authorization import PERMISSIONS
from app.schemas.auth import UserMeResponse
from app.schemas.rag import RagQueryRequest, RagQueryResponse
from app.schemas.retrieval import RetrievalRequest, RetrievalResult
from app.services.rag_service import RagService
from app.services.retriever_service import RetrieverService

router = APIRouter(prefix="/rag", tags=["rag"])


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
