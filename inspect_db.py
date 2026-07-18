import sqlalchemy as sa
from sqlalchemy import create_engine, text
from datetime import datetime, timezone

DB_URL = "postgresql+psycopg2://trace:trace@localhost:5432/trace"
engine = create_engine(DB_URL)

def fmt(val):
    if val is None:
        return "NULL"
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)

def run():
    with engine.connect() as conn:
        print("=" * 80)
        print("DATABASE INSPECTION REPORT")
        print("=" * 80)

        # 1. Documents
        print("\n--- 1. DOCUMENTS ---")
        rows = conn.execute(text("SELECT id, title, original_filename, doc_type, status, deleted_at, created_at FROM documents ORDER BY created_at")).fetchall()
        print(f"Total documents: {len(rows)}")
        soft_deleted = [r for r in rows if r.deleted_at is not None]
        print(f"Soft-deleted (deleted_at IS NOT NULL): {len(soft_deleted)}")
        print()
        for r in rows:
            print(f"  ID={r.id}  title={r.title}  file={r.original_filename}  type={r.doc_type}  status={r.status}  deleted_at={fmt(r.deleted_at)}  created_at={fmt(r.created_at)}")

        # 2. DocumentVersions
        print("\n--- 2. DOCUMENT VERSIONS ---")
        dv_count = conn.execute(text("SELECT COUNT(*) FROM document_versions")).scalar()
        print(f"Total document_versions rows: {dv_count}")
        dv_per_doc = conn.execute(text("SELECT document_id, COUNT(*) as cnt FROM document_versions GROUP BY document_id ORDER BY cnt DESC")).fetchall()
        print(f"Documents with versions: {len(dv_per_doc)}")
        for r in dv_per_doc:
            print(f"  document_id={r.document_id}  versions={r.cnt}")

        # 3. DocumentExtractedText
        print("\n--- 3. DOCUMENT EXTRACTED TEXT ---")
        det_count = conn.execute(text("SELECT COUNT(*) FROM document_extracted_text")).scalar()
        print(f"Total document_extracted_text rows: {det_count}")
        doc_count = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()
        print(f"Documents with extracted text: {det_count} / {doc_count}")
        if det_count < doc_count:
            missing = conn.execute(text("""
                SELECT d.id, d.title
                FROM documents d
                WHERE d.id NOT IN (
                    SELECT dv.document_id
                    FROM document_versions dv
                    JOIN document_extracted_text det ON det.document_version_id = dv.id
                )
            """)).fetchall()
            print(f"Documents MISSING extracted text ({len(missing)}):")
            for r in missing:
                print(f"  ID={r.id}  title={r.title}")

        # 4. IngestionJobs
        print("\n--- 4. INGESTION JOBS ---")
        jobs = conn.execute(text("SELECT id, document_id, status, stage, error, retry_count, created_at, finished_at FROM ingestion_jobs ORDER BY created_at")).fetchall()
        print(f"Total ingestion jobs: {len(jobs)}")
        for r in jobs:
            print(f"  ID={r.id}  doc_id={r.document_id}  status={r.status}  stage={r.stage}  error={fmt(r.error)}  retries={r.retry_count}  created={fmt(r.created_at)}  finished={fmt(r.finished_at)}")

        # 5. DocumentChunks
        print("\n--- 5. DOCUMENT CHUNKS ---")
        total_chunks = conn.execute(text("SELECT COUNT(*) FROM document_chunks")).scalar()
        print(f"Total document_chunks: {total_chunks}")
        chunks_per_doc = conn.execute(text("SELECT document_id, COUNT(*) as cnt FROM document_chunks GROUP BY document_id ORDER BY cnt DESC")).fetchall()
        print(f"Documents with chunks: {len(chunks_per_doc)}")
        for r in chunks_per_doc:
            print(f"  document_id={r.document_id}  chunks={r.cnt}")
        docs_with_chunks = {r.document_id for r in chunks_per_doc}
        all_docs = conn.execute(text("SELECT id, title FROM documents")).fetchall()
        zero_chunk_docs = [d for d in all_docs if d.id not in docs_with_chunks]
        print(f"Documents with ZERO chunks: {len(zero_chunk_docs)}")
        for d in zero_chunk_docs:
            print(f"  ID={d.id}  title={d.title}")
        print()
        embed_status = conn.execute(text("SELECT embedding_status, COUNT(*) as cnt FROM document_chunks GROUP BY embedding_status ORDER BY cnt DESC")).fetchall()
        print("Chunks by embedding_status:")
        for r in embed_status:
            print(f"  {r.embedding_status}: {r.cnt}")

        # 6. Documents not 'indexed' but uploaded for a while
        print("\n--- 6. DOCUMENTS NOT INDEXED (uploaded > 5 min ago) ---")
        stale = conn.execute(text("""
            SELECT id, title, status, created_at
            FROM documents
            WHERE status != 'indexed'
              AND created_at < NOW() - INTERVAL '5 minutes'
            ORDER BY created_at
        """)).fetchall()
        print(f"Count: {len(stale)}")
        for r in stale:
            print(f"  ID={r.id}  title={r.title}  status={r.status}  created_at={fmt(r.created_at)}")

        print("\n" + "=" * 80)
        print("INSPECTION COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    run()
