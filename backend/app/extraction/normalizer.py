import re

from app.extraction.entity import Entity
from app.extraction.types import EntityType

_WHITESPACE = re.compile(r"\s+")
_DASH_VARIANT = re.compile(r"[-–—/]+")
_LETTER_TO_DIGIT = re.compile(r"(?<=[A-Za-z])(?=\d)")
_TAG_PREFIX = re.compile(r"^[A-Z]{1,3}")
_TAG_LIKE = re.compile(r"^[A-Z]{1,3}-?\d{2,}$")
_UNDERSCORE = re.compile(r"_+")


def normalize_tag(raw: str) -> str:
    cleaned = _WHITESPACE.sub("", raw.strip())
    cleaned = _DASH_VARIANT.sub("-", cleaned)
    cleaned = _LETTER_TO_DIGIT.sub("-", cleaned)
    cleaned = cleaned.upper()
    return cleaned


def normalize_name(raw: str) -> str:
    cleaned = _WHITESPACE.sub(" ", raw.strip())
    cleaned = _DASH_VARIANT.sub("-", cleaned)
    return cleaned


def normalize_content(text: str) -> str:
    """Normalize chunk content before regex matching (M16).

    Replaces underscores, multiple spaces, and dash variants with a
    canonical form so equipment-tag regexes can match consistently.
    """
    text = _UNDERSCORE.sub(" ", text)
    text = _DASH_VARIANT.sub("-", text)
    text = _WHITESPACE.sub(" ", text)
    return text


def extract_tag_prefix(name: str) -> str | None:
    m = _TAG_PREFIX.match(name)
    if m:
        return m.group(0)
    return None


def is_tag_like(name: str) -> bool:
    return bool(_TAG_LIKE.match(name.upper()))


def entities_key(entity: Entity) -> str:
    """Return a deduplication key for an entity (H7).

    Tag-like entities use normalize_tag (case-insensitive, dash-unified).
    Named entities use normalize_name (preserves spaces, case-insensitive comparison).
    This prevents collisions between e.g. a Pump tag "P-101" and a
    named entity whose name normalizes identically under normalize_tag.
    """
    if is_tag_like(entity.name):
        normalized = normalize_tag(entity.name)
    else:
        normalized = normalize_name(entity.name).lower()
    return f"{entity.type.value}:{normalized}"


def merge_entities(entities: list[Entity]) -> list[Entity]:
    merged: dict[str, Entity] = {}

    for entity in entities:
        key = entities_key(entity)
        if key not in merged:
            merged[key] = entity
        else:
            existing = merged[key]
            all_aliases: set[str] = set()
            all_aliases.add(existing.name)
            all_aliases.update(existing.aliases)
            all_aliases.add(entity.name)
            all_aliases.update(entity.aliases)
            all_aliases.discard(existing.name)

            best = existing if existing.confidence >= entity.confidence else entity

            merged[key] = Entity(
                name=best.name,
                type=best.type,
                aliases=tuple(sorted(all_aliases)),
                confidence=best.confidence,
                chunk_id=best.chunk_id,
                document_id=best.document_id,
                metadata=_deep_merge(existing.metadata, entity.metadata),
            )

    return list(merged.values())


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge two metadata dicts (M17)."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
