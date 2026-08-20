"""Build Knowledge Graph from existing documents in the database.

Reads all documents and their chunks from PostgreSQL, extracts entities
and relationships, and persists them to Neo4j via GraphBuilderService.
"""

import asyncio
import re
import sys
from collections import defaultdict

from sqlalchemy import select

sys.path.insert(0, ".")

from app.db.session import async_session_factory
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.graph.neo4j_graph_store import Neo4jGraphStore
from app.graph.graph_builder import GraphBuilderService
from app.extraction.entity_extractor import EntityExtractor
from app.extraction.relationship_extractor import RelationshipExtractor
from app.extraction.relationship_extractor import RelationshipType, Relationship
from app.extraction.normalizer import merge_entities
from app.extraction.types import EntityType
from app.core.logging import logger


_TAG = re.compile(r"[A-Z]{1,3}\s*[-–—/]?\s*\d{2,6}", re.IGNORECASE)


def _find_tags(text: str) -> set[str]:
    """Find all equipment tag-like strings in text."""
    from app.extraction.normalizer import normalize_tag
    tags = set()
    for m in _TAG.finditer(text):
        tag = normalize_tag(m.group(0))
        tags.add(tag)
    return tags


def _find_failures(text: str) -> list[str]:
    """Find failure/cause keywords in text."""
    keywords = [
        "oil leakage", "leakage", "valve failure", "bearing failure",
        "cavitation", "corrosion", "erosion", "overheating",
        "vibration", "cracking", "rupture", "wear", "fouling",
        "blockage", "misalignment", "fatigue", "degradation",
        "overpressure", "contamination",
    ]
    text_lower = text.lower()
    found = []
    for kw in keywords:
        if kw in text_lower:
            found.append(kw.title())
    return found


def _infer_chunk_relationships(
    content: str,
    entity_names: list[str],
    chunk_id: str,
    document_id: str,
    doc_title: str,
    doc_type: str,
) -> list[Relationship]:
    """Infer relationships from chunk content using pragmatic heuristics."""
    from app.extraction.normalizer import normalize_name
    from app.extraction.patterns import TAG_PREFIX_TYPE
    from app.extraction.relationship_extractor import _normalize_entity_name

    relationships = []
    content_lower = content.lower()
    entity_set = set(entity_names)

    # Find tags in content
    content_tags = _find_tags(content)

    # Build entity-by-type lookup
    for entity_name in entity_names:
        entity_set.add(entity_name)

    # --- Document metadata → equipment relationships ---
    # Extract tag from document title (e.g., INC-001_Pump_Oil_Leakage_P-101 -> P-101)
    title_tags = _find_tags(doc_title)
    for tag in title_tags:
        if tag in entity_set:
            for other_tag in title_tags:
                if other_tag != tag and other_tag in entity_set:
                    relationships.append(Relationship(
                        source=tag,
                        target=other_tag,
                        type=RelationshipType.RELATED_TO,
                        confidence=0.80,
                        chunk_id=chunk_id,
                        document_id=document_id,
                    ))

    # --- HAS_FAILURE inference ---
    # Look for "X failure/inspection/maintenance on Y" patterns
    for tag in content_tags:
        if tag not in entity_set:
            continue

        # Check for failures mentioned in the same context
        for failure in _find_failures(content):
            if failure in entity_set or True:  # Always use if found in context
                # Check if tag and failure appear in proximity
                tag_idx = content_lower.find(tag.lower())
                fail_idx = content_lower.find(failure.lower())
                if tag_idx >= 0 and fail_idx >= 0 and abs(tag_idx - fail_idx) < 500:
                    # Determine direction based on context
                    if fail_idx > tag_idx:
                        # "tag ... failure" → tag HAS_FAILURE failure
                        relationships.append(Relationship(
                            source=tag,
                            target=failure,
                            type=RelationshipType.HAS_FAILURE,
                            confidence=0.70,
                            chunk_id=chunk_id,
                            document_id=document_id,
                        ))
                    else:
                        # "failure ... tag" → tag HAS_FAILURE failure
                        relationships.append(Relationship(
                            source=tag,
                            target=failure,
                            type=RelationshipType.HAS_FAILURE,
                            confidence=0.70,
                            chunk_id=chunk_id,
                            document_id=document_id,
                        ))

    # --- LOCATED_IN inference (Equipment register: "P-101 | ... | Operations | Cracker Unit") ---
    # Check for department/location patterns in tabular content
    loc_patterns = [
        (r"(?:Operations|Maintenance|Engineering|Utilities|Technical)\s*\|\s*([\w\s]+?)(?:\||$)", "department"),
    ]
    for row_line in content.split("\n"):
        row = row_line.strip()
        if "|" not in row:
            continue
        # Check if this row contains an equipment tag
        row_tags = _find_tags(row)
        equipment_tags_in_row = [t for t in row_tags if t in entity_set]
        if not equipment_tags_in_row:
            continue
        parts = [p.strip() for p in row.split("|")]
        # Equipment Register format: Asset ID | Asset Name | Type | Department | Location
        if len(parts) >= 5:
            location = parts[4].strip()
            if location and len(location) > 2 and not _TAG.match(location):
                for tag in equipment_tags_in_row:
                    relationships.append(Relationship(
                        source=tag,
                        target=location,
                        type=RelationshipType.LOCATED_IN,
                        confidence=0.85,
                        chunk_id=chunk_id,
                        document_id=document_id,
                    ))
            department = parts[3].strip() if len(parts) >= 4 else ""
            if department and len(department) > 2:
                for tag in equipment_tags_in_row:
                    relationships.append(Relationship(
                        source=tag,
                        target=department,
                        type=RelationshipType.PART_OF,
                        confidence=0.80,
                        chunk_id=chunk_id,
                        document_id=document_id,
                    ))

    # --- Document structure-based inference ---
    title_lower = doc_title.lower()

    # INC documents: describes an incident involving equipment
    if "inc" in title_lower:
        for tag in content_tags:
            if tag in entity_set:
                relationships.append(Relationship(
                    source=doc_title,
                    target=tag,
                    type=RelationshipType.DESCRIBES,
                    confidence=0.85,
                    chunk_id=chunk_id,
                    document_id=document_id,
                ))
                # Link failures mentioned in context
                for failure in _find_failures(content):
                    if failure in entity_set or failure.lower() in title_lower:
                        # Standardize failure name
                        relationships.append(Relationship(
                            source=tag,
                            target=normalize_name(failure),
                            type=RelationshipType.HAS_FAILURE,
                            confidence=0.80,
                            chunk_id=chunk_id,
                            document_id=document_id,
                        ))

    # INS documents: inspection of equipment
    if "ins" in title_lower or "inspection" in title_lower:
        for tag in content_tags:
            if tag in entity_set:
                relationships.append(Relationship(
                    source=doc_title,
                    target=tag,
                    type=RelationshipType.INSPECTS,
                    confidence=0.85,
                    chunk_id=chunk_id,
                    document_id=document_id,
                ))

    # MNT documents: maintenance of equipment
    if "mnt" in title_lower or "maintenance" in title_lower:
        for tag in content_tags:
            if tag in entity_set:
                relationships.append(Relationship(
                    source=doc_title,
                    target=tag,
                    type=RelationshipType.MAINTAINED_BY,
                    confidence=0.85,
                    chunk_id=chunk_id,
                    document_id=document_id,
                ))

    # SOP documents: procedure for equipment
    if "sop" in title_lower or "procedure" in title_lower:
        for tag in content_tags:
            if tag in entity_set:
                relationships.append(Relationship(
                    source=doc_title,
                    target=tag,
                    type=RelationshipType.FOLLOWS,
                    confidence=0.85,
                    chunk_id=chunk_id,
                    document_id=document_id,
                ))
                relationships.append(Relationship(
                    source=tag,
                    target=doc_title,
                    type=RelationshipType.REFERENCES,
                    confidence=0.80,
                    chunk_id=chunk_id,
                    document_id=document_id,
                ))

    # MAN documents: manual describes equipment
    if "man" in title_lower or "manual" in title_lower:
        for tag in content_tags:
            if tag in entity_set:
                relationships.append(Relationship(
                    source=doc_title,
                    target=tag,
                    type=RelationshipType.DESCRIBES,
                    confidence=0.90,
                    chunk_id=chunk_id,
                    document_id=document_id,
                ))

    # SCN documents: schematic references equipment
    if "scn" in title_lower or "schematic" in title_lower or "p&id" in content_lower:
        for tag in content_tags:
            if tag in entity_set:
                relationships.append(Relationship(
                    source=doc_title,
                    target=tag,
                    type=RelationshipType.REFERENCES,
                    confidence=0.80,
                    chunk_id=chunk_id,
                    document_id=document_id,
                ))

    # LOG documents: operator log, connect operators to equipment
    if "log" in title_lower or "shift" in title_lower:
        for tag in content_tags:
            if tag in entity_set:
                operator_entities = [n for n in entity_names if any(
                    op in n.lower() for op in ["operator", "shift", "engineer", "technician"]
                )]
                for op in operator_entities:
                    relationships.append(Relationship(
                        source=op,
                        target=tag,
                        type=RelationshipType.OPERATES,
                        confidence=0.65,
                        chunk_id=chunk_id,
                        document_id=document_id,
                    ))

    # PPT documents: presentation references equipment
    if "ppt" in title_lower or "presentation" in title_lower or "overview" in title_lower:
        for tag in content_tags:
            if tag in entity_set:
                relationships.append(Relationship(
                    source=doc_title,
                    target=tag,
                    type=RelationshipType.REFERENCES,
                    confidence=0.75,
                    chunk_id=chunk_id,
                    document_id=document_id,
                ))

    return relationships


async def build_graph():
    graph_store = Neo4jGraphStore()
    await graph_store.connect()
    logger.info("Neo4j connected")

    entity_extractor = EntityExtractor()
    rel_extractor = RelationshipExtractor()
    builder = GraphBuilderService(graph_store=graph_store)

    async with async_session_factory() as session:
        result = await session.execute(
            select(Document).where(Document.deleted_at.is_(None))
        )
        documents = result.scalars().all()
        logger.info("Found %d active documents", len(documents))

        total_entities = 0
        total_relationships = 0

        for doc in documents:
            doc_id_str = str(doc.id)
            doc_title = doc.title or ""
            doc_type = doc.doc_type or ""

            chunks_result = await session.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == doc.id)
                .order_by(DocumentChunk.chunk_index)
            )
            chunks = chunks_result.scalars().all()

            if not chunks:
                logger.info(
                    "No chunks for doc %s (%s), skipping",
                    doc_id_str, doc.original_filename,
                )
                continue

            # ── Step 1: Extract entities ──
            all_entities = []
            for chunk in chunks:
                entities = entity_extractor.extract_from_chunk(
                    content=chunk.content,
                    chunk_id=str(chunk.id),
                    document_id=doc_id_str,
                    metadata=chunk.extra_metadata or {},
                    document_title=doc_title,
                    document_type=doc_type,
                )
                all_entities.extend(entities)

            merged = merge_entities(all_entities)
            entity_names = [e.name for e in merged]

            # ── Step 2: Extract relationships via regex ──
            all_relationships = []
            for chunk in chunks:
                rels = rel_extractor.extract_from_entities(
                    content=chunk.content,
                    chunk_id=str(chunk.id),
                    document_id=doc_id_str,
                    entities=entity_names,
                    metadata=chunk.extra_metadata or {},
                )
                all_relationships.extend(rels)

            # ── Step 3: Infer additional relationships from context ──
            for chunk in chunks:
                inferred = _infer_chunk_relationships(
                    content=chunk.content,
                    entity_names=entity_names,
                    chunk_id=str(chunk.id),
                    document_id=doc_id_str,
                    doc_title=doc_title,
                    doc_type=doc_type,
                )
                all_relationships.extend(inferred)

            # ── Step 4: Deduplicate relationships (keep highest confidence) ──
            seen_rels = {}
            for rel in all_relationships:
                if rel.id not in seen_rels or rel.confidence > seen_rels[rel.id].confidence:
                    seen_rels[rel.id] = rel
            deduped_rels = list(seen_rels.values())

            # ── Step 5: Persist to Neo4j ──
            result = await builder.process_document(
                document_id=doc_id_str,
                entities=merged,
                relationships=deduped_rels,
                source_document=doc.original_filename or doc_title,
            )

            if result.successful:
                total_entities += result.nodes_merged
                total_relationships += result.relationships_merged
                logger.info(
                    "Doc %s (%s): %d nodes, %d rels (%d before dedup, %d after)",
                    doc_id_str, doc.original_filename,
                    result.nodes_merged, result.relationships_merged,
                    len(all_relationships), len(deduped_rels),
                )
            else:
                logger.error(
                    "Doc %s (%s) failed: %s",
                    doc_id_str, doc.original_filename, result.error,
                )

    logger.info(
        "Build complete: %d total entities, %d total relationships",
        total_entities, total_relationships,
    )
    await graph_store.close()
    return total_entities, total_relationships


if __name__ == "__main__":
    asyncio.run(build_graph())
