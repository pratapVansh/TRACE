"""Remove junk/test document records from the database."""

import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "trace",
    "password": "trace",
    "dbname": "trace",
}

JUNK_FILENAMES = [
    "TRACE - Complete Implementation Milestones.pdf",
    "notes.txt",
    "test.txt",
    "test_upload.txt",
    "verify_test.txt",
    "storage-check.txt",
    "audit-test.txt",
    "image_0.jpg",
]

JUNK_TITLE_PATTERNS = [
    "TRACE",
    "notes",
    "test",
    "storage-check",
    "audit",
    "verify",
    "image_0",
]


def run_cleanup(dry_run: bool = True) -> dict:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    placeholders = ",".join("%s" for _ in JUNK_FILENAMES)
    cur.execute(
        f"""
        SELECT id, original_filename, title, status
        FROM documents
        WHERE original_filename IN ({placeholders})
           OR title ILIKE '%%test%%'
           OR title ILIKE '%%notes%%'
           OR title ILIKE '%%verify%%'
           OR title ILIKE '%%storage%%'
           OR title ILIKE '%%audit%%'
           OR title ILIKE 'image_0%%'
        ORDER BY created_at
        """,
        JUNK_FILENAMES,
    )
    junk = cur.fetchall()

    if not junk:
        print("No junk records found")
        cur.close()
        conn.close()
        return {"total": 0, "junk_ids": [], "deleted_storage": []}

    print(f"Found {len(junk)} junk document(s):")
    for j in junk:
        print(f"  ID={j[0]}  File={j[1]}  Title={j[2]}  Status={j[3]}")

    junk_ids = [str(j[0]) for j in junk]

    if not dry_run:
        for j in junk:
            doc_id = j[0]
            cur.execute(
                "UPDATE documents SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL",
                (doc_id,),
            )
        conn.commit()
        print(f"\nSoft-deleted {len(junk)} junk document(s)")
    else:
        print(f"\nDRY RUN - would delete {len(junk)} document(s)")
        print("Run with --execute to actually delete")

    cur.close()
    conn.close()

    return {
        "total": len(junk),
        "junk_ids": junk_ids,
    }


if __name__ == "__main__":
    import sys

    dry_run = "--execute" not in sys.argv
    if dry_run:
        print("=== DRY RUN MODE ===")
    result = run_cleanup(dry_run=dry_run)
    print(f"\nCleanup result: {result['total']} documents identified")
