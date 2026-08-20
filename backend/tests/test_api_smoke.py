"""Route-level smoke tests.

The unit suite passed with 1112 tests while three endpoints returned 500 on
every call: nothing exercised them at the routing layer. These tests cover that
gap — each one fails against the pre-fix code:

* ``/api/dashboard`` built its response without the connection flags the schema
  required, so Pydantic raised before the route could fill them in.
* ``/api/metrics`` awaited three synchronous functions.
* ``/api/chat/conversations/archived`` sat below ``/conversations/{id}``, which
  matched first and tried to parse "archived" as a conversation id.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_chat_service, get_current_user
from app.core.dependencies import get_db
from app.main import app
from app.schemas.auth import UserMeResponse
from app.schemas.chat import ArchiveListResponse, ConversationItem
from app.schemas.dashboard import DashboardResponse, RecentUploadItem


@pytest.fixture
def admin_user() -> UserMeResponse:
    return UserMeResponse(
        id=uuid.uuid4(),
        email="admin@example.com",
        full_name="Test Admin",
        role="SuperAdmin",
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def client(admin_user: UserMeResponse):
    app.dependency_overrides[get_current_user] = lambda: admin_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ── Route shadowing ────────────────────────────────────────────


def _segments(path: str) -> list[str]:
    return [seg for seg in path.split("/") if seg]


def _shadows(earlier: str, later: str) -> bool:
    """Whether *earlier* would capture every request meant for *later*.

    True when the two have the same shape and every segment either matches
    literally or is a path parameter on the *earlier* route standing where the
    later route has a literal.
    """
    a, b = _segments(earlier), _segments(later)
    if len(a) != len(b):
        return False
    saw_param_over_literal = False
    for seg_a, seg_b in zip(a, b):
        a_is_param = seg_a.startswith("{")
        b_is_param = seg_b.startswith("{")
        if a_is_param and not b_is_param:
            saw_param_over_literal = True
        elif seg_a != seg_b:
            return False
    return saw_param_over_literal


def test_no_static_route_is_shadowed_by_an_earlier_path_parameter(
    client: TestClient,
):
    """A literal path must not sit below a parameterised one that matches it.

    Starlette resolves in declaration order, so ``/conversations/{id}``
    declared first swallows ``/conversations/archived`` and the handler never
    runs. Asserted across every route rather than for the one known case,
    since the failure is a silent runtime-only 500.

    The OpenAPI schema is used rather than ``app.routes`` because this FastAPI
    version nests included routers behind a private wrapper; ``paths`` is a
    public, ordered view of the same registrations. It is read inside the
    client fixture because routers are included during startup.
    """
    spec = app.openapi()["paths"]
    paths = list(spec)

    conflicts = []
    for i, later in enumerate(paths):
        for earlier in paths[:i]:
            # Only an overlapping HTTP method can actually capture the request:
            # GET /neighbors/{id} does not shadow POST /neighbors/batch.
            shared_methods = {
                m.lower() for m in spec[earlier]
            } & {m.lower() for m in spec[later]}
            if shared_methods and _shadows(earlier, later):
                conflicts.append(
                    f"{earlier} (declared first) shadows {later} "
                    f"for {sorted(shared_methods)}"
                )

    assert not conflicts, "Unreachable routes: " + "; ".join(conflicts)


def test_archived_conversations_declared_before_parameterised_route(
    client: TestClient,
):
    """The concrete case behind the generic check above."""
    paths = list(app.openapi()["paths"])

    assert "/api/chat/conversations/archived" in paths
    assert paths.index("/api/chat/conversations/archived") < paths.index(
        "/api/chat/conversations/{conversation_id}"
    ), (
        "/conversations/archived must be declared before "
        "/conversations/{conversation_id} or it is unreachable"
    )


def test_archived_conversations_endpoint_returns_ok(client: TestClient):
    chat_service = AsyncMock()
    chat_service.list_archived.return_value = ArchiveListResponse(
        conversations=[], total=0,
    )
    app.dependency_overrides[get_chat_service] = lambda: chat_service

    response = client.get("/api/chat/conversations/archived")

    assert response.status_code == 200, response.text
    assert response.json() == {"conversations": [], "total": 0}
    chat_service.list_archived.assert_awaited_once()


# ── Metrics ────────────────────────────────────────────────────


def test_metrics_json_returns_ok(client: TestClient):
    """``snapshot()`` is synchronous; awaiting it raised TypeError."""
    response = client.get("/api/metrics")

    assert response.status_code == 200, response.text
    body = response.json()
    assert {"counters", "histograms", "gauges"} <= set(body)


def test_metrics_prometheus_returns_ok(client: TestClient):
    """``prometheus_output()`` is synchronous too — same defect, same fix."""
    response = client.get("/api/metrics", params={"format": "prometheus"})

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/plain")


def test_metrics_reset_returns_ok(client: TestClient):
    """``reset()`` is synchronous — the third awaited non-coroutine."""
    response = client.post("/api/metrics/reset")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ok"


# ── Dashboard ──────────────────────────────────────────────────


def test_dashboard_response_builds_without_connection_flags():
    """The service constructs the response; the route fills the flags in after.

    Making the flags required meant the service could never build the object,
    so the endpoint failed before the route got a chance to set them.
    """
    response = DashboardResponse(
        document_count=1,
        entity_count=0,
        relationship_count=0,
        conversation_count=0,
        pending_jobs=0,
        recent_uploads=[],
    )

    assert response.qdrant_connected is False
    assert response.neo4j_connected is False
    assert response.db_connected is False


@pytest.mark.asyncio
async def test_dashboard_service_returns_valid_response():
    """Exercises the exact construction path that raised ValidationError."""
    from app.services.dashboard_service import DashboardService

    service = DashboardService(session=AsyncMock(), graph_store=None)
    service._doc_repo = AsyncMock()
    service._doc_repo.count_documents.return_value = 3
    service._doc_repo.list_documents.return_value = []
    service._conv_repo = AsyncMock()
    service._conv_repo.count_conversations.return_value = 2
    service._job_repo = AsyncMock()
    service._job_repo.count_pending_jobs.return_value = 1

    result = await service.get_dashboard()

    assert isinstance(result, DashboardResponse)
    assert result.document_count == 3
    assert result.conversation_count == 2
    assert result.pending_jobs == 1


def test_dashboard_endpoint_reports_live_connection_flags(
    client: TestClient, monkeypatch,
):
    """The route overwrites the defaults with real app.state values."""
    from app.services.dashboard_service import DashboardService

    async def fake_get_dashboard(self) -> DashboardResponse:
        return DashboardResponse(
            document_count=5,
            entity_count=10,
            relationship_count=7,
            conversation_count=0,
            pending_jobs=0,
            recent_uploads=[
                RecentUploadItem(
                    id=str(uuid.uuid4()),
                    title="Pump Manual",
                    filename="pump.pdf",
                    status="indexed",
                    uploaded_at=datetime.now(UTC).isoformat(),
                ),
            ],
        )

    monkeypatch.setattr(DashboardService, "get_dashboard", fake_get_dashboard)
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.state.qdrant_connected = True
    app.state.db_connected = True

    response = client.get("/api/dashboard")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document_count"] == 5
    assert body["qdrant_connected"] is True
    assert body["db_connected"] is True
    assert len(body["recent_uploads"]) == 1
