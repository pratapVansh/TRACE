"""Compare old vs new chunk counts for migration validation.

Reads documents that already have chunks, re-chunks in memory (dry-run)
using the current semantic chunker for comparison, and prints a diff table.

Usage: python -m scripts.compare_chunk_counts
"""
import asyncio
import sys
from datetime import UTC, datetime

sys.path.insert(0, ".")

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.chunking_service import ChunkingService
from app.services.document_mapper import get_latest_version


async def compare() -> None:
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

    print(f"{'Document':<40} {'Old Chunks':<12} {'New Chunks':<12} {'Change':<10}")
    print("-" * 74)

    total_old = 0
    total_new = 0

    for document in documents:
        name = document.original_filename
        doc_id = document.id
        version = get_latest_version(document)

        async with async_session_factory() as session:
            doc_repo = DocumentRepository(session)
            chunk_repo = DocumentChunkRepository(session)

            old_count = await chunk_repo.count_chunks_by_document(doc_id)

            extracted = await doc_repo.get_extracted_text_by_version_id(version.id)
            if extracted is None or not extracted.full_text.strip():
                print(f"{name:<40} {old_count:<12} {'SKIP':<12} {'':<10}")
                continue

            text = extracted.full_text
            pages = extracted.pages or []

            chunking = ChunkingService(session, chunk_repo)
            raw = chunking._chunk_text(text, pages=pages)
            new_count = len(raw)

            total_old += old_count
            total_new += new_count

            diff = new_count - old_count
            diff_str = f"+{diff}" if diff > 0 else str(diff) if diff < 0 else "0"
            print(f"{name:<40} {old_count:<12} {new_count:<12} {diff_str:<10}")

    print("-" * 74)
    total_diff = total_new - total_old
    total_diff_str = f"+{total_diff}" if total_diff > 0 else str(total_diff) if total_diff < 0 else "0"
    print(f"{'TOTAL':<40} {total_old:<12} {total_new:<12} {total_diff_str:<10}")


def main() -> None:
    start = datetime.now(UTC)
    print(f"Chunk count comparison starting at {start.isoformat()}")
    print(f"Chunk size: {settings.chunk_size}, overlap: {settings.chunk_overlap}, min: {settings.chunk_min_size}")
    print()

    asyncio.run(compare())

    elapsed = (datetime.now(UTC) - start).total_seconds()
    print(f"\nFinished in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
