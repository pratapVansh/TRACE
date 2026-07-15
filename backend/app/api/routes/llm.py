from fastapi import APIRouter, Depends

from app.ai.base import LLMProvider
from app.api.deps import get_llm_provider
from app.schemas.llm import LLMHealthResponse

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/health", response_model=LLMHealthResponse)
async def llm_health(
    provider: LLMProvider = Depends(get_llm_provider),
) -> LLMHealthResponse:
    status = await provider.health_check()
    return LLMHealthResponse(
        provider=status["provider"],
        model=status["model"],
        connected=status["connected"],
    )
