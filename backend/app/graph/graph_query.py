"""GraphQueryService — read-only queries against the Neo4j knowledge graph.

All Cypher queries are encapsulated here; the route layer never sees raw Cypher.
"""

from app.graph.base import GraphStore, GraphStoreOperationError
from app.schemas.graph import (
    EntityResponse,
    GraphSchemaResponse,
    GraphStatisticsResponse,
    NeighborResponse,
    NeighborsResponse,
    PathResponse,
    PathSegment,
    RelationshipResponse,
    SchemaLabel,
    SchemaRelationshipType,
    TypeCount,
)
from app.core.logging import logger


def _extract_properties(obj: object) -> dict:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "items"):
        return dict(obj.items())
    return {}


def _entity_from_record(record: dict, key: str = "n") -> EntityResponse | None:
    node = record.get(key)
    if node is None:
        return None
    props = _extract_properties(node)
    return EntityResponse(
        id=props.get("id", ""),
        name=props.get("name", ""),
        type=props.get("type", ""),
        aliases=props.get("aliases", []),
        confidence=props.get("confidence", 1.0),
        document_id=props.get("document_id", ""),
        chunk_id=props.get("chunk_id", ""),
        source_document=props.get("source_document", ""),
        created_at=props.get("created_at"),
        updated_at=props.get("updated_at"),
    )


def _rel_from_record(
    record: dict,
    rel_key: str = "r",
    rel_type_key: str = "rel_type",
    source_id_key: str = "source_id",
    target_id_key: str = "target_id",
    props_key: str | None = "rel_props",
) -> RelationshipResponse | None:
    """Extract a RelationshipResponse from a query record.

    Uses explicit source_id / target_id columns from the query (M12) rather
    than relying on relationship properties (which do not store source/target).
    Falls back to relationship properties for backward compatibility.
    """
    if props_key and record.get(props_key):
        props = record[props_key]
    else:
        rel = record.get(rel_key)
        if rel is None:
            return None
        props = _extract_properties(rel)
    rel_type = record.get(rel_type_key, props.get("type", ""))
    return RelationshipResponse(
        id=props.get("id", ""),
        type=rel_type,
        source=record.get(source_id_key, props.get("source", "")),
        target=record.get(target_id_key, props.get("target", "")),
        confidence=props.get("confidence", 1.0),
        document_id=props.get("document_id", ""),
        chunk_id=props.get("chunk_id", ""),
        source_document=props.get("source_document", ""),
        created_at=props.get("created_at"),
        updated_at=props.get("updated_at"),
    )


class GraphQueryService:
    """Read-only graph query operations.

    All methods raise GraphStoreOperationError on database failures.
    """

    def __init__(self, graph_store: GraphStore) -> None:
        self._graph = graph_store

    # ── Graph statistics ────────────────────────────────────

    async def get_statistics(self) -> GraphStatisticsResponse:
        """Return aggregate statistics across the entire graph."""
        counts = await self._graph.execute_read("""
            MATCH (n:Entity)
            OPTIONAL MATCH (n)-[r]->()
            RETURN count(DISTINCT n) AS total_entities,
                   count(DISTINCT n.document_id) AS total_documents,
                   count(r) AS total_relationships
        """)
        row = counts[0] if counts else {}
        total_entities = row.get("total_entities", 0)
        total_documents = row.get("total_documents", 0)
        total_relationships = row.get("total_relationships", 0)

        entity_types = await self._graph.execute_read("""
            MATCH (n:Entity)
            RETURN n.type AS type, count(n) AS count
            ORDER BY count DESC
        """)
        entity_type_counts = [
            TypeCount(type=r["type"], count=r["count"]) for r in entity_types
        ]

        rel_types = await self._graph.execute_read("""
            MATCH (n:Entity)-[r]->()
            RETURN type(r) AS type, count(r) AS count
            ORDER BY count DESC
        """)
        relationship_type_counts = [
            TypeCount(type=r["type"], count=r["count"]) for r in rel_types
        ]

        return GraphStatisticsResponse(
            total_entities=total_entities,
            total_relationships=total_relationships,
            total_documents=total_documents,
            entity_type_counts=entity_type_counts,
            relationship_type_counts=relationship_type_counts,
        )

    # ── Graph schema (labels + relationship types) ──────────

    async def get_schema(self) -> GraphSchemaResponse:
        """Return dynamic graph schema: node labels and relationship types with counts."""
        labels_data = await self._graph.execute_read("""
            MATCH (n)
            UNWIND labels(n) AS label
            RETURN label, count(*) AS count
            ORDER BY count DESC
        """)
        labels = [
            SchemaLabel(label=r["label"], count=r["count"])
            for r in labels_data
        ]

        rel_data = await self._graph.execute_read("""
            MATCH ()-[r]->()
            RETURN type(r) AS type, count(r) AS count
            ORDER BY count DESC
        """)
        relationship_types = [
            SchemaRelationshipType(type=r["type"], count=r["count"])
            for r in rel_data
        ]

        return GraphSchemaResponse(
            labels=labels,
            relationship_types=relationship_types,
        )

    # ── List entities with optional type filter ──────────────

    async def list_entities(
        self,
        skip: int = 0,
        limit: int = 100,
        entity_type: str | None = None,
    ) -> tuple[list[EntityResponse], int]:
        """Return paginated entities and total count in a single round trip (M9)."""
        where_clause = "WHERE n.type = $entity_type" if entity_type else ""
        query = f"""
            MATCH (n:Entity) {where_clause}
            WITH n
            ORDER BY n.name
            SKIP $skip
            LIMIT $limit
            WITH collect(n) AS nodes
            MATCH (all:Entity) {where_clause}
            RETURN nodes, count(*) AS total
        """
        count_query_only = f"MATCH (all:Entity) {where_clause} RETURN count(*) AS total"

        params = {"skip": skip, "limit": limit}
        if entity_type:
            params["entity_type"] = entity_type

        records = await self._graph.execute_read(query, params)
        if records and records[0].get("nodes"):
            items = [_entity_from_record({"n": n}) for n in records[0]["nodes"]]
            total = records[0]["total"]
        else:
            # No results — still need the total count
            total_records = await self._graph.execute_read(count_query_only, params)
            total = total_records[0]["total"] if total_records else 0
            items = []

        return items, total

    # ── Get single entity by id ─────────────────────────────

    async def get_entity(self, entity_id: str) -> EntityResponse | None:
        records = await self._graph.execute_read(
            "MATCH (n:Entity {id: $id}) RETURN n",
            {"id": entity_id},
        )
        if not records:
            return None
        return _entity_from_record(records[0])

    # ── Search entities by name (M32) ───────────────────────

    async def search_entities(
        self,
        query: str,
        skip: int = 0,
        limit: int = 100,
        entity_type: str | None = None,
    ) -> tuple[list[EntityResponse], int]:
        """Search entities by name with case-insensitive matching (M32).

        Uses three match strategies with priority ordering:
        1. Exact match (toLower = toLower)
        2. Word-level match (query word appears as a word boundary)
        3. Substring match (CONTAINS)
        """
        type_filter = "AND n.type = $entity_type" if entity_type else ""
        cypher = f"""
            MATCH (n:Entity)
            WHERE (toLower(n.name) = toLower($query)
               OR toLower(n.name) CONTAINS toLower($query))
              {type_filter}
            WITH n
            ORDER BY
              CASE WHEN toLower(n.name) = toLower($query) THEN 0 ELSE 1 END,
              n.name
            SKIP $skip
            LIMIT $limit
            WITH collect(n) AS nodes
            MATCH (all:Entity)
            WHERE (toLower(all.name) = toLower($query)
               OR toLower(all.name) CONTAINS toLower($query))
              {type_filter}
            RETURN nodes, count(*) AS total
        """
        count_cypher = (
            "MATCH (n:Entity) "
            "WHERE (toLower(n.name) = toLower($query) "
            "   OR toLower(n.name) CONTAINS toLower($query)) "
            f"{type_filter} "
            "RETURN count(n) AS total"
        )

        params = {"query": query, "skip": skip, "limit": limit}
        if entity_type:
            params["entity_type"] = entity_type

        records = await self._graph.execute_read(cypher, params)
        if records and records[0].get("nodes"):
            items = [_entity_from_record({"n": n}) for n in records[0]["nodes"]]
            total = records[0]["total"]
        else:
            total_records = await self._graph.execute_read(count_cypher, params)
            total = total_records[0]["total"] if total_records else 0
            items = []

        return items, total

    # ── Batch neighbor fetch (M31) ─────────────────────────

    async def get_neighbors_for_entities(
        self,
        entity_ids: list[str],
        depth: int = 1,
    ) -> dict[str, list[NeighborResponse]]:
        """Fetch neighbors for multiple entities in a single Cypher query.

        Returns a dict mapping entity_id -> list[NeighborResponse].
        Uses a single round trip instead of N+1 individual queries.
        """
        if not entity_ids:
            return {}

        query = (
            "MATCH (n:Entity) "
            "WHERE n.id IN $entity_ids "
            "OPTIONAL MATCH (n)-[r]-(neighbor:Entity) "
            "WHERE n <> neighbor "
            "RETURN n.id AS entity_id, neighbor, r, type(r) AS rel_type, "
            "  startNode(r).id AS source_id, endNode(r).id AS target_id, "
            "  properties(r) AS rel_props "
            "ORDER BY neighbor.name"
        )
        params: dict = {"entity_ids": entity_ids}

        records = await self._graph.execute_read(query, params)

        result: dict[str, list[NeighborResponse]] = {eid: [] for eid in entity_ids}
        seen: set[str] = set()
        for rec in records:
            eid = rec.get("entity_id", "")
            neighbor_entity = _entity_from_record(rec, "neighbor")
            rel = _rel_from_record(rec)
            if neighbor_entity and rel and eid in result:
                nkey = f"{eid}:{neighbor_entity.id}"
                if nkey not in seen:
                    seen.add(nkey)
                    result[eid].append(NeighborResponse(
                        entity=neighbor_entity,
                        relationship=rel,
                        depth=depth,
                    ))

        return result

    # ── Get neighbors of an entity ──────────────────────────

    async def get_neighbors(
        self,
        entity_id: str,
        depth: int = 1,
        rel_types: list[str] | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[EntityResponse | None, list[NeighborResponse], int]:
        """Get paginated neighbors of an entity (M8, M10, M11)."""
        entity = await self.get_entity(entity_id)
        if entity is None:
            return None, [], 0

        if depth <= 1:
            return await self._neighbors_depth_one(entity, entity_id, rel_types, skip, limit)
        return await self._neighbors_depth_many(entity, entity_id, depth, rel_types, skip, limit)

    async def _neighbors_depth_one(
        self,
        entity: EntityResponse,
        entity_id: str,
        rel_types: list[str] | None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[EntityResponse, list[NeighborResponse], int]:
        """Neighbors at depth 1 — includes incoming and outgoing (M11)."""
        type_filter = (
            "AND type(r) IN $rel_types" if rel_types else ""
        )
        query = (
            "MATCH (n:Entity {id: $id})-[r]-(neighbor:Entity) "
            f"WHERE n <> neighbor {type_filter} "
            "RETURN neighbor, r, type(r) AS rel_type, "
            "  startNode(r).id AS source_id, endNode(r).id AS target_id, "
            "  properties(r) AS rel_props "
            "ORDER BY neighbor.name "
            "SKIP $skip LIMIT $limit"
        )
        count_query = (
            "MATCH (n:Entity {id: $id})-[r]-(neighbor:Entity) "
            f"WHERE n <> neighbor {type_filter} "
            "RETURN count(DISTINCT neighbor) AS total"
        )
        params: dict = {"id": entity_id, "skip": skip, "limit": limit}
        if rel_types:
            params["rel_types"] = rel_types

        records = await self._graph.execute_read(query, params)
        total_records = await self._graph.execute_read(count_query, params)
        total = total_records[0]["total"] if total_records else 0

        neighbors: list[NeighborResponse] = []
        for rec in records:
            neighbor_entity = _entity_from_record(rec, "neighbor")
            rel = _rel_from_record(rec)
            if neighbor_entity and rel:
                neighbors.append(NeighborResponse(
                    entity=neighbor_entity,
                    relationship=rel,
                    depth=1,
                ))

        return entity, neighbors, total

    async def _neighbors_depth_many(
        self,
        entity: EntityResponse,
        entity_id: str,
        depth: int,
        rel_types: list[str] | None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[EntityResponse, list[NeighborResponse], int]:
        """Neighbors at variable depth — results are collected and paginated post-query."""
        safe_depth = min(max(depth, 1), 10)

        all_filter = (
            "ALL(rel IN relationships(path) WHERE type(rel) IN $rel_types)" if rel_types else ""
        )
        where_all = f"AND {all_filter}" if all_filter else ""

        query = (
            f"MATCH path = (n:Entity {{id: $id}})-[*1..{safe_depth}]-(neighbor:Entity) "
            f"WHERE n <> neighbor {where_all} "
            "WITH neighbor, min(length(path)) AS min_depth "
            "RETURN neighbor, min_depth ORDER BY min_depth, neighbor.name"
        )
        params: dict = {"id": entity_id}
        if rel_types:
            params["rel_types"] = rel_types

        records = await self._graph.execute_read(query, params)

        all_neighbors: list[NeighborResponse] = []
        seen_ids: set[str] = set()
        for rec in records:
            neighbor_entity = _entity_from_record(rec, "neighbor")
            min_depth = rec.get("min_depth", 1)
            if neighbor_entity and neighbor_entity.id not in seen_ids:
                seen_ids.add(neighbor_entity.id)
                all_neighbors.append(NeighborResponse(
                    entity=neighbor_entity,
                    relationship=RelationshipResponse(
                        id="",
                        type="*",
                        source=entity_id,
                        target=neighbor_entity.id,
                        confidence=0.0,
                    ),
                    depth=int(min_depth) if isinstance(min_depth, int | float) else 1,
                ))

        total = len(all_neighbors)
        paginated = all_neighbors[skip:skip + limit]

        return entity, paginated, total

    # ── Find shortest path between two entities ────────────

    async def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 6,
    ) -> PathResponse | None:
        safe_depth = min(max(max_depth, 1), 20)

        query = (
            "MATCH path = shortestPath("
            "(src:Entity {id: $source_id})-[*1..$max_depth]-(tgt:Entity {id: $target_id})"
            ") "
            "RETURN "
            "  [node IN nodes(path) | node] AS nodes, "
            "  [rel IN relationships(path) | rel] AS rels, "
            "  [rel IN relationships(path) | type(rel)] AS rel_types, "
            "  [rel IN relationships(path) | properties(rel)] AS rel_props_list, "
            "  length(path) AS length"
        )
        params = {"source_id": source_id, "target_id": target_id, "max_depth": safe_depth}

        records = await self._graph.execute_read(query, params)
        if not records:
            return None

        rec = records[0]
        nodes = rec.get("nodes", [])
        rels_data = rec.get("rels", [])
        rel_types = rec.get("rel_types", [])
        rel_props_list = rec.get("rel_props_list", [])
        path_length = rec.get("length", 0)

        segments: list[PathSegment] = []
        for i in range(len(rels_data)):
            src = _entity_from_record({"n": nodes[i]})
            tgt = _entity_from_record({"n": nodes[i + 1]})
            rel_type = rel_types[i] if i < len(rel_types) else ""
            rel_props = rel_props_list[i] if i < len(rel_props_list) else {}

            src_props = _extract_properties(nodes[i])
            tgt_props = _extract_properties(nodes[i + 1])
            rel_resp = RelationshipResponse(
                id=rel_props.get("id", ""),
                type=rel_type,
                source=src_props.get("id", ""),
                target=tgt_props.get("id", ""),
                confidence=rel_props.get("confidence", 1.0),
                document_id=rel_props.get("document_id", ""),
                chunk_id=rel_props.get("chunk_id", ""),
                source_document=rel_props.get("source_document", ""),
                created_at=rel_props.get("created_at"),
                updated_at=rel_props.get("updated_at"),
            )

            if src and tgt:
                segments.append(PathSegment(source=src, target=tgt, relationship=rel_resp))

        return PathResponse(segments=segments, total_length=path_length if isinstance(path_length, int) else 0)
