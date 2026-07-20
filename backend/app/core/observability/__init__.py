"""Observability — metrics collection and distributed tracing.

Usage::

    from app.core.observability import metrics, get_tracer, trace_span

    # Record a latency observation
    metrics.record_histogram("agent.execution.time", 1.23)

    # Increment a counter
    metrics.increment("memory.hits")

    # Distributed tracing
    tracer = get_tracer(__name__)
    with trace_span(tracer, "my_operation", {"key": "value"}):
        do_work()
"""

from app.core.observability.metrics import MetricsCollector
from app.core.observability.tracing import get_tracer, trace_span

metrics = MetricsCollector()

__all__ = [
    "metrics",
    "get_tracer",
    "trace_span",
    "MetricsCollector",
]
