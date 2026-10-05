from dataclasses import dataclass, field
from hashlib import sha256

from app.extraction.types import EntityType


def _entity_id(name: str, type_: EntityType, document_id: str = "") -> str:
    """Return a stable entity id, scoped to a source document when known.

    Graph entities carry a single ``document_id`` and are deleted by that
    value. A global name/type id therefore lets a later document overwrite
    the first document's provenance and makes either document's deletion
    unsafe. The empty default preserves legacy/direct-call compatibility;
    ingestion always supplies a document id.
    """
    scope = f":{document_id}" if document_id else ""
    raw = f"{type_.value}:{name.lower()}{scope}"
    return sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Entity:
    name: str
    type: EntityType
    aliases: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 1.0
    chunk_id: str = ""
    document_id: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return _entity_id(self.name, self.type, self.document_id)

    def with_confidence(self, value: float) -> "Entity":
        return Entity(
            name=self.name,
            type=self.type,
            aliases=self.aliases,
            confidence=value,
            chunk_id=self.chunk_id,
            document_id=self.document_id,
            metadata=self.metadata,
        )

    def with_alias(self, alias: str) -> "Entity":
        existing = self.aliases
        if alias != self.name and alias not in existing:
            existing = existing + (alias,)
        return Entity(
            name=self.name,
            type=self.type,
            aliases=existing,
            confidence=self.confidence,
            chunk_id=self.chunk_id,
            document_id=self.document_id,
            metadata=self.metadata,
        )
