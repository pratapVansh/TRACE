from fastapi import APIRouter, Request

from app.schemas.health import ComponentHealth, HealthResponse
from app.services import reranker_service

router = APIRouter(tags=["health"])


def _from_startup_flag(
    connected: bool,
    *,
    required: bool,
    configured: bool = True,
    degraded_detail: str,
) -> ComponentHealth:
    """Report a dependency that was probed once, during startup.

    Every external store in this service fails soft at boot: the app logs a
    warning and carries on. That is deliberate — a missing graph store should
    not stop documents being uploaded — but it means a half-working deployment
    looks identical to a healthy one from the outside.
    """
    if not configured:
        return ComponentHealth(
            status="off",
            checked="startup",
            required=required,
            detail="not configured",
        )
    return ComponentHealth(
        status="ok" if connected else "unavailable",
        checked="startup",
        required=required,
        detail=None if connected else degraded_detail,
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Liveness plus a per-component breakdown.

    Deliberately does no network I/O: every reading is either a process-local
    flag or a value recorded at startup, so this stays usable as a probe.
    """
    state = request.app.state

    rerank = reranker_service.status()
    components: dict[str, ComponentHealth] = {
        "database": _from_startup_flag(
            getattr(state, "db_connected", False),
            required=True,
            degraded_detail=(
                "PostgreSQL was unreachable at startup — documents, auth and "
                "conversations are unavailable"
            ),
        ),
        "vector_store": _from_startup_flag(
            getattr(state, "qdrant_connected", False),
            required=True,
            degraded_detail=(
                "Qdrant was unreachable at startup — search and retrieval "
                "return nothing"
            ),
        ),
        "graph_store": _from_startup_flag(
            getattr(state, "neo4j_store", None) is not None,
            required=False,
            degraded_detail=(
                "Neo4j was unreachable at startup — the knowledge graph is "
                "empty and answers lose their graph facts"
            ),
        ),
        "llm": _from_startup_flag(
            getattr(state, "llm_provider", None) is not None,
            required=False,
            degraded_detail=(
                "the LLM provider was unavailable at startup — Copilot cannot "
                "generate answers, though retrieval still works"
            ),
        ),
        "reranker": ComponentHealth(
            status=str(rerank["status"]),
            # The only component whose state is read live: its flags are
            # in-process, and it is the one that can turn itself off long
            # after startup.
            checked="live",
            required=False,
            detail=rerank["detail"],  # type: ignore[arg-type]
        ),
    }

    degraded = [name for name, c in components.items() if c.status not in ("ok", "off")]
    required_down = [
        name for name, c in components.items() if c.required and c.status != "ok"
    ]

    if required_down:
        status = "unavailable"
    elif degraded:
        status = "degraded"
    else:
        status = "ok"

    return HealthResponse(
        status=status,
        service="TRACE Backend",
        degraded=degraded,
        components=components,
    )
