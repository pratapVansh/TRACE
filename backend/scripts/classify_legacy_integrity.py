"""Read-only classification of legacy Aura and Supabase integrity findings."""

from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
import json
import logging
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from app.core.config import settings
from app.core.storage.supabase_storage import SupabaseStorageBackend


async def classify() -> dict:
    engine = create_async_engine(settings.get_database_url)
    try:
        async with engine.connect() as connection:
            documents = (await connection.execute(text(
                "SELECT id::text, original_filename, status, deleted_at "
                "FROM documents"
            ))).mappings().all()
            chunks = (await connection.execute(text(
                "SELECT id::text, document_id::text FROM document_chunks"
            ))).mappings().all()
            versions = (await connection.execute(text(
                "SELECT document_id::text, storage_uri FROM document_versions"
            ))).mappings().all()
    finally:
        await engine.dispose()

    docs = {row["id"]: dict(row) for row in documents}
    chunk_owner = {row["id"]: row["document_id"] for row in chunks}
    active_filename_owners: dict[str, set[str]] = defaultdict(set)
    for row in documents:
        if row["deleted_at"] is None:
            active_filename_owners[row["original_filename"]].add(row["id"])

    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    try:
        with driver.session(database=settings.neo4j_database) as session:
            nodes = [dict(row) for row in session.run(
                "MATCH (n:Entity) RETURN n.id AS id, n.name AS name, n.type AS type, "
                "n.document_id AS document_id, n.chunk_id AS chunk_id, "
                "n.source_document AS source_document, n.user_id AS user_id"
            )]
            relationships = [dict(row) for row in session.run(
                "MATCH (s:Entity)-[r]->(t:Entity) RETURN r.id AS id, type(r) AS type, "
                "r.document_id AS document_id, r.chunk_id AS chunk_id, "
                "r.source_document AS source_document, s.id AS source_id, "
                "s.name AS source_name, s.document_id AS source_document_id, "
                "s.user_id AS source_user_id, "
                "t.id AS target_id, t.name AS target_name, "
                "t.document_id AS target_document_id, t.user_id AS target_user_id"
            )]
    finally:
        driver.close()

    node_findings: list[dict] = []
    for node in nodes:
        doc_id = str(node.get("document_id") or "")
        doc = docs.get(doc_id)
        chunk_id = str(node.get("chunk_id") or "")
        evidence_candidates: set[str] = set()
        chunk_document_id = chunk_owner.get(chunk_id)
        if (
            chunk_document_id in docs
            and docs[chunk_document_id]["deleted_at"] is None
        ):
            evidence_candidates.add(chunk_document_id)
        evidence_candidates.update(
            active_filename_owners.get(str(node.get("source_document") or ""), set())
        )
        if doc and doc["deleted_at"] is None:
            evidence_candidates.add(doc_id)
        if len(evidence_candidates) == 1:
            intended_document_id = next(iter(evidence_candidates))
        else:
            intended_document_id = None

        if not doc_id and node.get("user_id"):
            classification = "valid/current"
            disposition = "requires preservation"
            reason = "user-memory entity is scoped by user_id rather than document_id"
        elif intended_document_id and (
            doc_id != intended_document_id
            or node.get("source_document")
            != docs[intended_document_id]["original_filename"]
        ):
            classification = "inconsistent provenance"
            disposition = "requires preservation"
            reason = "chunk/source filename identifies a current document but document provenance disagrees"
        elif doc is None:
            classification = "stale/orphan"
            disposition = "safe to remove"
            reason = "document_id is empty or absent from PostgreSQL"
        elif doc["deleted_at"] is not None:
            classification = "stale/orphan"
            disposition = "safe to remove"
            reason = "owning PostgreSQL document is soft-deleted"
        elif node.get("source_document") != doc["original_filename"]:
            classification = "inconsistent provenance"
            disposition = "requires preservation"
            reason = "active node source filename differs from PostgreSQL"
        else:
            classification = "valid/current"
            disposition = "requires preservation"
            reason = "active document and matching source filename"
        if classification != "valid/current":
            node_findings.append({
                **node,
                "intended_document_id": intended_document_id,
                "classification": classification,
                "disposition": disposition,
                "reason": reason,
            })

    relationship_findings: list[dict] = []
    for rel in relationships:
        doc_id = str(rel.get("document_id") or "")
        doc = docs.get(doc_id)
        endpoints = {
            str(rel.get("source_document_id") or ""),
            str(rel.get("target_document_id") or ""),
        }
        chunk_id = str(rel.get("chunk_id") or "")
        if (
            not doc_id
            and (rel.get("source_user_id") or rel.get("target_user_id"))
        ):
            classification = "valid/current"
            disposition = "requires preservation"
            reason = "user-memory relationship is not document-scoped"
        elif doc is None:
            classification = "stale/orphan"
            disposition = "safe to remove"
            reason = "document_id is empty or absent from PostgreSQL"
        elif doc["deleted_at"] is not None:
            classification = "stale/orphan"
            disposition = "safe to remove"
            reason = "owning PostgreSQL document is soft-deleted"
        elif chunk_id and chunk_owner.get(chunk_id) != doc_id:
            classification = "inconsistent provenance"
            disposition = "requires preservation"
            reason = "relationship chunk is missing or owned by another document"
        elif endpoints != {doc_id}:
            classification = "inconsistent provenance"
            disposition = "requires preservation"
            reason = "relationship endpoints are not scoped to its active document"
        elif rel.get("source_document") != doc["original_filename"]:
            classification = "inconsistent provenance"
            disposition = "requires preservation"
            reason = "relationship source filename differs from PostgreSQL"
        else:
            classification = "valid/current"
            disposition = "requires preservation"
            reason = "active document, chunk, endpoints, and filename agree"
        if classification != "valid/current":
            relationship_findings.append({**rel, "classification": classification,
                                          "disposition": disposition, "reason": reason})

    storage = SupabaseStorageBackend(
        url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
        bucket=settings.supabase_storage_bucket,
    )
    storage_findings: list[dict] = []
    for version in versions:
        doc_id = version["document_id"]
        doc = docs.get(doc_id)
        try:
            exists = await asyncio.to_thread(storage.exists, version["storage_uri"])
            error = None
        except Exception as exc:
            exists = None
            error = type(exc).__name__
        should_exist = bool(doc and doc["deleted_at"] is None)
        if not should_exist and error == "StoragePathError":
            # An invalid historical path cannot address a Supabase object, so
            # a deleted tombstone with that value has no storage orphan.
            continue
        if exists == should_exist:
            continue
        if not should_exist:
            classification = "stale/orphan"
            disposition = "safe to remove"
            reason = "soft-deleted/absent document still has a storage object"
        elif exists is False:
            classification = "stale/orphan"
            disposition = "requires preservation"
            reason = "active PostgreSQL row points to a missing object"
        else:
            classification = "inconsistent provenance"
            disposition = "requires preservation"
            reason = "storage URI is invalid or cannot be verified"
        storage_findings.append({
            **dict(version),
            "document_filename": doc["original_filename"] if doc else None,
            "document_status": doc["status"] if doc else None,
            "deleted": bool(doc and doc["deleted_at"] is not None),
            "exists": exists,
            "error": error,
            "classification": classification,
            "disposition": disposition,
            "reason": reason,
        })

    impacted_active_documents = sorted({
        str(item["document_id"])
        for item in node_findings + relationship_findings
        if item["classification"] == "inconsistent provenance"
    })
    by_document: dict[str, Counter] = defaultdict(Counter)
    for item in node_findings:
        by_document[str(item.get("document_id") or "<missing>")][
            f"node:{item['classification']}"
        ] += 1
    for item in relationship_findings:
        by_document[str(item.get("document_id") or "<missing>")][
            f"relationship:{item['classification']}"
        ] += 1

    return {
        "summary": {
            "neo4j_total_findings": len(node_findings) + len(relationship_findings),
            "neo4j_nodes": dict(Counter(x["classification"] for x in node_findings)),
            "neo4j_relationships": dict(Counter(
                x["classification"] for x in relationship_findings
            )),
            "supabase_findings": len(storage_findings),
            "active_documents_requiring_graph_preservation": impacted_active_documents,
        },
        "neo4j_by_document": {
            key: dict(value) for key, value in sorted(by_document.items())
        },
        "node_findings": node_findings,
        "relationship_findings": relationship_findings,
        "supabase_findings": storage_findings,
    }


if __name__ == "__main__":
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    report = asyncio.run(classify())
    output_path = Path(__file__).resolve().parents[1] / "audit_reports" / "legacy_integrity_classification.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, default=str))
    print(f"Full report: {output_path}")
