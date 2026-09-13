"""Read the indexed corpus - read-only - for validation and scoring.

Chunks come from Postgres (the canonical 256-token corpus) or from a Qdrant
collection (used for the separate 512-token evaluation collection). Nothing in
this module writes to either store.
"""

import hashlib
from collections import defaultdict

CHUNK_SEPARATOR = "\x1e"


def chunk_fingerprint(contents: list[str]) -> str:
    """sha256 of a document's chunk contents in chunk_index order."""
    return hashlib.sha256(CHUNK_SEPARATOR.join(contents).encode("utf-8")).hexdigest()


async def load_postgres_chunks() -> dict[str, list[str]]:
    """Active documents' chunk contents keyed by original filename."""
    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk

    by_doc: dict[str, list[str]] = {}
    async with async_session_factory() as session:
        rows = await session.execute(
            select(Document.original_filename, DocumentChunk.content)
            .join(DocumentChunk, DocumentChunk.document_id == Document.id)
            .where(Document.deleted_at.is_(None))
            .order_by(Document.original_filename, DocumentChunk.chunk_index)
        )
        for filename, content in rows.all():
            by_doc.setdefault(filename, []).append(content)
    return by_doc


def load_qdrant_chunks(collection: str) -> dict[str, list[str]]:
    """Chunk contents from a Qdrant collection, keyed by filename, in chunk order."""
    from qdrant_client import QdrantClient

    from app.core.config import settings

    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
    grouped: dict[str, list[tuple[int, str]]] = defaultdict(list)
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection,
            limit=256,
            offset=offset,
            with_payload=["filename", "content", "chunk_index"],
            with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            grouped[payload.get("filename", "")].append(
                (payload.get("chunk_index") or 0, payload.get("content", ""))
            )
        if offset is None:
            break
    return {name: [c for _, c in sorted(items)] for name, items in grouped.items()}
