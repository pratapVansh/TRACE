"""Read-only invariants used before and after legacy derived-data cleanup."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path

import asyncpg
import httpx
from dotenv import load_dotenv
from qdrant_client import QdrantClient


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


async def _postgres_snapshot() -> dict:
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    connection = await asyncpg.connect(dsn=dsn)
    try:
        tables = {}
        queries = {
            "documents": "SELECT * FROM documents ORDER BY id",
            "versions": "SELECT * FROM document_versions ORDER BY id",
            "chunks": "SELECT * FROM document_chunks ORDER BY id",
            "jobs": "SELECT * FROM ingestion_jobs ORDER BY id",
        }
        for name, query in queries.items():
            rows = [dict(row) for row in await connection.fetch(query)]
            tables[name] = {"count": len(rows), "sha256": _digest(rows)}
        return tables
    finally:
        await connection.close()


def _qdrant_snapshot() -> dict:
    client = QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ["QDRANT_API_KEY"],
        timeout=30,
    )
    collection = os.getenv("QDRANT_COLLECTION_NAME", "document_chunks")
    points = []
    offset = None
    while True:
        batch, offset = client.scroll(
            collection_name=collection,
            limit=128,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        points.extend({
            "id": str(point.id),
            "payload": point.payload or {},
            "vector": point.vector,
        } for point in batch)
        if offset is None:
            break
    points.sort(key=lambda item: item["id"])
    return {"count": len(points), "sha256": _digest(points)}


async def _rag_snapshot(base_url: str) -> dict:
    queries = [
        "P-101 pump oil leakage",
        "boiler start-up procedure",
        "instrument air compressor dew point",
        "hot work permit gas testing",
    ]
    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        login = await client.post("/api/auth/login", json={
            "email": os.environ["SUPER_ADMIN_EMAIL"],
            "password": os.environ["SUPER_ADMIN_PASSWORD"],
        })
        login.raise_for_status()
        token = login.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        result = {}
        for query in queries:
            response = await client.post("/api/rag/retrieve", json={
                "query": query,
                "top_k": 5,
            })
            response.raise_for_status()
            result[query] = [
                {
                    "chunk_id": item["chunk_id"],
                    "document_id": item["document_id"],
                    "document_name": item["document_name"],
                }
                for item in response.json()["results"]
            ]
        return result


async def snapshot(base_url: str) -> dict:
    return {
        "postgres": await _postgres_snapshot(),
        "qdrant": await asyncio.to_thread(_qdrant_snapshot),
        "rag_retrieval": await _rag_snapshot(base_url),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(snapshot(args.base_url)), indent=2, default=str))
