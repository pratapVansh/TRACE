"""Deterministic rule-based entity extractor.

Extracts typed entities from document chunk content using regex patterns,
equipment tag conventions, and document metadata. No LLM calls.
"""

from app.extraction.entity import Entity
from app.extraction.normalizer import (
    extract_tag_prefix,
    merge_entities,
    normalize_content,
    normalize_name,
    normalize_tag,
    is_tag_like,
)
from app.extraction.patterns import (
    CONTEXT_PATTERNS,
    EQUIPMENT_TAG,
    NAMED_PATTERNS,
    TAG_PREFIX_CONFIDENCE,
    TAG_PREFIX_TYPE,
)
from app.extraction.types import EntityType


def _seen_tag(tag: str, seen: set[str]) -> bool:
    normalized = normalize_tag(tag)
    if normalized in seen:
        return True
    seen.add(normalized)
    return False


def _extract_from_metadata(
    title: str | None,
    doc_type: str | None,
    document_id: str,
) -> list[Entity]:
    entities: list[Entity] = []

    if title:
        title_clean = normalize_name(title)
        entities.append(Entity(
            name=title_clean,
            type=EntityType.DOCUMENT,
            confidence=0.95,
            document_id=document_id,
            metadata={"source": "document_title"},
        ))

    if doc_type:
        mapped = _map_doc_type_to_entity(doc_type)
        if mapped:
            entities.append(Entity(
                name=normalize_name(doc_type),
                type=mapped,
                confidence=0.80,
                document_id=document_id,
                metadata={"source": "document_type"},
            ))

    return entities


def _map_doc_type_to_entity(doc_type: str) -> EntityType | None:
    lowered = doc_type.lower()
    if "procedure" in lowered or "sop" in lowered or "work instruction" in lowered:
        return EntityType.PROCEDURE
    if "spec" in lowered or "standard" in lowered:
        return EntityType.STANDARD
    if "report" in lowered or "manual" in lowered:
        return EntityType.DOCUMENT
    return None


class EntityExtractor:
    """Rule-based entity extractor for industrial document content.

    Uses regex patterns, equipment tag conventions, and document metadata
    to identify typed entities. Deterministic and reproducible.
    """

    def extract_from_chunk(
        self,
        content: str,
        chunk_id: str,
        document_id: str,
        metadata: dict | None = None,
        document_title: str | None = None,
        document_type: str | None = None,
    ) -> list[Entity]:
        metadata = metadata or {}
        entities: list[Entity] = []
        seen_tags: set[str] = set()

        # M16: normalize content before regex matching
        normalized_content = normalize_content(content)

        # ── Pass 1: Equipment tags with prefix-based type resolution ──
        for match in EQUIPMENT_TAG.finditer(normalized_content):
            raw_tag = match.group("tag")
            tag = normalize_tag(raw_tag)
            if _seen_tag(tag, seen_tags):
                continue

            prefix = extract_tag_prefix(tag)
            if prefix is None:
                continue

            entity_type = TAG_PREFIX_TYPE.get(prefix)
            if entity_type is None:
                continue

            # M19: minimum digit threshold
            digit_part = tag.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ-")
            if digit_part and len(digit_part) < 2:
                continue

            confidence = TAG_PREFIX_CONFIDENCE.get(prefix, 0.90)

            entities.append(Entity(
                name=tag,
                type=entity_type,
                confidence=confidence,
                chunk_id=chunk_id,
                document_id=document_id,
                metadata={
                    "source": "equipment_tag",
                    "context": _extract_context(content, match.start(), match.end()),
                    **metadata,
                },
            ))

        # ── Pass 2: Named patterns ──
        for pattern, entity_type, confidence in NAMED_PATTERNS:
            for match in pattern.finditer(normalized_content):
                raw = match.group(0)
                try:
                    tag = match.group(1)
                except IndexError:
                    tag = raw
                if tag is None:
                    tag = raw
                name = normalize_tag(tag) if is_tag_like(tag) else normalize_name(raw)

                if is_tag_like(name) and _seen_tag(name, seen_tags):
                    continue

                # M19: skip context-only generic word matches that collide with tag patterns
                if name.upper() in {"PUMP", "VALVE", "TANK", "MOTOR", "PIPE", "PIPELINE"}:
                    continue

                entities.append(Entity(
                    name=name,
                    type=entity_type,
                    confidence=confidence,
                    chunk_id=chunk_id,
                    document_id=document_id,
                    metadata={
                        "source": "named_pattern",
                        "matched_text": raw,
                        "context": _extract_context(content, match.start(), match.end()),
                        **metadata,
                    },
                ))

        # ── Pass 3: Context patterns (low confidence) ──
        for pattern, entity_type, confidence in CONTEXT_PATTERNS:
            for match in pattern.finditer(normalized_content):
                raw = match.group(0)
                name = normalize_name(raw)

                if is_tag_like(name) and _seen_tag(name, seen_tags):
                    continue

                entities.append(Entity(
                    name=name,
                    type=entity_type,
                    confidence=confidence,
                    chunk_id=chunk_id,
                    document_id=document_id,
                    metadata={
                        "source": "context_pattern",
                        "matched_text": raw,
                        "context": _extract_context(content, match.start(), match.end()),
                        **metadata,
                    },
                ))

        # ── Pass 4: Document metadata entities ──
        if document_title or document_type:
            metadata_entities = _extract_from_metadata(
                title=document_title,
                doc_type=document_type,
                document_id=document_id,
            )
            for e in metadata_entities:
                entities.append(Entity(
                    name=e.name,
                    type=e.type,
                    confidence=e.confidence,
                    chunk_id=chunk_id,
                    document_id=document_id,
                    metadata={**e.metadata, **metadata},
                ))

        return merge_entities(entities)


def _extract_context(text: str, start: int, end: int, window: int = 40) -> str:
    ctx_start = max(0, start - window)
    ctx_end = min(len(text), end + window)
    prefix = "\u2026" if ctx_start > 0 else ""
    suffix = "\u2026" if ctx_end < len(text) else ""
    return f"{prefix}{text[ctx_start:ctx_end].strip()}{suffix}"
