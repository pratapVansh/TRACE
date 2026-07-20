"""GraphBuilderService — persists extracted entities and relationships to Neo4j.

Uses MERGE for idempotent writes, preserves provenance via COALESCE (H10),
batches writes with UNWIND (M14), enforces timestamps (M7), and validates
graph integrity with correct orphan detection (H11).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.graph.base import GraphStore
from app.extraction.entity import Entity, _entity_id
from app.extraction.relationship import Relationship, RelationshipType
from app.core.logging import logger


# Relationship type to Neo4j label mapping
REL_TYPE_LABEL: dict[RelationshipType, str] = {
    RelationshipType.CONNECTED_TO: "CONNECTED_TO",
    RelationshipType.PART_OF: "PART_OF",
    RelationshipType.LOCATED_IN: "LOCATED_IN",
    RelationshipType.HAS_PROCEDURE: "HAS_PROCEDURE",
    RelationshipType.MAINTAINED_BY: "MAINTAINED_BY",
    RelationshipType.USES: "USES",
    RelationshipType.REFERENCES: "REFERENCES",
    RelationshipType.DEPENDS_ON: "DEPENDS_ON",
    RelationshipType.INPUT_TO: "INPUT_TO",
    RelationshipType.OUTPUT_TO: "OUTPUT_TO",
    RelationshipType.HAS_FAILURE: "HAS_FAILURE",
    RelationshipType.CAUSED_BY: "CAUSED_BY",
    RelationshipType.PERFORMED_BY: "PERFORMED_BY",
    RelationshipType.DESCRIBES: "DESCRIBES",
    RelationshipType.INSPECTS: "INSPECTS",
    RelationshipType.OPERATES: "OPERATES",
    RelationshipType.FAILED_IN: "FAILED_IN",
    RelationshipType.FOLLOWS: "FOLLOWS",
    RelationshipType.RELATED_TO: "RELATED_TO",
    RelationshipType.HAS_COMPONENT: "HAS_COMPONENT",
    RelationshipType.OWNS: "OWNS",
    RelationshipType.WORKS_AT: "WORKS_AT",
    RelationshipType.HAS_ROLE: "HAS_ROLE",
}


@dataclass
class GraphBuildResult:
    """Outcome of a graph build operation."""

    nodes_merged: int = 0
    relationships_merged: int = 0
    successful: bool = True
    error: str | None = None


@dataclass
class GraphIntegrityReport:
    """Report on graph integrity for a given document."""

    total_entity_nodes: int = 0
    total_relationship_edges: int = 0
    orphan_relationships: int = 0
    dangling_document_refs: int = 0

    @property
    def consistent(self) -> bool:
        return self.orphan_relationships == 0 and self.dangling_document_refs == 0


class GraphBuilderService:
    """Persists extracted entities and relationships into a graph database.

    All writes use MERGE for idempotent writes, batch with UNWIND (M14),
    preserve provenance via COALESCE (H10), and include created_at/updated_at
    timestamps (M7).  A single transaction ensures atomicity.
    """

    def __init__(self, graph_store: GraphStore) -> None:
        self._graph = graph_store
        self._label = "Entity"

    # ── Public API ──────────────────────────────────────────

    async def process_document(
        self,
        document_id: str,
        entities: list[Entity],
        relationships: list[Relationship],
        source_document: str = "",
    ) -> GraphBuildResult:
        """Persist all entities and relationships for a document in one atomic transaction.

        Uses UNWIND batching (M14), preserves provenance (H10), and sets
        created_at / updated_at timestamps (M7).
        """
        if not entities and not relationships:
            return GraphBuildResult(successful=True)

        now = _now()
        nodes_batched = len(entities)
        rels_batched = 0

        try:
            tx = await self._graph.begin_transaction()
        except Exception as exc:
            logger.exception("Graph build failed — doc=%s: %s", document_id, exc)
            return GraphBuildResult(successful=False, error=str(exc))

        try:
            if entities:
                query, params = _merge_nodes_batch(entities, document_id, source_document, now)
                result = await tx.run(query, params)
                await result.consume()

            rels_by_type: dict[str, list[Relationship]] = defaultdict(list)
            for rel in relationships:
                label = REL_TYPE_LABEL.get(rel.type)
                if label is not None:
                    rels_by_type[label].append(rel)
                else:
                    logger.warning("Unknown relationship type: %s", rel.type)

            for label, rels in rels_by_type.items():
                query, params = _merge_rels_batch(label, rels, document_id, source_document, now)
                result = await tx.run(query, params)
                await result.consume()
                rels_batched += len(rels)

        except Exception as exc:
            await tx.rollback()
            logger.exception("Graph build failed — doc=%s: %s", document_id, exc)
            return GraphBuildResult(successful=False, error=str(exc))

        else:
            await tx.commit()
        logger.info(
            "Graph build complete — doc=%s nodes=%d rels=%d",
            document_id, nodes_batched, rels_batched,
        )
        return GraphBuildResult(
            nodes_merged=nodes_batched,
            relationships_merged=rels_batched,
            successful=True,
        )

    async def process_chunk(
        self,
        document_id: str,
        chunk_id: str,
        entities: list[Entity],
        relationships: list[Relationship],
        source_document: str = "",
    ) -> GraphBuildResult:
        """Persist entities and relationships scoped to a single chunk."""
        scoped_entities = [
            Entity(
                name=e.name,
                type=e.type,
                aliases=e.aliases,
                confidence=e.confidence,
                chunk_id=chunk_id,
                document_id=document_id,
                metadata=e.metadata,
            )
            for e in entities
        ]
        scoped_rels = [
            Relationship(
                source=r.source,
                target=r.target,
                type=r.type,
                confidence=r.confidence,
                chunk_id=chunk_id,
                document_id=document_id,
                metadata=r.metadata,
            )
            for r in relationships
        ]
        return await self.process_document(
            document_id=document_id,
            entities=scoped_entities,
            relationships=scoped_rels,
            source_document=source_document,
        )

    async def delete_document(self, document_id: str) -> int:
        """Delete all nodes and relationships associated with a document.

        Uses DETACH DELETE to remove nodes and all their relationships.
        Returns the number of nodes deleted.
        """
        result = await self._graph.execute_write(
            "MATCH (n:Entity) WHERE n.document_id = $document_id "
            "WITH n, n.id AS node_id "
            "DETACH DELETE n "
            "RETURN count(node_id) AS deleted",
            {"document_id": document_id},
        )
        return result[0]["deleted"] if result else 0

    async def validate_graph_integrity(
        self,
        document_id: str,
    ) -> GraphIntegrityReport:
        """Check graph integrity for a document's subgraph.

        Validates that:
          - All expected nodes exist
          - Relationships reference valid endpoint nodes
          - No cross-document dangling references (H11)
        """
        node_count = await self._graph.execute_read(
            "MATCH (n:Entity) WHERE n.document_id = $document_id "
            "RETURN count(n) AS total",
            {"document_id": document_id},
        )
        total_nodes = node_count[0]["total"] if node_count else 0

        rel_count = await self._graph.execute_read(
            "MATCH (src:Entity)-[r]->(tgt:Entity) "
            "WHERE r.document_id = $document_id "
            "RETURN count(r) AS total",
            {"document_id": document_id},
        )
        total_rels = rel_count[0]["total"] if rel_count else 0

        # H11: detect orphan relationships where source OR target belongs to a different document
        cross_doc_count = await self._graph.execute_read(
            "MATCH (src:Entity)-[r]->(tgt:Entity) "
            "WHERE r.document_id = $document_id "
            "AND (src.document_id <> $document_id "
            "     OR tgt.document_id <> $document_id) "
            "RETURN count(r) AS total",
            {"document_id": document_id},
        )
        orphan_rels = cross_doc_count[0]["total"] if cross_doc_count else 0

        return GraphIntegrityReport(
            total_entity_nodes=total_nodes,
            total_relationship_edges=total_rels,
            orphan_relationships=orphan_rels,
        )


# ── Module-level helpers ─────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _merge_nodes_batch(
    entities: list[Entity],
    document_id: str,
    source_document: str,
    now: str,
) -> tuple[str, list[dict]]:
    """Generate a single UNWIND MERGE query for all entity nodes (M14)."""
    query = """
    UNWIND $entities AS e
    MERGE (n:Entity {id: e.id})
    SET n.name = e.name,
        n.type = e.type,
        n.confidence = e.confidence,
        n.aliases = e.aliases,
        n.document_id = e.document_id,
        n.chunk_id = e.chunk_id,
        n.source_document = COALESCE(n.source_document, e.source_document),
        n.updated_at = e.updated_at,
        n.created_at = COALESCE(n.created_at, e.created_at)
    """
    params = {
        "entities": [
            {
                "id": entity.id,
                "name": entity.name,
                "type": entity.type.value,
                "confidence": entity.confidence,
                "aliases": list(entity.aliases),
                "document_id": document_id,
                "chunk_id": entity.chunk_id or "",
                "source_document": source_document,
                "updated_at": now,
                "created_at": now,
            }
            for entity in entities
        ],
    }
    return query, params


def _merge_rels_batch(
    label: str,
    rels: list[Relationship],
    document_id: str,
    source_document: str,
    now: str,
) -> tuple[str, list[dict]]:
    """Generate a single UNWIND MERGE query for relationships of one label (M14).

    Uses entity IDs for matching to avoid ambiguity from duplicate entity names.
    Falls back to matching by name when source_type is not available (legacy data).
    """
    query = f"""
    UNWIND $rels AS r
    MATCH (src:Entity)
    WHERE (r.source_id IS NOT NULL AND src.id = r.source_id)
       OR (r.source_id IS NULL AND src.name = r.source_name)
    MATCH (tgt:Entity)
    WHERE (r.target_id IS NOT NULL AND tgt.id = r.target_id)
       OR (r.target_id IS NULL AND tgt.name = r.target_name)
    MERGE (src)-[rel:{label} {{id: r.id}}]->(tgt)
    SET rel.confidence = r.confidence,
        rel.document_id = r.document_id,
        rel.chunk_id = r.chunk_id,
        rel.source_document = COALESCE(rel.source_document, r.source_document),
        rel.updated_at = r.updated_at,
        rel.created_at = COALESCE(rel.created_at, r.created_at)
    """
    params = {
        "rels": [
            {
                "id": rel.id,
                "source_id": _entity_id(rel.source, rel.source_type) if rel.source_type else None,
                "source_name": rel.source,
                "target_id": _entity_id(rel.target, rel.target_type) if rel.target_type else None,
                "target_name": rel.target,
                "confidence": rel.confidence,
                "document_id": document_id,
                "chunk_id": rel.chunk_id or "",
                "source_document": source_document,
                "updated_at": now,
                "created_at": now,
            }
            for rel in rels
        ],
    }
    return query, params


# ── Legacy helpers (preserved for direct unit-test coverage) ──


def _merge_node_query(
    entity: Entity,
    document_id: str,
    source_document: str,
    now: str,
) -> tuple[str, dict]:
    """Generate a MERGE query for a single entity node."""
    query = (
        "MERGE (n:Entity {id: $id}) "
        "SET n.name = $name, "
        "    n.type = $type, "
        "    n.confidence = $confidence, "
        "    n.aliases = $aliases, "
        "    n.document_id = $document_id, "
        "    n.chunk_id = $chunk_id, "
        "    n.source_document = COALESCE(n.source_document, $source_document), "
        "    n.updated_at = $updated_at, "
        "    n.created_at = COALESCE(n.created_at, $created_at)"
    )
    params = {
        "id": entity.id,
        "name": entity.name,
        "type": entity.type.value,
        "confidence": entity.confidence,
        "aliases": list(entity.aliases),
        "document_id": document_id,
        "chunk_id": entity.chunk_id or "",
        "source_document": source_document,
        "updated_at": now,
        "created_at": now,
    }
    return query, params


def _merge_rel_query(
    rel: Relationship,
    document_id: str,
    source_document: str,
    now: str,
) -> tuple[str | None, dict]:
    """Generate a MERGE query for a single relationship.

    Returns (None, {}) if the relationship type is not supported.
    """
    label = REL_TYPE_LABEL.get(rel.type)
    if label is None:
        logger.warning("Unknown relationship type: %s", rel.type)
        return None, {}

    source_id = _entity_id(rel.source, rel.source_type) if rel.source_type else None
    target_id = _entity_id(rel.target, rel.target_type) if rel.target_type else None

    query = (
        "MATCH (src:Entity) "
        "WHERE ($source_id IS NOT NULL AND src.id = $source_id) "
        "   OR ($source_id IS NULL AND src.name = $source_name) "
        "MATCH (tgt:Entity) "
        "WHERE ($target_id IS NOT NULL AND tgt.id = $target_id) "
        "   OR ($target_id IS NULL AND tgt.name = $target_name) "
        f"MERGE (src)-[r:{label} {{id: $id}}]->(tgt) "
        "SET r.confidence = $confidence, "
        "    r.document_id = $document_id, "
        "    r.chunk_id = $chunk_id, "
        "    r.source_document = COALESCE(r.source_document, $source_document), "
        "    r.updated_at = $updated_at, "
        "    r.created_at = COALESCE(r.created_at, $created_at)"
    )
    params = {
        "id": rel.id,
        "source_id": source_id,
        "source_name": rel.source,
        "target_id": target_id,
        "target_name": rel.target,
        "confidence": rel.confidence,
        "document_id": document_id,
        "chunk_id": rel.chunk_id or "",
        "source_document": source_document,
        "updated_at": now,
        "created_at": now,
    }
    return query, params
