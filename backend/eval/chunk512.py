"""Build the separate Qdrant collection for the chunk-size ablation.

    python -m eval.chunk512

Re-chunks every active document's extracted text at 512 / 64 tokens (the
probe's run 1 setting) with TRACE's own chunker, embeds with the production
embedding model and indexes into ``eval_chunks_512``. Postgres is only read;
the production ``document_chunks`` collection is never touched. The collection
is recreated on every run, so the build is repeatable.
"""

import asyncio
import json
import sys
import uuid

from eval.schema import EVAL_DIR

COLLECTION = "eval_chunks_512"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64


async def build() -> dict:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.core.cache import cache_manager
    from app.core.config import settings
    from app.db.session import async_session_factory
    from app.models.document import Document
    from app.models.document_extracted_text import DocumentExtractedText
    from app.services.chunking_service import ChunkingService
    from app.services.document_mapper import get_latest_version
    from app.services.embedding_service import _encode_batch_async
    from app.services.vector_store import QdrantVectorStore

    assert COLLECTION.startswith("eval_") and COLLECTION != "document_chunks"
    settings.qdrant_collection_name = COLLECTION
    settings.chunk_size = CHUNK_SIZE
    settings.chunk_overlap = CHUNK_OVERLAP
    cache_manager._local_cache.cache.clear()

    store = QdrantVectorStore()
    await store.connect()
    if await store.collection_exists():
        await store.delete_collection()
    await store.create_collection()
    await store.create_fulltext_index()

    # _chunk_text is pure: it reads settings.chunk_size and never uses the
    # session or repository, so no chunk rows are written.
    chunker = ChunkingService(session=None, chunk_repository=None)
    counts: dict[str, int] = {}
    vectors = []
    async with async_session_factory() as session:
        documents = (await session.execute(
            select(Document).options(selectinload(Document.versions)).where(Document.deleted_at.is_(None))
        )).scalars().all()
        for document in documents:
            version = get_latest_version(document)
            extracted = (await session.execute(
                select(DocumentExtractedText).where(DocumentExtractedText.document_version_id == version.id)
            )).scalar_one_or_none()
            if extracted is None or not extracted.full_text.strip():
                continue
            chunks = chunker._chunk_text(extracted.full_text, pages=extracted.pages or [])
            embeddings = await _encode_batch_async([c["content"] for c in chunks])
            counts[document.original_filename] = len(chunks)
            for chunk, embedding in zip(chunks, embeddings):
                point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document.id}:{CHUNK_SIZE}:{chunk['chunk_index']}"))
                payload = {
                    "chunk_id": point_id,
                    "document_id": str(document.id),
                    "filename": document.original_filename,
                    "content": chunk["content"],
                    "document_type": document.doc_type,
                    "metadata": chunk.get("extra_metadata") or {},
                    "chunk_index": chunk["chunk_index"],
                }
                if chunk.get("page_number") is not None:
                    payload["page_number"] = chunk["page_number"]
                vectors.append({"point_id": point_id, "vector": embedding, "payload": payload})

    indexed = await store.upsert_vectors(vectors)
    return {
        "collection": COLLECTION,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "documents": len(counts),
        "chunks": sum(counts.values()),
        "indexed": indexed,
        "chunks_per_document": dict(sorted(counts.items())),
    }


def main() -> int:
    summary = asyncio.run(build())
    out = EVAL_DIR / "results" / "chunk512"
    out.mkdir(parents=True, exist_ok=True)
    (out / "collection.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "chunks_per_document"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
