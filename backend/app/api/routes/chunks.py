import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_permission
from app.api.deps import get_chunk_index_service, get_chunk_repository, get_db
from app.core.authorization import PERMISSIONS
from app.schemas.auth import UserMeResponse
from app.schemas.chunks import ChunkIndexStatusResponse, ChunkListResponse, ChunkResponse
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.services.chunk_index_service import ChunkIndexService

router = APIRouter(tags=["chunks"])


def _chunk_to_response(chunk) -> ChunkResponse:
    return ChunkResponse(
        id=chunk.id,
        document_id=chunk.document_id,
        chunk_index=chunk.chunk_index,
        page_number=chunk.page_number,
        section_title=chunk.section_title,
        content=chunk.content,
        metadata=chunk.extra_metadata,
        token_count=chunk.token_count,
        embedding_status=chunk.embedding_status,
        created_at=chunk.created_at,
        updated_at=chunk.updated_at,
    )


def _build_pagination_meta(total: int, skip: int, limit: int) -> dict:
    import math
    page = (skip // limit) + 1
    total_pages = max(1, math.ceil(total / limit)) if limit > 0 else 1
    return {
        "total": total,
        "page": page,
        "page_size": limit,
        "total_items": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


@router.get(
    "/documents/{document_id}/chunks",
    response_model=ChunkListResponse,
)
async def list_document_chunks(
    document_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    embedding_status: str | None = Query(default=None),
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.DOCUMENTS_READ)),
    chunk_repository: DocumentChunkRepository = Depends(get_chunk_repository),
    db: AsyncSession = Depends(get_db),
) -> ChunkListResponse:
    chunks, total = await asyncio.gather(
        chunk_repository.get_chunks_by_document(
            document_id,
            embedding_status=embedding_status,
            skip=skip,
            limit=limit,
        ),
        chunk_repository.count_chunks_by_document(
            document_id,
            embedding_status=embedding_status,
        ),
    )
    return ChunkListResponse(
        items=[_chunk_to_response(c) for c in chunks],
        **_build_pagination_meta(total, skip, limit),
    )


@router.get(
    "/chunks/{chunk_id}",
    response_model=ChunkResponse,
)
async def get_chunk(
    chunk_id: UUID,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.DOCUMENTS_READ)),
    chunk_repository: DocumentChunkRepository = Depends(get_chunk_repository),
) -> ChunkResponse:
    chunk = await chunk_repository.get_chunk_by_id(chunk_id)
    if chunk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chunk not found",
        )
    return _chunk_to_response(chunk)


@router.get(
    "/documents/{document_id}/chunks/status",
    response_model=ChunkIndexStatusResponse,
)
async def get_chunk_index_status(
    document_id: UUID,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.DOCUMENTS_READ)),
    chunk_index_service: ChunkIndexService = Depends(get_chunk_index_service),
) -> ChunkIndexStatusResponse:
    status_data = await chunk_index_service.get_document_index_status(document_id)
    return ChunkIndexStatusResponse(**status_data)
