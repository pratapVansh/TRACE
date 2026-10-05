"""Read-only inventory of active PostgreSQL documents and local source blobs.

This command never creates directories, mutates rows, or writes objects. Run it
from ``backend`` before planning a storage migration::

    python scripts/storage_inventory.py
    python scripts/storage_inventory.py --json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


@dataclass(slots=True)
class InventoryReport:
    active_document_rows: int = 0
    source_objects_found: int = 0
    valid_source_objects: int = 0
    missing_source_objects: int = 0
    total_bytes: int = 0
    checksum_mismatches: int = 0
    size_mismatches: int = 0
    missing: list[dict[str, str]] = field(default_factory=list)
    checksum_mismatch_details: list[dict[str, str]] = field(default_factory=list)
    size_mismatch_details: list[dict[str, str | int]] = field(default_factory=list)


def _safe_source_path(root: Path, storage_uri: str) -> Path:
    relative = Path(storage_uri.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("unsafe storage URI")
    source = (root / relative).resolve()
    source.relative_to(root)
    return source


def inspect_rows(rows, storage_root: Path) -> InventoryReport:
    """Build an inventory from database rows without modifying either store."""
    root = storage_root.resolve()
    report = InventoryReport(active_document_rows=len(rows))

    for row in rows:
        values = row._mapping if hasattr(row, "_mapping") else row
        document_id = str(values["document_id"])
        filename = str(values["original_filename"])
        storage_uri = values.get("storage_uri")
        if not storage_uri:
            report.missing_source_objects += 1
            report.missing.append(
                {"document_id": document_id, "filename": filename, "reason": "no latest version"}
            )
            continue

        try:
            source = _safe_source_path(root, str(storage_uri))
        except ValueError:
            report.missing_source_objects += 1
            report.missing.append(
                {"document_id": document_id, "filename": filename, "reason": "unsafe storage URI"}
            )
            continue

        if not source.is_file():
            report.missing_source_objects += 1
            report.missing.append(
                {"document_id": document_id, "filename": filename, "reason": "file not found"}
            )
            continue

        report.source_objects_found += 1
        content = source.read_bytes()
        actual_size = len(content)
        report.total_bytes += actual_size
        size_matches = actual_size == int(values["file_size_bytes"])
        checksum_matches = (
            hashlib.sha256(content).hexdigest().lower()
            == str(values["checksum_sha256"]).lower()
        )

        if not size_matches:
            report.size_mismatches += 1
            report.size_mismatch_details.append(
                {
                    "document_id": document_id,
                    "filename": filename,
                    "expected": int(values["file_size_bytes"]),
                    "actual": actual_size,
                }
            )
        if not checksum_matches:
            report.checksum_mismatches += 1
            report.checksum_mismatch_details.append(
                {"document_id": document_id, "filename": filename}
            )
        if size_matches and checksum_matches:
            report.valid_source_objects += 1

    return report


async def collect_inventory() -> InventoryReport:
    engine = create_async_engine(settings.get_database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.execute(text("SET TRANSACTION READ ONLY"))
                result = await connection.execute(text("""
                    SELECT d.id AS document_id,
                           d.original_filename,
                           dv.storage_uri,
                           dv.file_size_bytes,
                           dv.checksum_sha256
                    FROM documents AS d
                    LEFT JOIN document_versions AS dv
                      ON dv.document_id = d.id AND dv.is_latest = true
                    WHERE d.deleted_at IS NULL
                    ORDER BY d.id
                """))
                rows = result.fetchall()
        return inspect_rows(rows, settings.storage_root_path)
    finally:
        await engine.dispose()


def _print_human(report: InventoryReport) -> None:
    print("Storage migration inventory (read-only)")
    print(f"Active document rows: {report.active_document_rows}")
    print(f"Source objects found: {report.source_objects_found}")
    print(f"Valid source objects: {report.valid_source_objects}")
    print(f"Missing source objects: {report.missing_source_objects}")
    print(f"Total bytes: {report.total_bytes}")
    print(f"Checksum mismatches: {report.checksum_mismatches}")
    print(f"Size mismatches: {report.size_mismatches}")
    for item in report.missing:
        print(
            "MISSING "
            f"document_id={item['document_id']} filename={item['filename']} "
            f"reason={item['reason']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args()
    report = asyncio.run(collect_inventory())
    if args.json:
        print(json.dumps(asdict(report), indent=2, sort_keys=True))
    else:
        _print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
