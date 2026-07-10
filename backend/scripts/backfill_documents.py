"""Backfill business metadata for all existing indexed documents."""

import asyncio
import sys

import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, ".")

from app.services.document_classifier import classify_document

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "trace",
    "password": "trace",
    "dbname": "trace",
}


def run_backfill() -> int:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    updated = 0

    cur.execute("""
        SELECT d.id, d.original_filename, det.full_text
        FROM documents d
        JOIN document_versions dv ON dv.document_id = d.id AND dv.is_latest = TRUE
        LEFT JOIN document_extracted_text det ON det.document_version_id = dv.id
        WHERE d.deleted_at IS NULL
          AND d.status IN ('indexed', 'queued', 'processing', 'review')
        ORDER BY d.original_filename
    """)
    documents = cur.fetchall()

    print(f"Found {len(documents)} documents to process")

    for doc in documents:
        doc_id = doc["id"]
        filename = doc["original_filename"]
        text = doc["full_text"] or ""

        classification = classify_document(filename=filename, content_text=text)

        cur.execute(
            """
            UPDATE documents
            SET department = %s,
                document_category = %s,
                equipment_ids = %s
            WHERE id = %s
            """,
            (
                classification.department,
                classification.category,
                classification.equipment_ids,
                doc_id,
            ),
        )
        updated += 1
        print(
            f"  {filename:50s} -> dept={classification.department:20s}"
            f" cat={classification.category:20s} equip={classification.equipment_ids}"
        )

    conn.commit()
    cur.close()
    conn.close()
    return updated


if __name__ == "__main__":
    count = run_backfill()
    print(f"\nBackfill complete: {count} documents updated")
