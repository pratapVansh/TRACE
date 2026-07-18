"""Deterministic rule-based relationship extractor.

Extracts typed relationships between entities from document chunk content
using regex patterns. No LLM calls, no Neo4j queries.
"""

import re

from app.extraction.normalizer import normalize_name, normalize_tag, is_tag_like
from app.extraction.relationship import Relationship, RelationshipType
from app.extraction.relationship_patterns import RELATIONSHIP_PATTERNS

_STANDARD_PREFIXES = re.compile(r"^(API|ASME|ASTM|ISO|ANSI|NACE|IEC)\s", re.IGNORECASE)


def _relationships_key(rel: Relationship) -> str:
    return f"{rel.type.value}:{rel.source}:{rel.target}"


def _deduplicate(relationships: list[Relationship]) -> list[Relationship]:
    """Merge identical relationships, keeping highest confidence."""
    seen: dict[str, Relationship] = {}
    for rel in relationships:
        key = _relationships_key(rel)
        if key not in seen or rel.confidence > seen[key].confidence:
            seen[key] = rel
    return list(seen.values())


def _normalize_entity_name(raw: str) -> str:
    cleaned = raw.strip()
    # Standard names (API 610, ASME B31.3) should keep their spaces
    if _STANDARD_PREFIXES.match(cleaned):
        return normalize_name(cleaned)
    tag_normalized = normalize_tag(cleaned)
    if is_tag_like(tag_normalized):
        return tag_normalized
    return normalize_name(cleaned)


class RelationshipExtractor:
    """Rule-based relationship extractor for industrial document content.

    Uses regex patterns to identify typed relationships between entities
    from text. Deterministic and reproducible.
    """

    def extract_from_chunk(
        self,
        content: str,
        chunk_id: str,
        document_id: str,
        metadata: dict | None = None,
    ) -> list[Relationship]:
        """Extract relationships from a single document chunk.

        Args:
            content: The chunk text content.
            chunk_id: Unique identifier for this chunk.
            document_id: Unique identifier for the parent document.
            metadata: Optional chunk-level metadata.

        Returns:
            A deduplicated list of Relationship objects found in the chunk.
        """
        metadata = metadata or {}
        relationships: list[Relationship] = []

        for pattern, rel_type, confidence in RELATIONSHIP_PATTERNS:
            for match in pattern.finditer(content):
                try:
                    raw_src = match.group("src")
                    raw_tgt = match.group("tgt")
                except IndexError:
                    continue

                src = _normalize_entity_name(raw_src.strip())
                tgt = _normalize_entity_name(raw_tgt.strip())

                if not src or not tgt:
                    continue
                if src == tgt:
                    continue

                relationships.append(Relationship(
                    source=src,
                    target=tgt,
                    type=rel_type,
                    confidence=confidence,
                    chunk_id=chunk_id,
                    document_id=document_id,
                    metadata=metadata,
                ))

        return _deduplicate(relationships)

    def extract_from_entities(
        self,
        content: str,
        chunk_id: str,
        document_id: str,
        entities: list[str],
        metadata: dict | None = None,
    ) -> list[Relationship]:
        """Extract relationships, filtering to known entities.

        Only relationships where both source and target appear in the
        provided entity name list are returned.
        """
        entity_set = set()
        for e in entities:
            entity_set.add(_normalize_entity_name(e))

        results = self.extract_from_chunk(
            content=content,
            chunk_id=chunk_id,
            document_id=document_id,
            metadata=metadata,
        )

        filtered: list[Relationship] = []
        for rel in results:
            if rel.source in entity_set and rel.target in entity_set:
                filtered.append(rel)

        return filtered
