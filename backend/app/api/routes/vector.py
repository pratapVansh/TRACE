from fastapi import APIRouter, Depends

from app.api.deps import get_vector_store
from app.schemas.vector import VectorHealthResponse
from app.services.vector_store import VectorStore, VectorStoreConnectionError

router = APIRouter(prefix="/vector", tags=["vector"])


@router.get("/health", response_model=VectorHealthResponse)
async def vector_health(
    vector_store: VectorStore = Depends(get_vector_store),
) -> VectorHealthResponse:
    try:
        return await vector_store.health_check()
    except VectorStoreConnectionError:
        return VectorHealthResponse(
            connected=False,
            collection_exists=False,
            vector_count=0,
            qdrant_version="",
        )
