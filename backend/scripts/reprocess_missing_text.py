"""Re-process documents that have no extracted text (e.g., LOG files)."""

import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "trace",
    "password": "trace",
    "dbname": "trace",
}


def run_reprocess() -> int:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT d.id, d.original_filename, ij.id as job_id
        FROM documents d
        JOIN document_versions dv ON dv.document_id = d.id AND dv.is_latest = TRUE
        LEFT JOIN document_extracted_text det ON det.document_version_id = dv.id
        LEFT JOIN LATERAL (
            SELECT id FROM ingestion_jobs
            WHERE document_id = d.id
            ORDER BY created_at DESC LIMIT 1
        ) ij ON TRUE
        WHERE d.deleted_at IS NULL
          AND det.id IS NULL
        ORDER BY d.original_filename
    """)
    missing = cur.fetchall()

    if not missing:
        print("All documents have extracted text")
        cur.close()
        conn.close()
        return 0

    print(f"Found {len(missing)} document(s) without extracted text:")
    for m in missing:
        print(f"  {m['original_filename']} (id={m['id']})")

    for m in missing:
        doc_id = m["id"]
        old_job_id = m["job_id"]

        if old_job_id:
            cur.execute(
                "UPDATE ingestion_jobs SET status = 'pending', stage = 'queued', "
                "retry_count = 0, error = NULL, started_at = NULL, finished_at = NULL, "
                "next_retry_at = NULL WHERE id = %s",
                (old_job_id,),
            )
        else:
            cur.execute(
                "INSERT INTO ingestion_jobs (document_id, status, stage, retry_count, max_retries) "
                "VALUES (%s, 'pending', 'queued', 0, 3)",
                (doc_id,),
            )

        cur.execute(
            "UPDATE documents SET status = 'queued' WHERE id = %s",
            (doc_id,),
        )
        print(f"  Queued {m['original_filename']} for re-processing")

    conn.commit()
    cur.close()
    conn.close()
    return len(missing)


if __name__ == "__main__":
    count = run_reprocess()
    print(f"\nQueued {count} document(s) for re-processing")
