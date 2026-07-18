import { apiClient } from "./client";

export interface EntityResponse {
  id: string;
  name: string;
  type: string;
  aliases: string[];
  confidence: number;
  document_id: string;
  chunk_id: string;
  source_document: string;
  updated_at: string | null;
}

export interface RelationshipResponse {
  id: string;
  type: string;
  source: string;
  target: string;
  confidence: number;
  document_id: string;
  chunk_id: string;
  source_document: string;
}

export interface NeighborResponse {
  entity: EntityResponse;
  relationship: RelationshipResponse;
  depth: number;
}

export interface NeighborsData {
  entity: EntityResponse;
  neighbors: NeighborResponse[];
  total: number;
}

export interface EntityListData {
  items: EntityResponse[];
  total: number;
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface PathSegment {
  source: EntityResponse;
  target: EntityResponse;
  relationship: RelationshipResponse;
}

export interface PathData {
  segments: PathSegment[];
  total_length: number;
}

export async function fetchEntities(
  skip = 0,
  limit = 100,
  entityType?: string,
): Promise<EntityListData> {
  const params: Record<string, string | number> = { skip, limit };
  if (entityType) params.entity_type = entityType;
  const { data } = await apiClient.get<EntityListData>("/api/graph/entities", {
    params,
  });
  return data;
}

export async function fetchEntity(
  entityId: string,
): Promise<EntityResponse> {
  const { data } = await apiClient.get<EntityResponse>(
    `/api/graph/entity/${entityId}`,
  );
  return data;
}

export async function searchEntities(
  query: string,
  skip = 0,
  limit = 100,
  entityType?: string,
): Promise<EntityListData> {
  const params: Record<string, string | number> = { q: query, skip, limit };
  if (entityType) params.entity_type = entityType;
  const { data } = await apiClient.get<EntityListData>("/api/graph/search", {
    params,
  });
  return data;
}

export async function fetchNeighbors(
  entityId: string,
  depth = 1,
  relTypes?: string[],
): Promise<NeighborsData> {
  const params: Record<string, string | number> = { depth };
  if (relTypes && relTypes.length > 0) {
    params.rel_types = relTypes.join(",");
  }
  const { data } = await apiClient.get<NeighborsData>(
    `/api/graph/neighbors/${entityId}`,
    { params },
  );
  return data;
}

export async function fetchBatchNeighbors(
  entityIds: string[],
  depth = 1,
): Promise<Record<string, NeighborResponse[]>> {
  const { data } = await apiClient.post<{ results: Record<string, NeighborResponse[]> }>(
    "/api/graph/neighbors/batch",
    { entity_ids: entityIds, depth },
  );
  return data.results;
}

export interface TypeCount {
  type: string;
  count: number;
}

export interface GraphStatistics {
  total_entities: number;
  total_relationships: number;
  total_documents: number;
  entity_type_counts: TypeCount[];
  relationship_type_counts: TypeCount[];
}

export async function fetchGraphStatistics(): Promise<GraphStatistics> {
  const { data } = await apiClient.get<GraphStatistics>("/api/graph/statistics");
  return data;
}

export interface SchemaLabel {
  label: string;
  count: number;
  description: string;
}

export interface SchemaRelationshipType {
  type: string;
  count: number;
  description: string;
}

export interface GraphSchema {
  labels: SchemaLabel[];
  relationship_types: SchemaRelationshipType[];
}

export async function fetchGraphSchema(): Promise<GraphSchema> {
  const { data } = await apiClient.get<GraphSchema>("/api/graph/schema");
  return data;
}

export async function findPath(
  source: string,
  target: string,
  maxDepth = 6,
): Promise<PathData> {
  const { data } = await apiClient.get<PathData>("/api/graph/path", {
    params: { source, target, max_depth: maxDepth },
  });
  return data;
}
