"""Backfill chunks, embeddings, and Qdrant indexing for existing documents.

One-time migration for documents processed through an early pipeline version
that did not include chunking, embedding, or Qdrant indexing.

Idempotent: skips documents that already have chunks (unless --force is passed).
"""
import argparse
import asyncio
import sys
from datetime import UTC, datetime

sys.path.insert(0, ".")

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.document import Document
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.chunking_service import ChunkingService
from app.services.document_mapper import get_latest_version
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_indexing_service import QdrantIndexingService
from app.services.vector_store import QdrantVectorStore


async def backfill(*, force: bool = False) -> int:
    qdrant_store = QdrantVectorStore()
    await qdrant_store.connect()
    await qdrant_store.create_collection()
    await qdrant_store.create_fulltext_index()

    async with async_session_factory() as session:
        doc_repo = DocumentRepository(session)
        chunk_repo = DocumentChunkRepository(session)

        result = await session.execute(
            select(Document)
            .options(selectinload(Document.versions))
            .where(Document.deleted_at.is_(None))
            .order_by(Document.original_filename)
        )
        documents: list[Document] = list(result.scalars().all())
    print(f"Found {len(documents)} active documents")

    processed = 0
    for document in documents:
        name = document.original_filename
        doc_id = document.id

        # Use a fresh session per document for clean transaction isolation
        async with async_session_factory() as session:
            doc_repo = DocumentRepository(session)
            chunk_repo = DocumentChunkRepository(session)
            chunking = ChunkingService(session, chunk_repo)
            embedding = EmbeddingService(session, chunk_repo)
            indexing = QdrantIndexingService(qdrant_store)

            try:
                if force:
                    await chunking.delete_document_chunks(doc_id)
                    await qdrant_store.delete_vectors_by_document(doc_id)
                    await session.flush()

                existing = await chunk_repo.count_chunks_by_document(doc_id)
                if existing > 0:
                    print(f"  SKIP  {name} -- {existing} chunk(s) already exist")
                    await session.commit()
                    continue

                version = get_latest_version(document)
                extracted = await doc_repo.get_extracted_text_by_version_id(version.id)
                if extracted is None or not extracted.full_text.strip():
                    print(f"  SKIP  {name} -- no extracted text")
                    await session.commit()
                    continue

                text = extracted.full_text
                pages = extracted.pages or []
                print(f"  CHUNK {name} -- text_length={len(text)}", end="", flush=True)

                chunks = await chunking.chunk_document(
                    doc_id, text=text, pages=pages, filename=name, language=None,
                )
                chunk_count = len(chunks)
                if chunk_count == 0:
                    print(" => 0 chunks")
                    await session.commit()
                    continue
                print(f" => {chunk_count} chunks", end="", flush=True)

                embedded = await embedding.generate_for_document(doc_id)
                print(f" => {embedded} embedded", end="", flush=True)

                completed_chunks = await chunk_repo.get_chunks_by_document(
                    doc_id, embedding_status="completed",
                )
                if completed_chunks:
                    indexed = await indexing.index_document_chunks(
                        chunks=list(completed_chunks),
                        document=document,
                    )
                    print(f" => {indexed} indexed")
                else:
                    print(" => 0 indexed (no completed embeddings)")

                await session.commit()
                processed += 1

            except Exception as exc:
                await session.rollback()
                print(f" => FAILED: {exc}")
                continue

    print(f"\nDone. Processed {processed} document(s)")
    return processed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill chunks, embeddings, and Qdrant indexing.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-chunk documents that already have chunks (deletes existing data first)",
    )
    args = parser.parse_args()

    start = datetime.now(UTC)
    print(f"Backfill starting at {start.isoformat()}")
    print(f"Qdrant: {settings.qdrant_url}")
    print(f"Collection: {settings.qdrant_collection_name}")
    print(f"Embedding model: {settings.embedding_model_name}")
    if args.force:
        print("Force mode: re-chunking all documents (existing data will be replaced)")
    print()

    count = asyncio.run(backfill(force=args.force))

    elapsed = (datetime.now(UTC) - start).total_seconds()
    print(f"\nFinished in {elapsed:.1f}s -- {count} document(s) processed")


if __name__ == "__main__":
    main()
