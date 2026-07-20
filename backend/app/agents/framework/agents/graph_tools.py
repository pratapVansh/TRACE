"""Knowledge-graph tools for the KnowledgeGraphAgent.

All tools reuse the existing ``GraphQueryService`` and its schemas;
they never access Neo4j directly.
"""

from typing import Any

from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.base import FrameworkTool
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.schemas import ToolCategory, ToolMetadata


class GraphSearchTool(FrameworkTool):
    """Searches the knowledge graph for entities matching a query."""

    metadata = ToolMetadata(
        tool_id="graph_search",
        name="Graph Search",
        description="Searches the knowledge graph for entities by name. Supports type filters.",
        category=ToolCategory.KNOWLEDGE_GRAPH,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Entity name or keyword to search for"},
                "entity_type": {"type": "string", "description": "Optional type filter (e.g. Pump, Valve)"},
                "limit": {"type": "integer", "description": "Max results (default 20)"},
            },
            "required": ["query"],
        },
    )

    def __init__(self, graph_query_service: Any = None) -> None:
        self._graph_svc = graph_query_service

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        query = params.get("query", "")
        entity_type = params.get("entity_type")
        limit = params.get("limit", 20)

        if not query.strip():
            return ToolResult(data=None, error="Search query cannot be empty.")
        if self._graph_svc is None:
            return ToolResult(data=None, error="Graph query service is not available.")

        try:
            entities, total = await self._graph_svc.search_entities(
                query=query,
                limit=min(limit, 100),
                entity_type=entity_type,
            )
        except Exception as exc:
            return ToolResult(data=None, error=f"Graph search failed: {exc}")

        context.add_reasoning_step(
            f"GraphSearchTool: found {total} entit(ies) for query={query!r}"
        )

        return ToolResult(
            data={
                "entities": [
                    {
                        "id": e.id,
                        "name": e.name,
                        "type": e.type,
                        "confidence": e.confidence,
                        "source_document": e.source_document,
                        "aliases": e.aliases,
                    }
                    for e in entities
                ],
                "total": total,
            },
            metadata={"result_count": total},
        )


class GraphNeighborTool(FrameworkTool):
    """Retrieves neighbors (connected entities) of a knowledge-graph entity."""

    metadata = ToolMetadata(
        tool_id="graph_neighbors",
        name="Graph Neighbors",
        description="Returns entities connected to a given entity, with relationship details.",
        category=ToolCategory.KNOWLEDGE_GRAPH,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "ID of the entity to explore"},
                "depth": {"type": "integer", "description": "Traversal depth (default 1, max 5)"},
                "rel_types": {"type": "string", "description": "Optional comma-separated relationship type filter"},
                "limit": {"type": "integer", "description": "Max neighbors (default 50)"},
            },
            "required": ["entity_id"],
        },
    )

    def __init__(self, graph_query_service: Any = None) -> None:
        self._graph_svc = graph_query_service

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        entity_id = params.get("entity_id", "")
        depth = min(params.get("depth", 1), 5)
        rel_types_raw = params.get("rel_types")
        limit = min(params.get("limit", 50), 200)

        if not entity_id.strip():
            return ToolResult(data=None, error="entity_id is required.")
        if self._graph_svc is None:
            return ToolResult(data=None, error="Graph query service is not available.")

        parsed_rels: list[str] | None = None
        if rel_types_raw:
            parsed_rels = [t.strip().upper() for t in rel_types_raw.split(",") if t.strip()]

        try:
            entity, neighbors, total = await self._graph_svc.get_neighbors(
                entity_id=entity_id,
                depth=depth,
                rel_types=parsed_rels,
                limit=limit,
            )
        except Exception as exc:
            return ToolResult(data=None, error=f"Failed to retrieve neighbors: {exc}")

        if entity is None:
            return ToolResult(data=None, error=f"Entity '{entity_id}' not found.")

        context.add_reasoning_step(
            f"GraphNeighborTool: {total} neighbor(s) of {entity.name} (depth={depth})"
        )

        return ToolResult(
            data={
                "entity": {
                    "id": entity.id,
                    "name": entity.name,
                    "type": entity.type,
                },
                "neighbors": [
                    {
                        "entity": {
                            "id": n.entity.id,
                            "name": n.entity.name,
                            "type": n.entity.type,
                        },
                        "relationship": {
                            "type": n.relationship.type,
                            "source": n.relationship.source,
                            "target": n.relationship.target,
                        },
                        "depth": n.depth,
                    }
                    for n in neighbors
                ],
                "total": total,
            },
            metadata={"neighbor_count": total},
        )


class GraphPathTool(FrameworkTool):
    """Finds the shortest path between two entities in the knowledge graph."""

    metadata = ToolMetadata(
        tool_id="graph_path",
        name="Graph Path",
        description="Finds the shortest connection path between two knowledge-graph entities.",
        category=ToolCategory.KNOWLEDGE_GRAPH,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {
                "source_id": {"type": "string", "description": "ID of the starting entity"},
                "target_id": {"type": "string", "description": "ID of the target entity"},
                "max_depth": {"type": "integer", "description": "Maximum path length (default 6, max 15)"},
            },
            "required": ["source_id", "target_id"],
        },
    )

    def __init__(self, graph_query_service: Any = None) -> None:
        self._graph_svc = graph_query_service

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        source_id = params.get("source_id", "")
        target_id = params.get("target_id", "")
        max_depth = min(params.get("max_depth", 6), 15)

        if not source_id or not target_id:
            return ToolResult(data=None, error="Both source_id and target_id are required.")
        if self._graph_svc is None:
            return ToolResult(data=None, error="Graph query service is not available.")

        try:
            path = await self._graph_svc.find_path(
                source_id=source_id,
                target_id=target_id,
                max_depth=max_depth,
            )
        except Exception as exc:
            return ToolResult(data=None, error=f"Path search failed: {exc}")

        if path is None or not path.segments:
            return ToolResult(
                data={
                    "path_found": False,
                    "message": f"No path found between entities (max_depth={max_depth}).",
                    "segments": [],
                },
            )

        context.add_reasoning_step(
            f"GraphPathTool: found path of length {path.total_length}"
        )

        return ToolResult(
            data={
                "path_found": True,
                "total_length": path.total_length,
                "segments": [
                    {
                        "source": {"id": s.source.id, "name": s.source.name, "type": s.source.type},
                        "target": {"id": s.target.id, "name": s.target.name, "type": s.target.type},
                        "relationship": {
                            "type": s.relationship.type,
                            "source": s.relationship.source,
                            "target": s.relationship.target,
                        },
                    }
                    for s in path.segments
                ],
            },
            metadata={"path_length": path.total_length},
        )


class GraphStatisticsTool(FrameworkTool):
    """Returns aggregate statistics about the knowledge graph."""

    metadata = ToolMetadata(
        tool_id="graph_statistics",
        name="Graph Statistics",
        description="Returns counts of entities, relationships, documents, and type distributions.",
        category=ToolCategory.KNOWLEDGE_GRAPH,
        permissions=set(),
        input_schema={
            "type": "object",
            "properties": {},
        },
    )

    def __init__(self, graph_query_service: Any = None) -> None:
        self._graph_svc = graph_query_service

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        if self._graph_svc is None:
            return ToolResult(data=None, error="Graph query service is not available.")

        try:
            stats = await self._graph_svc.get_statistics()
        except Exception as exc:
            return ToolResult(data=None, error=f"Failed to retrieve graph statistics: {exc}")

        context.add_reasoning_step("GraphStatisticsTool: retrieved graph statistics")

        return ToolResult(
            data={
                "total_entities": stats.total_entities,
                "total_relationships": stats.total_relationships,
                "total_documents": stats.total_documents,
                "entity_types": [
                    {"type": t.type, "count": t.count}
                    for t in stats.entity_type_counts
                ],
                "relationship_types": [
                    {"type": t.type, "count": t.count}
                    for t in stats.relationship_type_counts
                ],
            },
        )
