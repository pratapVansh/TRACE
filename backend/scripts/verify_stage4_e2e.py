"""Verify the deployed TRACE document-to-answer path against a running API.

This is intentionally a black-box check. It uses the configured bootstrap account,
uploads one supplied document, waits for ingestion, verifies search and graph/RAG
retrieval, asks Copilot a question, verifies citations, reads the audit trail, and
optionally soft-deletes the verification document.

Run from ``backend`` after the Compose stack is healthy::

    python scripts/verify_stage4_e2e.py \
        --file tests/fixtures/e2e/stage4_verification.txt --cleanup
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import sys
import time

import httpx
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]


def _credentials() -> tuple[str, str]:
    load_dotenv(ROOT / ".env")
    email = os.getenv("SUPER_ADMIN_EMAIL", "").strip()
    password = os.getenv("SUPER_ADMIN_PASSWORD", "")
    if not email or not password:
        raise RuntimeError(
            "SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD must be set in the root .env"
        )
    return email, password


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


async def _wait_for_processing(
    client: httpx.AsyncClient,
    document_id: str,
    *,
    timeout_seconds: float,
) -> dict:
    deadline = time.monotonic() + timeout_seconds
    last: dict = {}
    while time.monotonic() < deadline:
        response = await client.get(f"/api/documents/{document_id}/processing-status")
        response.raise_for_status()
        last = response.json()
        if last["status"] == "completed":
            return last
        if last["status"] == "failed":
            raise RuntimeError(f"ingestion failed: {last.get('error')}")
        await asyncio.sleep(1)
    raise TimeoutError(f"ingestion did not finish in {timeout_seconds}s; last={last}")


async def verify(args: argparse.Namespace) -> None:
    email, password = _credentials()
    source = args.file.resolve()
    _require(source.is_file(), f"verification file not found: {source}")

    timeout = httpx.Timeout(args.request_timeout, connect=10.0)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=timeout) as client:
        health = (await client.get("/api/health")).raise_for_status().json()
        _require(health["status"] == "ok", f"health is not ok: {health}")
        print("health: ok")

        login = await client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        me = (await client.get("/api/auth/me")).raise_for_status().json()
        _require(me["role"] == "SuperAdmin", f"bootstrap account is {me['role']}, not SuperAdmin")
        print("bootstrap/login: SuperAdmin ok")

        with source.open("rb") as handle:
            upload = await client.post(
                "/api/documents",
                files={"file": (source.name, handle, "text/plain")},
                data={"title": "Stage 4 E2E Verification", "source": "production-hardening"},
            )
        upload.raise_for_status()
        document = upload.json()
        document_id = str(document["id"])
        print(f"upload: accepted document={document_id}")

        try:
            processing = await _wait_for_processing(
                client,
                document_id,
                timeout_seconds=args.processing_timeout,
            )
            _require(processing["document_status"] == "indexed", f"unexpected document status: {processing}")
            print("processing: completed/indexed")

            search = await client.post(
                "/api/search",
                json={
                    "query": "TRACE-E2E-20261002-P9901",
                    "top_k": 5,
                    "mode": "hybrid",
                },
            )
            search.raise_for_status()
            search_items = search.json()["results"]
            _require(
                any(str(item["document_id"]) == document_id for item in search_items),
                "uploaded document was not returned by hybrid search",
            )
            print("search: uploaded document retrieved")

            graph_search = await client.get("/api/graph/search", params={"q": "P-9901", "limit": 20})
            graph_search.raise_for_status()
            graph_entities = graph_search.json()["items"]
            _require(any(item["name"] == "P-9901" for item in graph_entities), "P-9901 missing from graph")
            print("graph: uploaded entity retrieved")

            graph_rag = await client.post(
                "/api/rag/graph-query",
                json={
                    "question": "Where is P-9901 located and what equipment does it feed?",
                    "top_k": 5,
                    "vector_top_k": 5,
                    "graph_top_k": 5,
                },
            )
            graph_rag.raise_for_status()
            graph_answer = graph_rag.json()
            _require(graph_answer["citations"], "graph RAG returned no document citations")
            _require(graph_answer["graph_facts"], "graph RAG returned no graph facts")
            print("graph retrieval: answer, document citations, and graph facts present")

            chat = await client.post(
                "/api/chat",
                json={
                    "question": "For TRACE-E2E-20261002-P9901, what must be done before restart?",
                    "top_k": 5,
                },
            )
            chat.raise_for_status()
            chat_answer = chat.json()
            _require(chat_answer["answer"].strip(), "Copilot returned an empty answer")
            _require(chat_answer["citations"], "Copilot returned no citations")
            _require(
                any(str(citation.get("document_id")) == document_id for citation in chat_answer["citations"]),
                "Copilot citations do not include the uploaded document",
            )
            print("copilot/citations: grounded response cites uploaded document")

            audit = await client.get("/api/audit-logs", params={"limit": 500})
            audit.raise_for_status()
            audit_items = audit.json()["items"]
            _require(
                any(str(item.get("entity_id")) == document_id for item in audit_items),
                "audit log has no entry for the uploaded document",
            )
            print("audit logs: uploaded document action visible")
        finally:
            if args.cleanup:
                cleanup = await client.delete(f"/api/documents/{document_id}")
                cleanup.raise_for_status()
                print("cleanup: verification document soft-deleted")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--processing-timeout", type=float, default=180.0)
    parser.add_argument("--request-timeout", type=float, default=120.0)
    parser.add_argument("--cleanup", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        asyncio.run(verify(parse_args()))
    except Exception as exc:
        print(f"Stage 4 verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
