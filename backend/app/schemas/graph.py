from pydantic import BaseModel

from app.schemas.pagination import PaginatedResponse


class GraphHealthResponse(BaseModel):
    provider: str
    connection_status: str
    database_version: str
    database_name: str
    latency_ms: float


class EntityResponse(BaseModel):
    id: str
    name: str
    type: str
    aliases: list[str] = []
    confidence: float = 1.0
    document_id: str = ""
    chunk_id: str = ""
    source_document: str = ""
    created_at: str | None = None
    updated_at: str | None = None


class RelationshipResponse(BaseModel):
    id: str
    type: str
    source: str
    target: str
    confidence: float = 1.0
    document_id: str = ""
    chunk_id: str = ""
    source_document: str = ""
    created_at: str | None = None
    updated_at: str | None = None


class NeighborResponse(BaseModel):
    entity: EntityResponse
    relationship: RelationshipResponse
    depth: int = 1


class NeighborsResponse(BaseModel):
    entity: EntityResponse
    neighbors: list[NeighborResponse] = []
    total: int = 0


class PathSegment(BaseModel):
    source: EntityResponse
    target: EntityResponse
    relationship: RelationshipResponse


class PathResponse(BaseModel):
    segments: list[PathSegment] = []
    total_length: int = 0


class BatchNeighborsRequest(BaseModel):
    entity_ids: list[str]
    depth: int = 1


class BatchNeighborsResponse(BaseModel):
    results: dict[str, list[NeighborResponse]]


class TypeCount(BaseModel):
    type: str
    count: int


class SchemaLabel(BaseModel):
    label: str
    count: int
    description: str = ""


class SchemaRelationshipType(BaseModel):
    type: str
    count: int
    description: str = ""


class GraphSchemaResponse(BaseModel):
    labels: list[SchemaLabel] = []
    relationship_types: list[SchemaRelationshipType] = []


class GraphStatisticsResponse(BaseModel):
    total_entities: int
    total_relationships: int
    total_documents: int
    entity_type_counts: list[TypeCount] = []
    relationship_type_counts: list[TypeCount] = []


class EntityListResponse(PaginatedResponse[EntityResponse]):
    pass


class GraphSearchResponse(PaginatedResponse[EntityResponse]):
    pass
