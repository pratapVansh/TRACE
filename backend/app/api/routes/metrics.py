"""Metrics endpoint — Prometheus + JSON formats."""

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from app.core.observability import metrics

router = APIRouter(prefix="/metrics", tags=["observability"])


@router.get("")
async def get_metrics(
    format: str = Query("json", description="Output format: json or prometheus"),
):
    """Return current observability metrics.

    Supports two formats:
    - ``json`` (default) — nested dict with counters, histograms, gauges
    - ``prometheus`` — plaintext Prometheus exposition format
    """
    if format == "prometheus":
        return PlainTextResponse(metrics.prometheus_output())

    return metrics.snapshot()


@router.post("/reset")
async def reset_metrics():
    """Clear all accumulated metrics (for testing)."""
    metrics.reset()
    return {"status": "ok", "message": "Metrics reset"}
