from __future__ import annotations

import hashlib

from scripts.storage_inventory import inspect_rows


def _row(**values):
    return values


def test_inventory_reports_found_missing_bytes_and_checksum_mismatch(tmp_path) -> None:
    valid = b"valid-content"
    mismatched = b"changed-content"
    valid_path = tmp_path / "documents" / "one" / "v1" / "valid.txt"
    mismatch_path = tmp_path / "documents" / "two" / "v1" / "changed.txt"
    valid_path.parent.mkdir(parents=True)
    mismatch_path.parent.mkdir(parents=True)
    valid_path.write_bytes(valid)
    mismatch_path.write_bytes(mismatched)

    rows = [
        _row(
            document_id="one",
            original_filename="valid.txt",
            storage_uri="documents/one/v1/valid.txt",
            file_size_bytes=len(valid),
            checksum_sha256=hashlib.sha256(valid).hexdigest(),
        ),
        _row(
            document_id="two",
            original_filename="changed.txt",
            storage_uri="documents/two/v1/changed.txt",
            file_size_bytes=len(mismatched),
            checksum_sha256="0" * 64,
        ),
        _row(
            document_id="three",
            original_filename="missing.txt",
            storage_uri="documents/three/v1/missing.txt",
            file_size_bytes=10,
            checksum_sha256="0" * 64,
        ),
    ]

    report = inspect_rows(rows, tmp_path)

    assert report.active_document_rows == 3
    assert report.source_objects_found == 2
    assert report.valid_source_objects == 1
    assert report.missing_source_objects == 1
    assert report.total_bytes == len(valid) + len(mismatched)
    assert report.checksum_mismatches == 1
    assert report.size_mismatches == 0


def test_inventory_treats_unsafe_uri_as_missing_without_reading_outside_root(tmp_path) -> None:
    report = inspect_rows(
        [
            _row(
                document_id="unsafe",
                original_filename="secret.txt",
                storage_uri="../secret.txt",
                file_size_bytes=1,
                checksum_sha256="0" * 64,
            )
        ],
        tmp_path,
    )

    assert report.missing_source_objects == 1
    assert report.source_objects_found == 0
    assert report.missing[0]["reason"] == "unsafe storage URI"
