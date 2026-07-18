"""Investigate chunk counts per document vs extracted text lengths."""

import asyncio
from sqlalchemy import select, func, text
from app.db.session import async_session_factory


async def main():
    async with async_session_factory() as session:
        # 1. Per-document report
        result = await session.execute(text("""
            SELECT
                d.original_filename,
                d.doc_type,
                LENGTH(et.full_text) AS text_len,
                COUNT(dc.id) AS chunk_count,
                COALESCE(AVG(dc.token_count), 0)::int AS avg_tokens,
                COALESCE(MAX(dc.token_count), 0)::int AS max_tokens,
                COALESCE(MIN(dc.token_count), 0)::int AS min_tokens,
                COALESCE(SUM(dc.token_count), 0)::int AS total_tokens,
                CASE WHEN COUNT(dc.id) > 0
                    THEN ROUND(LENGTH(et.full_text)::numeric / COUNT(dc.id))
                    ELSE 0
                END AS avg_chars_per_chunk,
                et.full_text IS NOT NULL AND LENGTH(et.full_text) > 0 AS has_text
            FROM documents d
            JOIN document_versions dv ON dv.document_id = d.id AND dv.is_latest = TRUE
            JOIN document_extracted_text et ON et.document_version_id = dv.id
            LEFT JOIN document_chunks dc ON dc.document_id = d.id
            WHERE d.deleted_at IS NULL
            GROUP BY d.id, d.original_filename, d.doc_type, et.full_text
            ORDER BY LENGTH(et.full_text) DESC
        """))

        rows = result.fetchall()
        print(f"{'Document Name':45s} {'Type':12s} {'Chars':>8s} {'Chunks':>7s} {'AvgTok':>7s} {'MaxTok':>7s} {'MinTok':>7s} {'AvgChr':>8s}")
        print("-" * 110)
        total_chars = 0
        total_chunks = 0
        total_tokens = 0
        for r in rows:
            total_chars += r.text_len
            total_chunks += r.chunk_count
            total_tokens += r.total_tokens
            fn = (r.original_filename or "")[:44]
        print(f"{fn:45s} {r.doc_type or '':12s} {r.text_len:>8d} {r.chunk_count:>7d} {r.avg_tokens:>7d} {r.max_tokens:>7d} {r.min_tokens:>7d} {r.avg_chars_per_chunk:>8d}")

        n = len(rows)
        print("-" * 110)
        print(f"{'TOTAL':45s} {'':12s} {total_chars:>8d} {total_chunks:>7d} {'':>7s} {'':>7s} {'':>7s} {'':>8s}")
        print(f"\nDocuments: {n}")
        print(f"Total chars: {total_chars}")
        print(f"Total chunks: {total_chunks}")
        print(f"Avg chunks/document: {total_chunks/n:.2f}")
        print(f"Avg chars/document: {total_chars//n}")

        # 2. Check if any single-chunk docs have enough text for multiple chunks
        print("\n\n=== Single-Chunk Deep Dive ===")
        result = await session.execute(text("""
            SELECT
                d.original_filename,
                LENGTH(et.full_text) AS text_len,
                dc.token_count,
                dc.content
            FROM documents d
            JOIN document_versions dv ON dv.document_id = d.id AND dv.is_latest = TRUE
            JOIN document_extracted_text et ON et.document_version_id = dv.id
            LEFT JOIN document_chunks dc ON dc.document_id = d.id
            WHERE d.deleted_at IS NULL
              AND (SELECT COUNT(*) FROM document_chunks WHERE document_id = d.id) <= 1
            ORDER BY LENGTH(et.full_text) DESC
            LIMIT 5
        """))
        for r in result:
            content_preview = r.content[:200] if r.content else "(no content)"
            fn = (r.original_filename or "")[:44]
            print(f"\n{fn:45s} text_len={r.text_len} chunk_token_count={r.token_count}")
            print(f"  Content preview: {content_preview}...")

        # 3. Check total tokens consumed
        result = await session.execute(text("""
            SELECT
                d.original_filename,
                LENGTH(et.full_text) AS text_len,
                ROUND(LENGTH(et.full_text) / 4.0)::int AS est_tokens,
                COALESCE(SUM(dc.token_count), 0)::int AS actual_tokens,
                ROUND(LENGTH(et.full_text) / 500.0)::int AS est_chunks_500char
            FROM documents d
            JOIN document_versions dv ON dv.document_id = d.id AND dv.is_latest = TRUE
            JOIN document_extracted_text et ON et.document_version_id = dv.id
            LEFT JOIN document_chunks dc ON dc.document_id = d.id
            WHERE d.deleted_at IS NULL
            GROUP BY d.id, d.original_filename, et.full_text
            ORDER BY LENGTH(et.full_text) DESC
        """))
        print("\n\n=== Token Analysis ===")
        print(f"{'Document Name':45s} {'Chars':>8s} {'EstTok':>8s} {'ActTok':>8s} {'Est500Ch':>8s}")
        print("-" * 85)
        for r in result:
            print(f"{r.original_filename:45s} {r.text_len:>8d} {r.est_tokens:>8d} {r.actual_tokens:>8d} {r.est_chunks_500char:>8d}")


asyncio.run(main())
