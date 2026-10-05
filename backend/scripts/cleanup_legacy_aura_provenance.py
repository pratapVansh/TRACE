"""Surgically migrate legacy global Aura entities to document-scoped records.

The command is a dry run unless ``--apply`` is supplied.  PostgreSQL and
Qdrant are read-only.  Before any Aura mutation, the complete Entity subgraph
is written to ``audit_reports`` for recovery and review.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

from app.core.config import settings  # noqa: E402
from app.core.storage.supabase_storage import SupabaseStorageBackend  # noqa: E402
from app.extraction.entity import _entity_id  # noqa: E402
from app.extraction.relationship import RelationshipType  # noqa: E402
from app.extraction.types import EntityType  # noqa: E402


FAILTEST_DOCUMENT_ID = "162779ac-346a-4681-87df-199d63e93d3e"
FAILTEST_OBJECT_KEY = (
    "documents/162779ac-346a-4681-87df-199d63e93d3e/"
    "v1/FAILTEST-143234.txt"
)
FAILTEST_CONTENT = (
    b"Failure-path exercise document FAILTEST-143234.\n"
    b"Equipment: FAIL-143234 -- Instrument Air Dryer.\n"
    b"This document is uploaded, indexed, then its stored object is removed so the\n"
    b"background worker hits a real StorageNotFoundError on reprocessing.\n"
)
FAILTEST_SHA256 = "032f10221ced215bb27401413a90f68815899dd06b6a2127676e6b10a0ae1415"


def _jsonable(value):
    return json.loads(json.dumps(value, default=str))


def _legacy_entity_id(name: str, type_value: str) -> str:
    raw = f"{type_value}:{name.lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


async def _postgres_snapshot() -> tuple[dict[str, dict], dict[str, dict], dict[str, list[dict]]]:
    engine = create_async_engine(settings.get_database_url)
    try:
        async with engine.connect() as connection:
            documents = (await connection.execute(text(
                "SELECT id::text, original_filename, status, deleted_at "
                "FROM documents"
            ))).mappings().all()
            chunks = (await connection.execute(text(
                "SELECT id::text, document_id::text, chunk_index, content "
                "FROM document_chunks ORDER BY document_id, chunk_index"
            ))).mappings().all()
            failtest = (await connection.execute(text(
                "SELECT checksum_sha256, "
                "file_size_bytes FROM document_versions "
                "WHERE document_id = CAST(:document_id AS uuid)"
            ), {"document_id": FAILTEST_DOCUMENT_ID})).mappings().one()
    finally:
        await engine.dispose()

    if failtest["checksum_sha256"] != FAILTEST_SHA256:
        raise RuntimeError("FAILTEST recovery bytes do not match PostgreSQL checksum")
    if int(failtest["file_size_bytes"]) != len(FAILTEST_CONTENT):
        raise RuntimeError("FAILTEST recovery bytes do not match PostgreSQL file size")

    docs = {row["id"]: dict(row) for row in documents}
    chunk_map = {row["id"]: dict(row) for row in chunks}
    chunks_by_document: dict[str, list[dict]] = defaultdict(list)
    for row in chunks:
        chunks_by_document[row["document_id"]].append(dict(row))
    return docs, chunk_map, chunks_by_document


def _choose_chunk(
    document_id: str,
    name: str,
    original_chunk_id: str,
    chunk_map: dict[str, dict],
    chunks_by_document: dict[str, list[dict]],
) -> str:
    original = chunk_map.get(original_chunk_id)
    if original and original["document_id"] == document_id:
        return original_chunk_id
    lowered = name.lower()
    for chunk in chunks_by_document.get(document_id, []):
        if lowered and lowered in str(chunk["content"]).lower():
            return chunk["id"]
    candidates = chunks_by_document.get(document_id, [])
    if not candidates:
        raise RuntimeError(f"Cannot preserve graph fact: document {document_id} has no chunks")
    return candidates[0]["id"]


def _snapshot_graph(session) -> tuple[list[dict], list[dict]]:
    nodes = [dict(row) for row in session.run(
        "MATCH (n:Entity) RETURN elementId(n) AS element_id, properties(n) AS properties"
    )]
    relationships = [dict(row) for row in session.run(
        "MATCH (s:Entity)-[r]->(t:Entity) "
        "RETURN elementId(r) AS element_id, type(r) AS type, "
        "elementId(s) AS source_element_id, elementId(t) AS target_element_id, "
        "properties(s) AS source_properties, properties(t) AS target_properties, "
        "properties(r) AS properties"
    )]
    return nodes, relationships


def _active(documents: dict[str, dict], document_id: str) -> bool:
    return document_id in documents and documents[document_id]["deleted_at"] is None


def _build_plan(documents, chunk_map, chunks_by_document, nodes, relationships) -> dict:
    filename_owners: dict[str, set[str]] = defaultdict(set)
    for document_id, document in documents.items():
        if document["deleted_at"] is None:
            filename_owners[document["original_filename"]].add(document_id)

    node_by_element = {row["element_id"]: row for row in nodes}
    relationship_documents_by_node: dict[str, set[str]] = defaultdict(set)
    for relationship in relationships:
        document_id = str(relationship["properties"].get("document_id") or "")
        if _active(documents, document_id):
            relationship_documents_by_node[relationship["source_element_id"]].add(document_id)
            relationship_documents_by_node[relationship["target_element_id"]].add(document_id)

    replacements: dict[tuple[str, str], dict] = {}
    legacy_node_elements: list[str] = []
    true_orphan_elements: list[str] = []
    valid_current_legacy = 0
    provenance_finding_nodes = 0

    for node in nodes:
        props = dict(node["properties"])
        name = str(props.get("name") or "")
        type_value = str(props.get("type") or "")
        try:
            entity_type = EntityType(type_value)
        except ValueError as exc:
            raise RuntimeError(f"Unknown entity type {type_value!r} on node {props.get('id')}") from exc

        is_legacy = props.get("id") == _legacy_entity_id(name, entity_type.value)
        if not is_legacy:
            continue
        legacy_node_elements.append(node["element_id"])

        targets: set[str] = set(relationship_documents_by_node[node["element_id"]])
        current_document_id = str(props.get("document_id") or "")
        if _active(documents, current_document_id):
            targets.add(current_document_id)
        chunk = chunk_map.get(str(props.get("chunk_id") or ""))
        if chunk and _active(documents, chunk["document_id"]):
            targets.add(chunk["document_id"])
        targets.update(filename_owners.get(str(props.get("source_document") or ""), set()))

        expected_filename = (
            documents[current_document_id]["original_filename"]
            if _active(documents, current_document_id) else None
        )
        if not targets:
            true_orphan_elements.append(node["element_id"])
        elif expected_filename == props.get("source_document"):
            valid_current_legacy += 1
        else:
            provenance_finding_nodes += 1

        for target_document_id in targets:
            replacement_id = _entity_id(name, entity_type, target_document_id)
            replacement_props = dict(props)
            replacement_props.update({
                "id": replacement_id,
                "document_id": target_document_id,
                "source_document": documents[target_document_id]["original_filename"],
                "chunk_id": _choose_chunk(
                    target_document_id,
                    name,
                    str(props.get("chunk_id") or ""),
                    chunk_map,
                    chunks_by_document,
                ),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            replacements[(replacement_id, target_document_id)] = replacement_props

    relationship_replacements_by_key: dict[tuple[str, str, str, str], dict] = {}
    unsupported_relationships: list[str] = []
    for relationship in relationships:
        props = dict(relationship["properties"])
        document_id = str(props.get("document_id") or "")
        if not _active(documents, document_id):
            raise RuntimeError(
                f"Relationship {relationship['element_id']} has no active owner and cannot be preserved"
            )
        try:
            relationship_type = RelationshipType(relationship["type"]).value
        except ValueError:
            unsupported_relationships.append(relationship["element_id"])
            continue

        source_props = dict(relationship["source_properties"])
        target_props = dict(relationship["target_properties"])
        source_type = EntityType(str(source_props["type"]))
        target_type = EntityType(str(target_props["type"]))
        source_id = _entity_id(str(source_props["name"]), source_type, document_id)
        target_id = _entity_id(str(target_props["name"]), target_type, document_id)
        valid_chunk_id = _choose_chunk(
            document_id,
            f"{source_props['name']} {target_props['name']}",
            str(props.get("chunk_id") or ""),
            chunk_map,
            chunks_by_document,
        )
        corrected_props = dict(props)
        corrected_props.update({
            "document_id": document_id,
            "source_document": documents[document_id]["original_filename"],
            "chunk_id": valid_chunk_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        replacement = {
            "legacy_element_id": relationship["element_id"],
            "type": relationship_type,
            "source_id": source_id,
            "target_id": target_id,
            "document_id": document_id,
            "properties": corrected_props,
        }
        relationship_replacements_by_key[(
            relationship_type,
            source_id,
            target_id,
            str(corrected_props.get("id") or ""),
        )] = replacement

        for endpoint_props, replacement_id in (
            (source_props, source_id), (target_props, target_id)
        ):
            endpoint_copy = dict(endpoint_props)
            endpoint_copy.update({
                "id": replacement_id,
                "document_id": document_id,
                "source_document": documents[document_id]["original_filename"],
                "chunk_id": _choose_chunk(
                    document_id,
                    str(endpoint_props["name"]),
                    str(endpoint_props.get("chunk_id") or ""),
                    chunk_map,
                    chunks_by_document,
                ),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            replacements[(replacement_id, document_id)] = endpoint_copy

    if unsupported_relationships:
        raise RuntimeError(f"Unsupported relationship types: {unsupported_relationships}")

    relationship_replacements = list(relationship_replacements_by_key.values())
    return {
        "replacement_nodes": list(replacements.values()),
        "replacement_relationships": relationship_replacements,
        "legacy_node_elements": legacy_node_elements,
        "legacy_relationship_elements": [row["element_id"] for row in relationships],
        "true_orphan_elements": true_orphan_elements,
        "counts": {
            "original_nodes": len(nodes),
            "original_relationships": len(relationships),
            "legacy_global_nodes": len(legacy_node_elements),
            "valid_current_legacy_nodes": valid_current_legacy,
            "provenance_finding_nodes": provenance_finding_nodes,
            "true_orphan_nodes": len(true_orphan_elements),
            "replacement_nodes": len(replacements),
            "replacement_relationships": len(relationship_replacements),
            "collapsed_duplicate_relationships": (
                len(relationships) - len(relationship_replacements)
            ),
        },
    }


def _apply_graph_plan(session, plan: dict) -> None:
    with session.begin_transaction() as tx:
        tx.run(
            "UNWIND $rows AS row MERGE (n:Entity {id: row.id}) "
            "ON CREATE SET n = row",
            rows=plan["replacement_nodes"],
        ).consume()

        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in plan["replacement_relationships"]:
            grouped[row["type"]].append(row)
        for relationship_type, rows in grouped.items():
            tx.run(
                f"UNWIND $rows AS row MATCH (s:Entity {{id: row.source_id}}) "
                f"MATCH (t:Entity {{id: row.target_id}}) "
                f"MERGE (s)-[r:{relationship_type} {{id: row.properties.id}}]->(t) "
                "ON CREATE SET r = row.properties",
                rows=rows,
            ).consume()

        node_check = tx.run(
            "UNWIND $rows AS row OPTIONAL MATCH (n:Entity {id: row.id}) "
            "WHERE n.document_id = row.document_id "
            "RETURN count(n) AS total",
            rows=plan["replacement_nodes"],
        ).single()["total"]
        if int(node_check) != len(plan["replacement_nodes"]):
            raise RuntimeError("Not all replacement nodes verified; transaction rolled back")

        for relationship_type, rows in grouped.items():
            verified = tx.run(
                f"UNWIND $rows AS row MATCH (s:Entity {{id: row.source_id}})"
                f"-[r:{relationship_type} {{id: row.properties.id}}]->"
                f"(t:Entity {{id: row.target_id}}) "
                "WHERE r.document_id = row.document_id RETURN count(r) AS total",
                rows=rows,
            ).single()["total"]
            if int(verified) != len(rows):
                raise RuntimeError(
                    f"Not all {relationship_type} replacements verified; transaction rolled back"
                )

        deleted_relationships = tx.run(
            "UNWIND $element_ids AS element_id MATCH ()-[r]->() "
            "WHERE elementId(r) = element_id DELETE r RETURN count(r) AS total",
            element_ids=plan["legacy_relationship_elements"],
        ).single()["total"]
        if int(deleted_relationships) != len(plan["legacy_relationship_elements"]):
            raise RuntimeError("Legacy relationship deletion mismatch; transaction rolled back")

        deleted_nodes = tx.run(
            "UNWIND $element_ids AS element_id MATCH (n:Entity) "
            "WHERE elementId(n) = element_id AND NOT (n)--() "
            "DELETE n RETURN count(n) AS total",
            element_ids=plan["legacy_node_elements"],
        ).single()["total"]
        if int(deleted_nodes) != len(plan["legacy_node_elements"]):
            raise RuntimeError("Legacy node deletion mismatch; transaction rolled back")

        tx.commit()


def _restore_failtest_storage() -> dict:
    if hashlib.sha256(FAILTEST_CONTENT).hexdigest() != FAILTEST_SHA256:
        raise RuntimeError("Embedded FAILTEST bytes failed checksum validation")
    storage = SupabaseStorageBackend(
        url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
        bucket=settings.supabase_storage_bucket,
    )
    key = storage.save(FAILTEST_OBJECT_KEY, FAILTEST_CONTENT)
    stored = storage.read(key)
    return {
        "key": key,
        "bytes": len(stored),
        "sha256": hashlib.sha256(stored).hexdigest(),
    }


async def run(apply: bool) -> dict:
    documents, chunk_map, chunks_by_document = await _postgres_snapshot()
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    try:
        with driver.session(database=settings.neo4j_database) as session:
            nodes, relationships = _snapshot_graph(session)
            plan = _build_plan(
                documents, chunk_map, chunks_by_document, nodes, relationships
            )
            result = {"mode": "apply" if apply else "dry-run", "plan": plan["counts"]}
            if not apply:
                return result

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_path = (
                Path(__file__).resolve().parents[1]
                / "audit_reports"
                / f"aura_legacy_backup_{timestamp}.json"
            )
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(
                json.dumps({"nodes": _jsonable(nodes), "relationships": _jsonable(relationships)}, indent=2),
                encoding="utf-8",
            )
            _apply_graph_plan(session, plan)
            result["aura_backup"] = str(backup_path)
            result["supabase_restored"] = await asyncio.to_thread(_restore_failtest_storage)
            return result
    finally:
        driver.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    logging.getLogger("httpx").setLevel(logging.WARNING)
    print(json.dumps(asyncio.run(run(args.apply)), indent=2))
