import math

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.authorization import require_permission
from app.api.deps import get_graph_query_service, get_graph_store
from app.core.authorization import PERMISSIONS
from app.graph.base import GraphStore, GraphStoreOperationError
from app.graph.graph_query import GraphQueryService
from app.schemas.auth import UserMeResponse
from app.schemas.graph import (
    BatchNeighborsRequest,
    BatchNeighborsResponse,
    EntityListResponse,
    EntityResponse,
    GraphHealthResponse,
    GraphSchemaResponse,
    GraphSearchResponse,
    GraphStatisticsResponse,
    NeighborsResponse,
    PathResponse,
)
from app.schemas.pagination import build_pagination_metadata

router = APIRouter(prefix="/graph", tags=["graph"])


# ── Health (unauthenticated) ───────────────────────────────────

@router.get("/health", response_model=GraphHealthResponse)
async def graph_health(
    store: GraphStore = Depends(get_graph_store),
) -> GraphHealthResponse:
    status = await store.health_check()
    return GraphHealthResponse(
        provider=status["provider"],
        connection_status=status["connection_status"],
        database_version=status["database_version"],
        database_name=status["database_name"],
        latency_ms=status["latency_ms"],
    )


# ── Graph statistics ─────────────────────────────────────────

@router.get("/statistics", response_model=GraphStatisticsResponse)
async def graph_statistics(
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.KNOWLEDGE_GRAPH)),
    svc: GraphQueryService = Depends(get_graph_query_service),
) -> GraphStatisticsResponse:
    try:
        return await svc.get_statistics()
    except GraphStoreOperationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


# ── Graph schema (labels + relationship types) ────────────────

@router.get("/schema", response_model=GraphSchemaResponse)
async def graph_schema(
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.KNOWLEDGE_GRAPH)),
    svc: GraphQueryService = Depends(get_graph_query_service),
) -> GraphSchemaResponse:
    try:
        return await svc.get_schema()
    except GraphStoreOperationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


# ── List entities (paginated, filterable) ─────────────────────

@router.get("/entities", response_model=EntityListResponse)
async def list_entities(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    entity_type: str | None = Query(default=None, description="Filter by entity type (e.g. Pump, Valve)"),
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.KNOWLEDGE_GRAPH)),
    svc: GraphQueryService = Depends(get_graph_query_service),
) -> EntityListResponse:
    try:
        items, total = await svc.list_entities(
            skip=skip, limit=limit, entity_type=entity_type,
        )
    except GraphStoreOperationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    meta = build_pagination_metadata(total=total, skip=skip, limit=limit)
    return EntityListResponse(items=items, **meta)


# ── Get single entity by id ───────────────────────────────────

@router.get("/entity/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: str,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.KNOWLEDGE_GRAPH)),
    svc: GraphQueryService = Depends(get_graph_query_service),
) -> EntityResponse:
    try:
        entity = await svc.get_entity(entity_id)
    except GraphStoreOperationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    return entity


# ── Search entities by name ────────────────────────────────────

@router.get("/search", response_model=GraphSearchResponse)
async def search_entities(
    q: str = Query(..., min_length=1, description="Search query string"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    entity_type: str | None = Query(default=None, description="Filter by entity type"),
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.KNOWLEDGE_GRAPH)),
    svc: GraphQueryService = Depends(get_graph_query_service),
) -> GraphSearchResponse:
    try:
        items, total = await svc.search_entities(
            query=q, skip=skip, limit=limit, entity_type=entity_type,
        )
    except GraphStoreOperationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    meta = build_pagination_metadata(total=total, skip=skip, limit=limit)
    return GraphSearchResponse(items=items, **meta)


# ── Get neighbors of an entity ────────────────────────────────

@router.get("/neighbors/{entity_id}", response_model=NeighborsResponse)
async def get_neighbors(
    entity_id: str,
    depth: int = Query(default=1, ge=1, le=10, description="Traversal depth"),
    rel_types: str | None = Query(default=None, description="Comma-separated relationship types to filter"),
    skip: int = Query(default=0, ge=0, description="Number of neighbors to skip"),
    limit: int = Query(default=100, ge=1, le=500, description="Maximum neighbors to return"),
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.KNOWLEDGE_GRAPH)),
    svc: GraphQueryService = Depends(get_graph_query_service),
) -> NeighborsResponse:
    parsed_rels: list[str] | None = None
    if rel_types:
        parsed_rels = [t.strip().upper() for t in rel_types.split(",") if t.strip()]

    try:
        entity, neighbors, total = await svc.get_neighbors(
            entity_id=entity_id,
            depth=depth,
            rel_types=parsed_rels,
            skip=skip,
            limit=limit,
        )
    except GraphStoreOperationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    return NeighborsResponse(
        entity=entity,
        neighbors=neighbors,
        total=total,
    )


# ── Batch neighbor fetch (M26) ────────────────────────────────

@router.post("/neighbors/batch", response_model=BatchNeighborsResponse)
async def batch_neighbors(
    request: BatchNeighborsRequest,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.KNOWLEDGE_GRAPH)),
    svc: GraphQueryService = Depends(get_graph_query_service),
) -> BatchNeighborsResponse:
    try:
        results = await svc.get_neighbors_for_entities(
            entity_ids=request.entity_ids,
            depth=request.depth,
        )
    except GraphStoreOperationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return BatchNeighborsResponse(results=results)


# ── Find shortest path between two entities ────────────────────

@router.get("/path", response_model=PathResponse)
async def find_path(
    source: str = Query(..., description="Source entity ID"),
    target: str = Query(..., description="Target entity ID"),
    max_depth: int = Query(default=6, ge=1, le=20, description="Maximum path length"),
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.KNOWLEDGE_GRAPH)),
    svc: GraphQueryService = Depends(get_graph_query_service),
) -> PathResponse:
    try:
        result = await svc.find_path(
            source_id=source,
            target_id=target,
            max_depth=max_depth,
        )
    except GraphStoreOperationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    if result is None or not result.segments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No path found between the specified entities",
        )
    return result
