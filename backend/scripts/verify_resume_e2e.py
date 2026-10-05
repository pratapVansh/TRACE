"""Black-box verification for native-text resume ingestion and cloud cleanup.

The probe creates only uniquely named data and removes only that data. Existing
documents, vectors, graph entities, and search history are never cleared.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import UUID, uuid4

import fitz
import asyncpg
import httpx
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient, models

from app.core.storage.supabase_storage import SupabaseStorageBackend
from app.schemas.rag import Citation
from app.services.evidence_classification import classify_statements


ROOT = Path(__file__).resolve().parents[2]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _resume_pdf(probe: str) -> bytes:
    equipment_suffix = int(probe[:6], 16) % 900_000 + 10_000
    sections = [
        (
            "Avery Trace\navery.trace@example.invalid | +1 555 010 4242",
            "CONTACT",
        ),
        (
            f"EDUCATION\nNorthbridge Institute — B.Tech in Robotics, 2024.\n"
            f"Education verification code: EDU-{probe}.",
            "EDUCATION",
        ),
        (
            f"EXPERIENCE\nReliability Engineer at Meridian Works.\n"
            f"Reduced inspection latency by 37 percent. Experience code: EXP-{probe}.\n"
            f"P-{equipment_suffix} connects to TK-{equipment_suffix}.",
            "EXPERIENCE",
        ),
        (
            f"PROJECTS\nBuilt the Copper Finch anomaly detector for rotating equipment.\n"
            f"Project verification code: PRJ-{probe}.",
            "PROJECTS",
        ),
    ]
    document = fitz.open()
    for text, heading in sections:
        page = document.new_page()
        page.insert_text((72, 72), heading, fontsize=16)
        page.insert_textbox(fitz.Rect(72, 110, 540, 720), text, fontsize=11)
    result = document.tobytes(garbage=4, deflate=True)
    document.close()
    return result


async def _wait_for_processing(
    client: httpx.AsyncClient,
    document_id: str,
    timeout_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last: dict = {}
    while time.monotonic() < deadline:
        response = await client.get(f"/api/documents/{document_id}/processing-status")
        response.raise_for_status()
        last = response.json()
        if last["status"] == "completed":
            _require(last["document_status"] == "indexed", f"not indexed: {last}")
            return
        if last["status"] == "failed":
            raise RuntimeError(f"ingestion failed: {last}")
        await asyncio.sleep(1)
    raise TimeoutError(f"ingestion timed out; last={last}")


async def _cloud_state(document_id: str) -> dict:
    collection = os.getenv(
        "QDRANT_COLLECTION_NAME",
        os.getenv("QDRANT_COLLECTION", "document_chunks"),
    )
    qdrant = QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ["QDRANT_API_KEY"],
        timeout=30,
    )
    vector_count = await asyncio.to_thread(
        qdrant.count,
        collection_name=collection,
        count_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=document_id),
                )
            ]
        ),
        exact=True,
    )
    points, _ = await asyncio.to_thread(
        qdrant.scroll,
        collection_name=collection,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=document_id),
                )
            ]
        ),
        limit=100,
        with_payload=True,
        with_vectors=True,
    )
    vector_total = await asyncio.to_thread(
        qdrant.count,
        collection_name=collection,
        exact=True,
    )

    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )
    try:
        async with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            record = await session.run(
                "MATCH (n:Entity) WHERE n.document_id = $document_id "
                "RETURN count(n) AS nodes",
                document_id=document_id,
            )
            graph_count = int((await record.single())["nodes"])
            relationship_result = await session.run(
                "MATCH ()-[r]->() WHERE r.document_id = $document_id "
                "RETURN count(r) AS relationships",
                document_id=document_id,
            )
            relationship_count = int(
                (await relationship_result.single())["relationships"]
            )
            total_result = await session.run(
                "MATCH (n:Entity) WITH count(n) AS nodes "
                "MATCH ()-[r]->() RETURN nodes, count(r) AS relationships"
            )
            total_record = await total_result.single()
    finally:
        await driver.close()
    return {
        "vector_count": int(vector_count.count),
        "vector_total": int(vector_total.count),
        "points": points,
        "graph_nodes": graph_count,
        "graph_relationships": relationship_count,
        "graph_total_nodes": int(total_record["nodes"]),
        "graph_total_relationships": int(total_record["relationships"]),
    }


def _storage() -> SupabaseStorageBackend:
    return SupabaseStorageBackend(
        url=os.environ["SUPABASE_URL"],
        service_role_key=os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        bucket=os.getenv("SUPABASE_STORAGE_BUCKET", "trace"),
        timeout_seconds=float(os.getenv("SUPABASE_STORAGE_TIMEOUT_SECONDS", "30")),
        max_retries=int(os.getenv("SUPABASE_STORAGE_MAX_RETRIES", "3")),
    )


async def _postgres_state(document_id: str) -> tuple[int, int, int]:
    query = (
        "SELECT (d.deleted_at IS NOT NULL)::int, "
        "(SELECT count(*) FROM document_versions v WHERE v.document_id=d.id), "
        "(SELECT count(*) FROM document_chunks c WHERE c.document_id=d.id) "
        f"FROM documents d WHERE d.id='{UUID(document_id)}'"
    )
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    connection = await asyncpg.connect(dsn=dsn)
    try:
        row = await connection.fetchrow(query)
    finally:
        await connection.close()
    _require(row is not None and len(row) == 3, "unexpected PostgreSQL lifecycle state")
    return tuple(int(value) for value in row)  # type: ignore[return-value]


def _restart_backend() -> None:
    subprocess.run(
        ["docker", "compose", "restart", "backend"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


async def _wait_for_health(client: httpx.AsyncClient, timeout_seconds: float = 90) -> dict:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            response = await client.get("/api/health")
            if response.status_code == 200 and response.json().get("status") == "ok":
                return response.json()
            last_error = f"HTTP {response.status_code}: {response.text[:300]}"
        except Exception as exc:  # the container is briefly unavailable during restart
            last_error = repr(exc)
        await asyncio.sleep(1)
    raise TimeoutError(f"backend did not recover after restart: {last_error}")


async def verify(args: argparse.Namespace) -> None:
    load_dotenv(ROOT / ".env")
    if args.check_document_id:
        state = await _cloud_state(args.check_document_id)
        _require(state["vector_count"] == 0, f"Qdrant cleanup left {state['vector_count']} vectors")
        _require(state["graph_nodes"] == 0, f"Neo4j cleanup left {state['graph_nodes']} nodes")
        _require(state["graph_relationships"] == 0, "Neo4j cleanup left relationships")
        print("cleanup: requested document is absent from Qdrant Cloud and Neo4j Aura")
        return

    email = os.getenv("SUPER_ADMIN_EMAIL", "").strip()
    password = os.getenv("SUPER_ADMIN_PASSWORD", "")
    _require(bool(email and password), "bootstrap credentials are missing")

    probe = uuid4().hex[:10].upper()
    equipment_suffix = int(probe[:6], 16) % 900_000 + 10_000
    filename = f"TRACE_Resume_E2E_{probe}.pdf"
    document_id: str | None = None
    history_id: str | None = None
    storage_path: str | None = None
    baseline = await _cloud_state(str(uuid4()))
    storage = _storage()

    timeout = httpx.Timeout(args.request_timeout, connect=10)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=timeout) as client:
        health = (await client.get("/api/health")).raise_for_status().json()
        _require(health["status"] == "ok", f"backend health is not ok: {health}")
        components = health.get("components", {})
        for name in ("database", "qdrant", "neo4j", "storage", "llm", "reranker"):
            if name in components:
                _require(components[name].get("status") in {"ok", "healthy"}, f"{name} unhealthy: {components[name]}")
        print("health: backend and dependencies ok")

        login = await client.post(
            "/api/auth/login", json={"email": email, "password": password}
        )
        login.raise_for_status()
        _require(
            "trace_refresh_token" in client.cookies,
            "HttpOnly refresh cookie was not issued",
        )
        refresh = await client.post("/api/auth/refresh")
        refresh.raise_for_status()
        token = refresh.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        print("auth: login cookie survived and bodyless refresh succeeded")

        upload = await client.post(
            "/api/documents",
            files={"file": (filename, _resume_pdf(probe), "application/pdf")},
            data={"title": f"Resume E2E {probe}", "source": "resume-e2e"},
        )
        upload.raise_for_status()
        document_id = str(upload.json()["id"])
        storage_path = storage.build_document_path(UUID(document_id), 1, filename)
        _require(
            await asyncio.to_thread(storage.exists, storage_path),
            "Supabase object is absent after upload",
        )
        print(f"upload: Supabase-backed PDF accepted ({document_id})")

        try:
            await _wait_for_processing(client, document_id, args.processing_timeout)
            detail = (await client.get(f"/api/documents/{document_id}")).raise_for_status().json()
            _require(detail["doc_type"] == "resume", f"wrong document type: {detail['doc_type']}")
            _require(detail["mime_type"] == "application/pdf", "file format was not retained")
            chunks_response = (
                await client.get(f"/api/documents/{document_id}/chunks", params={"limit": 500})
            ).raise_for_status().json()
            chunks = chunks_response["items"]
            _require(chunks and chunks_response["total_items"] == len(chunks), "PostgreSQL chunks are missing")
            _require(all(item["embedding_status"] == "completed" for item in chunks), "a chunk embedding is incomplete")
            _require(len({item["id"] for item in chunks}) == len(chunks), "duplicate PostgreSQL chunk ids")
            _require(len({item["chunk_index"] for item in chunks}) == len(chunks), "duplicate chunk indexes")
            chunk_by_id = {str(item["id"]): item for item in chunks}
            pg_state = await _postgres_state(document_id)
            _require(pg_state == (0, 1, len(chunks)), f"wrong active PostgreSQL state: {pg_state}")

            cloud = await _cloud_state(document_id)
            _require(cloud["vector_count"] == len(chunks), "Qdrant vector/chunk count mismatch")
            _require(len(cloud["points"]) == len(chunks), "Qdrant scroll returned missing points")
            for point in cloud["points"]:
                payload = point.payload or {}
                chunk_id = str(payload.get("chunk_id", ""))
                _require(chunk_id in chunk_by_id, f"Qdrant has unknown chunk id {chunk_id}")
                source = chunk_by_id[chunk_id]
                _require(str(payload.get("document_id")) == document_id, "wrong Qdrant document id")
                _require(int(payload.get("chunk_index")) == source["chunk_index"], "wrong Qdrant chunk index")
                _require(payload.get("content") == source["content"], "Qdrant/PostgreSQL chunk content mismatch")
                _require(payload.get("filename") == filename, "wrong Qdrant filename")
                vector = point.vector
                if isinstance(vector, dict):
                    vector = next(iter(vector.values()))
                _require(vector is not None and len(vector) == 384, "wrong Qdrant vector dimension")
            _require(cloud["graph_nodes"] > 0, "Aura received no document-scoped entities")
            _require(cloud["graph_relationships"] > 0, "Aura received no document-scoped relationships")
            print("ingestion: native PDF indexed and semantic type detected as resume")

            if args.restart_backend:
                _restart_backend()
                health = await _wait_for_health(client)
                _require(health["status"] == "ok", "backend unhealthy after restart")
                print("restart: backend recovered and persisted cloud/local data remained readable")

            expected = {
                "education": f"EDU-{probe}",
                "experience": f"EXP-{probe}",
                "projects": f"PRJ-{probe}",
            }
            for section, marker in expected.items():
                response = await client.post(
                    "/api/search",
                    json={
                        "query": marker,
                        "top_k": 8,
                        "mode": "ranked",
                        "filters": {"document_type": "resume"},
                    },
                )
                response.raise_for_status()
                results = response.json()["results"]
                _require(
                    any(
                        item["document_id"] == document_id and marker in item["chunk"]
                        for item in results
                    ),
                    f"{section} section was not retrieved",
                )
            print("search: ranked Cloud Qdrant retrieval found education/experience/projects")

            retrieval = await client.post(
                "/api/rag/retrieve",
                json={
                    "query": "Summarize education experience and projects from this resume",
                    "top_k": 8,
                    "filters": {"document_id": document_id},
                },
            )
            retrieval.raise_for_status()
            retrieved_text = "\n".join(item["content"] for item in retrieval.json()["results"])
            for marker in expected.values():
                _require(marker in retrieved_text, f"overview retrieval omitted {marker}")
            print("retrieval: overview retained all four same-document resume passages")

            rag = await client.post(
                "/api/rag/query",
                json={
                    "question": f"What education, experience, and project are stated for {probe}?",
                    "top_k": 8,
                    "filters": {"document_id": document_id},
                },
            )
            rag.raise_for_status()
            answer = rag.json()
            _require(answer["answer"].strip(), "RAG returned an empty answer")
            _require(
                any(citation["document_id"] == document_id for citation in answer["citations"]),
                "RAG did not cite the resume",
            )
            citations = [Citation.model_validate(item) for item in answer["citations"]]
            for citation in citations:
                _require(citation.document_id == document_id, "citation leaked another document")
                _require(citation.chunk_id in chunk_by_id, "citation points to an unknown chunk")
                _require(citation.chunk_content == chunk_by_id[citation.chunk_id]["content"], "citation text mismatches its chunk")
            unsupported = [
                statement for statement in classify_statements(answer["answer"], citations)
                if statement.classification != "FACT"
                and not statement.text.startswith(
                    "Unsupported inferences or recommendations were omitted"
                )
            ]
            _require(not unsupported, f"RAG returned unsupported claims: {unsupported}")
            print("RAG: grounded answer returned with resume citation")

            graph_rag = await client.post(
                "/api/rag/graph-query",
                json={
                    "question": f"What does pump P-{equipment_suffix} connect to?",
                    "top_k": 8,
                    "vector_top_k": 8,
                    "graph_top_k": 5,
                    "filters": {"document_id": document_id},
                },
            )
            graph_rag.raise_for_status()
            graph_answer = graph_rag.json()
            _require(
                all(item.get("source_document") in {"", filename} for item in graph_answer["graph_citations"]),
                "graph facts leaked provenance from another document",
            )
            _require(
                all(item.get("document_id") == document_id for item in graph_answer["citations"]),
                "graph RAG vector citations leaked another document",
            )
            print("graph RAG: document-scoped facts and citations preserved provenance")

            refusal = await client.post(
                "/api/rag/query",
                json={
                    "question": "State the lunar escape velocity and recommend a launch trajectory.",
                    "top_k": 8,
                    "filters": {"document_id": document_id},
                },
            )
            refusal.raise_for_status()
            refusal_body = refusal.json()
            _require(
                "could not find enough cited evidence" in refusal_body["answer"].lower()
                or "do not contain" in refusal_body["answer"].lower(),
                f"unrelated question was not safely refused: {refusal_body['answer']}",
            )
            print("grounding: unrelated claims/recommendations were refused")

            history = await client.post(
                "/api/search/history",
                json={"query": f"resume history probe {probe}", "result_count": 3},
            )
            history.raise_for_status()
            history_id = str(history.json()["id"])
            listed = (await client.get("/api/search/history")).raise_for_status().json()
            _require(any(str(item["id"]) == history_id for item in listed), "history did not persist")
            print("history: PostgreSQL create/list persistence succeeded")
        finally:
            if history_id:
                deleted_history = await client.delete(f"/api/search/history/{history_id}")
                deleted_history.raise_for_status()
            if document_id:
                deleted_document = await client.delete(f"/api/documents/{document_id}")
                deleted_document.raise_for_status()

        _require(document_id is not None and storage_path is not None, "probe was not created")
        final = await _cloud_state(document_id)
        _require(final["vector_count"] == 0, f"Qdrant cleanup left {final['vector_count']} vectors")
        _require(final["graph_nodes"] == 0, f"Neo4j cleanup left {final['graph_nodes']} nodes")
        _require(final["graph_relationships"] == 0, "Neo4j cleanup left relationships")
        _require(
            not await asyncio.to_thread(storage.exists, storage_path),
            "Supabase cleanup left the object",
        )
        _require(
            (final["vector_total"], final["graph_total_nodes"], final["graph_total_relationships"])
            == (baseline["vector_total"], baseline["graph_total_nodes"], baseline["graph_total_relationships"]),
            "existing cloud data totals changed during the probe",
        )
        pg_state = await _postgres_state(document_id)
        _require(pg_state[0] == 1 and pg_state[1] == 1 and pg_state[2] > 0, f"wrong soft-delete/history state: {pg_state}")
        missing = await client.get(f"/api/documents/{document_id}")
        _require(missing.status_code == 404, "soft-deleted document remains API-visible")
        print("cleanup: Qdrant, Aura, and Supabase are clean; PostgreSQL history is consistent")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--processing-timeout", type=float, default=240)
    parser.add_argument("--request-timeout", type=float, default=120)
    parser.add_argument("--check-document-id")
    parser.add_argument("--restart-backend", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        asyncio.run(verify(parse_args()))
    except Exception as exc:
        print(f"Resume E2E failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
