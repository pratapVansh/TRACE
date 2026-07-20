"""Observability dashboard — aggregated monitoring data."""

from fastapi import APIRouter

from app.core.observability import metrics

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/dashboard")
async def observability_dashboard():
    """Aggregated dashboard data for monitoring.

    Returns latency percentiles, memory efficiency, hallucination rate,
    citation coverage, confidence trends, and reasoning depth for all
    agents — computed from the in-process metrics store.
    """
    snap = metrics.snapshot()
    histograms = snap.get("histograms", {})
    counters = snap.get("counters", {})
    gauges = snap.get("gauges", {})

    # ── Agent latencies (p50 / p95 / p99) ──────────────────────
    agent_latencies: dict[str, dict[str, float]] = {}
    for hname, hdata in histograms.items():
        if hname.startswith("agent.") and hname.endswith(".time"):
            agent_name = hname.replace("agent.", "").replace(".time", "")
            agent_latencies[agent_name] = {
                "p50": hdata.get("p50", 0),
                "p95": hdata.get("p95", 0),
                "p99": hdata.get("p99", 0),
                "avg": hdata.get("avg", 0),
                "count": hdata.get("count", 0),
            }

    # ── Tool latencies ─────────────────────────────────────────
    tool_latencies: dict[str, dict[str, float]] = {}
    for hname, hdata in histograms.items():
        if hname.startswith("tool.") and hname.endswith(".time"):
            tool_name = hname.replace("tool.", "").replace(".time", "")
            tool_latencies[tool_name] = {
                "p50": hdata.get("p50", 0),
                "p95": hdata.get("p95", 0),
                "p99": hdata.get("p99", 0),
                "avg": hdata.get("avg", 0),
                "count": hdata.get("count", 0),
            }

    # ── Memory efficiency ──────────────────────────────────────
    mem_hits = counters.get("memory.hits", 0)
    mem_misses = counters.get("memory.misses", 0)
    mem_total = mem_hits + mem_misses
    mem_hit_rate = round(mem_hits / mem_total, 4) if mem_total > 0 else 0.0

    # ── Hallucination rate ─────────────────────────────────────
    hallucination_flagged = counters.get("hallucination.flagged", 0)
    answers_total = counters.get("answer.total", 0)
    hallucination_rate = (
        round(hallucination_flagged / answers_total, 4)
        if answers_total > 0
        else 0.0
    )

    # ── Citation coverage ──────────────────────────────────────
    citations_total = counters.get("citations.total", 0)
    citation_coverage = round(
        citations_total / answers_total, 2
    ) if answers_total > 0 else 0.0

    # ── Confidence trends ──────────────────────────────────────
    confidence_data = histograms.get("confidence.score", {})
    confidence_trends = {
        "avg": confidence_data.get("avg", 0),
        "min": confidence_data.get("min", 0),
        "max": confidence_data.get("max", 0),
    } if confidence_data else {}

    # ── Reasoning depth ────────────────────────────────────────
    reasoning_data = histograms.get("reasoning.length", {})

    return {
        "latency": {
            "agent": agent_latencies,
            "tool": tool_latencies,
        },
        "memory": {
            "hits": mem_hits,
            "misses": mem_misses,
            "hit_rate": mem_hit_rate,
        },
        "hallucination": {
            "flagged": hallucination_flagged,
            "total_answers": answers_total,
            "rate": hallucination_rate,
        },
        "citations": {
            "total": citations_total,
            "coverage_per_answer": citation_coverage,
        },
        "confidence": confidence_trends,
        "reasoning": {
            "avg_length": reasoning_data.get("avg", 0),
            "max_length": reasoning_data.get("max", 0),
        },
    }
