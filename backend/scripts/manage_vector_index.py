"""Inspect, adopt, or rebuild TRACE's Qdrant embedding collection.

Run from ``backend`` (or from the backend container):

    python scripts/manage_vector_index.py status
    python scripts/manage_vector_index.py stamp-existing --confirm-model all-MiniLM-L6-v2
    python scripts/manage_vector_index.py reindex --confirm-collection document_chunks

``stamp-existing`` is only for a legacy collection whose vectors are known to
have been produced by the configured model. It verifies the physical vector
dimension and refuses conflicting metadata. ``reindex`` is the migration path
for an actual model/dimension change and regenerates embeddings from the
existing chunks.
"""

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import update

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.document_chunk import DocumentChunk
from app.services.vector_store import (
    EMBEDDING_MODEL_METADATA_KEY,
    VECTOR_DIMENSION,
    VECTOR_DIMENSION_METADATA_KEY,
    QdrantVectorStore,
    VectorStoreConfigurationError,
)


async def show_status(store: QdrantVectorStore) -> bool:
    await store.connect()
    if not await store.collection_exists():
        print(f"Collection: {settings.qdrant_collection_name} (absent)")
        return False
    metadata, physical_dimension = await store.get_embedding_metadata()
    print(f"Collection: {settings.qdrant_collection_name}")
    print(f"Configured model: {settings.embedding_model_name}")
    print(f"Configured dimension: {VECTOR_DIMENSION}")
    print(f"Stored model: {metadata.get(EMBEDDING_MODEL_METADATA_KEY, '<missing>')}")
    print(
        "Stored dimension: "
        f"{metadata.get(VECTOR_DIMENSION_METADATA_KEY, '<missing>')}"
    )
    print(f"Physical dimension: {physical_dimension}")
    try:
        await store.verify_embedding_compatibility()
    except VectorStoreConfigurationError as exc:
        print(f"Compatibility: BLOCKED ({exc})")
        return False
    print("Compatibility: OK")
    return True


async def stamp_existing(store: QdrantVectorStore, confirmed_model: str) -> None:
    """Adopt a known legacy collection without changing any vectors."""
    await store.connect()
    if confirmed_model != settings.embedding_model_name:
        raise SystemExit(
            "--confirm-model must exactly match EMBEDDING_MODEL_NAME "
            f"({settings.embedding_model_name!r})"
        )
    if not await store.collection_exists():
        raise SystemExit("Collection does not exist; start the backend to create it")

    metadata, physical_dimension = await store.get_embedding_metadata()
    if physical_dimension != VECTOR_DIMENSION:
        raise SystemExit(
            f"Physical dimension {physical_dimension!r} does not match configured "
            f"dimension {VECTOR_DIMENSION}; use reindex"
        )
    stored_model = metadata.get(EMBEDDING_MODEL_METADATA_KEY)
    stored_dimension = metadata.get(VECTOR_DIMENSION_METADATA_KEY)
    if stored_model not in (None, settings.embedding_model_name):
        raise SystemExit(
            f"Collection already declares model {stored_model!r}; use reindex"
        )
    if stored_dimension not in (None, VECTOR_DIMENSION):
        raise SystemExit(
            f"Collection already declares dimension {stored_dimension!r}; use reindex"
        )

    await store.stamp_embedding_metadata()
    await store.verify_embedding_compatibility()
    print("Compatibility metadata stamped; vectors were not modified.")


async def reindex(store: QdrantVectorStore, confirmed_collection: str) -> None:
    """Rebuild all active-document vectors with the configured embedding model."""
    if confirmed_collection != settings.qdrant_collection_name:
        raise SystemExit(
            "--confirm-collection must exactly match QDRANT_COLLECTION_NAME "
            f"({settings.qdrant_collection_name!r})"
        )

    await store.connect()
    await store.delete_collection()

    # Stored JSON embeddings belong to the old vector space too. Mark every
    # chunk pending so the normal, tested backfill pipeline regenerates them.
    async with async_session_factory() as session:
        await session.execute(
            update(DocumentChunk).values(embedding=None, embedding_status="pending")
        )
        await session.commit()

    # Import late so status/stamp operations do not initialize ingestion code.
    from scripts.backfill_chunks_embeddings_index import backfill

    processed = await backfill()
    await store.verify_embedding_compatibility()
    print(
        f"Reindex complete: {processed} active document(s) processed with "
        f"{settings.embedding_model_name} ({VECTOR_DIMENSION} dimensions)."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Qdrant embedding compatibility")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Show stored and configured embedding metadata")
    stamp = commands.add_parser(
        "stamp-existing",
        help="Adopt a known-compatible legacy collection without re-embedding",
    )
    stamp.add_argument("--confirm-model", required=True)
    rebuild = commands.add_parser(
        "reindex",
        help="Destructively rebuild embeddings and vectors for a model migration",
    )
    rebuild.add_argument("--confirm-collection", required=True)
    return parser


async def run(args: argparse.Namespace) -> int:
    store = QdrantVectorStore()
    if args.command == "status":
        return 0 if await show_status(store) else 2
    if args.command == "stamp-existing":
        await stamp_existing(store, args.confirm_model)
        return 0
    await reindex(store, args.confirm_collection)
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(run(build_parser().parse_args())))


if __name__ == "__main__":
    main()
