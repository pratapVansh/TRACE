"""Read-only cross-store integrity audit for TRACE's production RAG data."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(ROOT / ".env")

from app.core.config import settings  # noqa: E402
from app.core.storage.supabase_storage import SupabaseStorageBackend  # noqa: E402
from app.core.storage.exceptions import StoragePathError  # noqa: E402
from app.services.vector_store import VECTOR_DIMENSION  # noqa: E402


async def _postgres_snapshot() -> dict:
    # The running Compose backend intentionally gets PostgreSQL from
    # .env.docker while cloud services come from the root .env. A developer
    # may also have a native PostgreSQL on localhost: comparing that unrelated
    # database to the live cloud indexes produces a completely false orphan
    # report. Require execution inside the backend container, where the
    # service hostname resolves directly and cannot collide with a host daemon.
    if (
        not Path("/.dockerenv").exists()
        and os.getenv("TRACE_ALLOW_HOST_INTEGRITY_AUDIT") != "1"
    ):
        raise RuntimeError(
            "Run this audit inside the backend container so PostgreSQL is "
            "unambiguously the active service, or explicitly set "
            "TRACE_ALLOW_HOST_INTEGRITY_AUDIT=1 after verifying DATABASE_URL"
        )
    engine = create_async_engine(settings.get_database_url)
    try:
        async with engine.connect() as connection:
            documents = (
                await connection.execute(
                    text(
                        "SELECT id::text, original_filename, doc_type, status, "
                        "deleted_at FROM documents"
                    )
                )
            ).mappings().all()
            versions = (
                await connection.execute(
                    text(
                        "SELECT dv.document_id::text, dv.storage_uri, "
                        "dv.checksum_sha256, dv.file_size_bytes "
                        "FROM document_versions dv"
                    )
                )
            ).mappings().all()
            chunks = (
                await connection.execute(
                    text(
                        "SELECT id::text, document_id::text, chunk_index, "
                        "page_number, content, metadata, embedding_status, "
                        "CASE WHEN embedding IS NULL THEN NULL "
                        "ELSE jsonb_array_length(embedding) END AS dimension "
                        "FROM document_chunks"
                    )
                )
            ).mappings().all()
    finally:
        await engine.dispose()
    return {
        "documents": [dict(row) for row in documents],
        "versions": [dict(row) for row in versions],
        "chunks": [dict(row) for row in chunks],
    }


def _qdrant_snapshot() -> tuple[dict, list[dict]]:
    client = QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ["QDRANT_API_KEY"],
        timeout=30,
    )
    collection = settings.qdrant_collection_name
    info = client.get_collection(collection)
    points: list[dict] = []
    offset = None
    while True:
        batch, offset = client.scroll(
            collection_name=collection,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        points.extend(
            {"id": str(point.id), "payload": point.payload or {}}
            for point in batch
        )
        if offset is None:
            break
    vector_params = info.config.params.vectors
    size = getattr(vector_params, "size", None)
    distance = str(getattr(vector_params, "distance", ""))
    return {"size": size, "distance": distance}, points


def _neo4j_snapshot() -> tuple[list[dict], list[dict]]:
    # CI's PostgreSQL is disposable while Aura is shared. Audit the run-owned
    # graph only; the production path retains the existing full graph audit.
    ci_run_id = os.getenv("TRACE_CI_RUN_ID") if os.getenv("GITHUB_ACTIONS") == "true" else None
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )
    try:
        with driver.session(database=os.environ.get("NEO4J_DATABASE", "neo4j")) as session:
            nodes = [
                dict(record)
                for record in session.run(
                    "MATCH (n:Entity) "
                    "WHERE $ci_run_id IS NULL OR n.trace_ci_run_id = $ci_run_id "
                    "RETURN n.id AS id, n.document_id AS document_id, "
                    "n.name AS name, n.type AS type, n.user_id AS user_id, "
                    "n.source_document AS source_document",
                    ci_run_id=ci_run_id,
                )
            ]
            relationships = [
                dict(record)
                for record in session.run(
                    "MATCH (s:Entity)-[r]->(t:Entity) "
                    "WHERE $ci_run_id IS NULL OR r.trace_ci_run_id = $ci_run_id "
                    "RETURN r.id AS id, r.document_id AS document_id, "
                    "r.chunk_id AS chunk_id, r.source_document AS source_document, "
                    "s.document_id AS source_document_id, "
                    "t.document_id AS target_document_id",
                    ci_run_id=ci_run_id,
                )
            ]
    finally:
        driver.close()
    return nodes, relationships


def _storage_backend() -> SupabaseStorageBackend:
    return SupabaseStorageBackend(
        url=os.environ["SUPABASE_URL"],
        service_role_key=os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        bucket=os.getenv("SUPABASE_STORAGE_BUCKET", "trace"),
        timeout_seconds=float(os.getenv("SUPABASE_STORAGE_TIMEOUT_SECONDS", "30")),
        max_retries=int(os.getenv("SUPABASE_STORAGE_MAX_RETRIES", "3")),
    )


async def audit() -> dict:
    postgres = await _postgres_snapshot()
    qdrant_info, points = await asyncio.to_thread(_qdrant_snapshot)
    graph_nodes, graph_relationships = await asyncio.to_thread(_neo4j_snapshot)
    storage = _storage_backend()

    documents = {row["id"]: row for row in postgres["documents"]}
    active_ids = {doc_id for doc_id, row in documents.items() if row["deleted_at"] is None}
    deleted_ids = set(documents) - active_ids
    chunks = {row["id"]: row for row in postgres["chunks"]}
    chunks_by_document: dict[str, set[str]] = defaultdict(set)
    for chunk_id, row in chunks.items():
        if row["embedding_status"] == "completed":
            chunks_by_document[row["document_id"]].add(chunk_id)

    issues: list[str] = []
    if qdrant_info["size"] != VECTOR_DIMENSION:
        issues.append(
            f"Qdrant dimension is {qdrant_info['size']}, expected {VECTOR_DIMENSION}"
        )
    if "COSINE" not in qdrant_info["distance"].upper():
        issues.append(
            f"Qdrant distance is {qdrant_info['distance']}, expected cosine"
        )

    pg_dimensions = Counter(
        row["dimension"] for row in chunks.values() if row["dimension"] is not None
    )
    if any(dimension != VECTOR_DIMENSION for dimension in pg_dimensions):
        issues.append(f"PostgreSQL embedding dimensions differ: {dict(pg_dimensions)}")

    qdrant_by_document: dict[str, set[str]] = defaultdict(set)
    payload_chunk_ids: list[str] = []
    for point in points:
        payload = point["payload"]
        document_id = str(payload.get("document_id") or "")
        chunk_id = str(payload.get("chunk_id") or "")
        payload_chunk_ids.append(chunk_id)
        qdrant_by_document[document_id].add(chunk_id)
        if document_id not in active_ids:
            issues.append(f"orphan Qdrant point {point['id']} document={document_id}")
            continue
        chunk = chunks.get(chunk_id)
        if chunk is None:
            issues.append(f"Qdrant point {point['id']} references missing chunk {chunk_id}")
            continue
        document = documents[document_id]
        expected = {
            "document_id": document_id,
            "chunk_id": chunk_id,
            "filename": document["original_filename"],
            "document_type": document["doc_type"],
            "chunk_index": chunk["chunk_index"],
            "content": chunk["content"],
        }
        for key, value in expected.items():
            if payload.get(key) != value:
                issues.append(
                    f"Qdrant metadata mismatch point={point['id']} field={key}"
                )
        if str(point["id"]) != chunk_id:
            issues.append(f"Qdrant point id does not equal chunk id: {point['id']}")

    duplicate_payloads = [
        chunk_id for chunk_id, count in Counter(payload_chunk_ids).items()
        if chunk_id and count > 1
    ]
    if duplicate_payloads:
        issues.append(f"duplicate Qdrant chunk payloads: {duplicate_payloads}")

    for document_id in active_ids:
        document = documents[document_id]
        if document["status"] not in {"indexed", "review"}:
            continue
        expected_ids = chunks_by_document.get(document_id, set())
        actual_ids = qdrant_by_document.get(document_id, set())
        if expected_ids != actual_ids:
            issues.append(
                f"vector/chunk mismatch document={document_id} "
                f"postgres={len(expected_ids)} qdrant={len(actual_ids)}"
            )

    duplicate_chunk_slots = Counter(
        (row["document_id"], row["chunk_index"]) for row in chunks.values()
    )
    if any(count > 1 for count in duplicate_chunk_slots.values()):
        issues.append("duplicate PostgreSQL chunk indexes exist")

    for version in postgres["versions"]:
        should_exist = version["document_id"] in active_ids
        try:
            exists = await asyncio.to_thread(storage.exists, version["storage_uri"])
        except StoragePathError:
            # Historical soft-delete tombstones can predate object-key
            # normalization and contain an absolute/local path. Such a value
            # cannot name a Supabase object, so there is no external orphan to
            # remove. It remains an error for any active document.
            if not should_exist:
                continue
            issues.append(
                f"invalid/unverifiable storage URI for document="
                f"{version['document_id']}: {version['storage_uri']} (StoragePathError)"
            )
            continue
        except Exception as exc:
            issues.append(
                f"invalid/unverifiable storage URI for document="
                f"{version['document_id']}: {version['storage_uri']} ({type(exc).__name__})"
            )
            continue
        if exists != should_exist:
            state = "missing active" if should_exist else "orphan deleted"
            issues.append(f"{state} Supabase object {version['storage_uri']}")

    for node in graph_nodes:
        document_id = str(node.get("document_id") or "")
        if not document_id and node.get("user_id"):
            # User-memory graph entities deliberately share the Entity label
            # but are scoped by user_id, not document_id.
            continue
        if document_id not in active_ids:
            issues.append(f"orphan Neo4j node {node.get('id')} document={document_id}")
            continue
        expected_filename = documents[document_id]["original_filename"]
        if node.get("source_document") != expected_filename:
            issues.append(
                f"Neo4j node provenance mismatch id={node.get('id')} document={document_id}"
            )

    for relationship in graph_relationships:
        document_id = str(relationship.get("document_id") or "")
        if document_id not in active_ids:
            issues.append(
                f"orphan Neo4j relationship {relationship.get('id')} document={document_id}"
            )
            continue
        endpoints = {
            str(relationship.get("source_document_id") or ""),
            str(relationship.get("target_document_id") or ""),
        }
        if endpoints != {document_id}:
            issues.append(
                f"cross-document Neo4j relationship {relationship.get('id')} "
                f"document={document_id} endpoints={sorted(endpoints)}"
            )
        chunk_id = str(relationship.get("chunk_id") or "")
        if chunk_id and (
            chunk_id not in chunks
            or chunks[chunk_id]["document_id"] != document_id
        ):
            issues.append(
                f"Neo4j relationship chunk provenance mismatch "
                f"id={relationship.get('id')} document={document_id}"
            )
        expected_filename = documents[document_id]["original_filename"]
        if relationship.get("source_document") != expected_filename:
            issues.append(
                f"Neo4j relationship source provenance mismatch "
                f"id={relationship.get('id')} document={document_id}"
            )

    return {
        "counts": {
            "postgres_documents": len(documents),
            "postgres_active_documents": len(active_ids),
            "postgres_soft_deleted_documents": len(deleted_ids),
            "postgres_chunks": len(chunks),
            "qdrant_points": len(points),
            "neo4j_nodes": len(graph_nodes),
            "neo4j_relationships": len(graph_relationships),
            "supabase_versions_checked": len(postgres["versions"]),
        },
        "embedding": {
            "model": settings.embedding_model_name,
            "expected_dimension": VECTOR_DIMENSION,
            "qdrant_dimension": qdrant_info["size"],
            "qdrant_distance": qdrant_info["distance"],
            "postgres_dimensions": dict(pg_dimensions),
        },
        "issue_count": len(issues),
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fail-on-issues", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(audit())
    print(json.dumps(result, indent=2, default=str))
    if args.fail_on_issues and result["issue_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
