"""/api/health must distinguish healthy from degraded.

Every external dependency in this service fails soft: the app logs a warning at
startup and carries on. That is the right call for availability, but it meant a
deployment running without its reranker, its graph store or its LLM reported
exactly the same ``{"status": "ok"}`` as a fully working one. The reranker is
the sharpest case — it can also switch itself off *after* startup, mid-traffic,
and callers keep getting results that are simply ranked worse.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import reranker_service


@pytest.fixture
def health_client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def _restore_reranker_state():
    saved = (
        reranker_service._DISABLED,
        reranker_service._DISABLED_REASON,
        reranker_service._MODEL_LOAD_FAILED,
        reranker_service._MODEL,
    )
    yield
    (
        reranker_service._DISABLED,
        reranker_service._DISABLED_REASON,
        reranker_service._MODEL_LOAD_FAILED,
        reranker_service._MODEL,
    ) = saved


def _health(client) -> dict:
    response = client.get("/api/health")
    assert response.status_code == 200
    return response.json()


def test_health_reports_every_component(health_client):
    body = _health(health_client)
    assert set(body["components"]) == {
        "database",
        "vector_store",
        "graph_store",
        "llm",
        "reranker",
    }
    assert body["service"] == "TRACE Backend"
    # The reranker is the one component read live rather than from a startup
    # snapshot, because it is the one that can fail later.
    assert body["components"]["reranker"]["checked"] == "live"


def test_runtime_disabled_reranker_is_reported(health_client, monkeypatch):
    """The silent failure this endpoint exists to expose."""
    monkeypatch.setattr(reranker_service.settings, "rerank_enabled", True)
    monkeypatch.setattr(reranker_service, "_MODEL", object())
    monkeypatch.setattr(reranker_service, "_MODEL_LOAD_FAILED", False)
    monkeypatch.setattr(reranker_service, "_DISABLED", False)

    healthy = _health(health_client)
    assert healthy["status"] == "ok"
    assert healthy["degraded"] == []

    # Exactly what a scoring timeout does at runtime.
    reranker_service._disable("scoring exceeded its budget")

    degraded = _health(health_client)
    assert degraded["status"] == "degraded"
    assert "reranker" in degraded["degraded"]

    component = degraded["components"]["reranker"]
    assert component["status"] == "degraded"
    # The detail has to say what it costs, not just that something is off.
    assert "scoring exceeded its budget" in component["detail"]
    assert "unreranked results" in component["detail"]


def test_failed_model_load_is_reported(health_client, monkeypatch):
    monkeypatch.setattr(reranker_service.settings, "rerank_enabled", True)
    monkeypatch.setattr(reranker_service, "_DISABLED", False)
    monkeypatch.setattr(reranker_service, "_MODEL", None)
    monkeypatch.setattr(reranker_service, "_MODEL_LOAD_FAILED", True)

    body = _health(health_client)
    assert body["status"] == "degraded"
    assert "failed to load" in body["components"]["reranker"]["detail"]


def test_unwarmed_model_is_reported(health_client, monkeypatch):
    """Not loaded is not the same as loaded — and it predicts a later failure."""
    monkeypatch.setattr(reranker_service.settings, "rerank_enabled", True)
    monkeypatch.setattr(reranker_service, "_DISABLED", False)
    monkeypatch.setattr(reranker_service, "_MODEL_LOAD_FAILED", False)
    monkeypatch.setattr(reranker_service, "_MODEL", None)

    body = _health(health_client)
    assert body["status"] == "degraded"
    assert "warmup did not run" in body["components"]["reranker"]["detail"]


def test_reranking_switched_off_is_not_degraded(health_client, monkeypatch):
    """Configured off is a choice, not a fault, and must not raise an alarm."""
    monkeypatch.setattr(reranker_service.settings, "rerank_enabled", False)
    monkeypatch.setattr(reranker_service, "_DISABLED", False)

    body = _health(health_client)
    assert body["components"]["reranker"]["status"] == "off"
    assert "reranker" not in body["degraded"]
    assert body["status"] == "ok"


def test_optional_store_down_is_degraded_not_unavailable(health_client):
    """Losing the graph store costs answer quality; it does not stop the service."""
    app.state.neo4j_store = None
    body = _health(health_client)

    assert body["status"] == "degraded"
    assert "graph_store" in body["degraded"]
    assert body["components"]["graph_store"]["required"] is False
    assert "knowledge graph" in body["components"]["graph_store"]["detail"]


def test_required_store_down_is_unavailable(health_client):
    """Losing Qdrant means retrieval returns nothing — that is not 'degraded'."""
    app.state.qdrant_connected = False
    body = _health(health_client)

    assert body["status"] == "unavailable"
    assert body["components"]["vector_store"]["required"] is True
