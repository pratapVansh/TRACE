"""OpenTelemetry tracing — graceful fallback when OTel is not installed.

Usage::

    from app.core.observability import get_tracer

    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("my_operation") as span:
        span.set_attribute("key", "value")
        do_work()
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Generator

from app.core.config import settings

logger = logging.getLogger(__name__)

_OTEL_AVAILABLE = False
_tracer_provider = None

# ── Attempt optional OpenTelemetry import ─────────────────────
try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except ImportError:
    otel_trace = None  # type: ignore[assignment]
    OTLPSpanExporter = None  # type: ignore[assignment,misc]
    Resource = None  # type: ignore[assignment,misc]
    TracerProvider = None  # type: ignore[assignment,misc]
    BatchSpanProcessor = None  # type: ignore[assignment,misc]


def _setup_otel() -> None:
    """Initialize the OpenTelemetry tracer provider and exporter."""
    global _tracer_provider
    if _tracer_provider is not None or not _OTEL_AVAILABLE:
        return
    if not settings.otel_enabled:
        logger.info("OpenTelemetry tracing is disabled via config")
        return

    resource = Resource.create({
        "service.name": settings.app_name,
        "service.version": "1.0.0",
    })

    provider = TracerProvider(resource=resource)

    endpoint = settings.otel_exporter_otlp_endpoint
    if endpoint:
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("OTLP span exporter configured: %s", endpoint)
    else:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        console = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console))
        logger.info("Console span exporter configured (no OTLP endpoint set)")

    otel_trace.set_tracer_provider(provider)  # type: ignore[union-attr]
    _tracer_provider = provider


def _get_otel_tracer(name: str) -> Any:
    """Return an OpenTelemetry tracer instance, or None."""
    if not _OTEL_AVAILABLE:
        return None
    if _tracer_provider is None:
        _setup_otel()
    return otel_trace.get_tracer(name)  # type: ignore[union-attr]


# ── No-op fallback tracer ──────────────────────────────────────


class _NoOpSpan:
    """Mimics the OpenTelemetry Span interface but does nothing."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_attributes(self, attributes: dict[str, Any]) -> None:
        pass

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def end(self) -> None:
        pass

    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def record_exception(self, exc: Exception, attributes: dict[str, Any] | None = None) -> None:
        pass


class _NoOpTracer:
    """Mimics the OpenTelemetry Tracer interface but does nothing."""

    def start_as_current_span(self, name: str, **kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan()

    def start_span(self, name: str, **kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan()


_noop_tracer = _NoOpTracer()


def get_tracer(name: str) -> Any:
    """Return an OpenTelemetry tracer, or a no-op tracer if OTel is unavailable.

    This is the public API — every component should use this function
    instead of importing opentelemetry directly.
    """
    otel = _get_otel_tracer(name)
    return otel or _noop_tracer


# ── Convenience context manager for simple tracing ─────────────


@contextmanager
def trace_span(
    tracer: Any,
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """Context manager wrapping an OTel span with timing and error capture.

    Works with both real and no-op tracers.
    """
    span = tracer.start_as_current_span(name)
    if attributes:
        span.set_attributes(attributes)
    start = time.perf_counter()
    try:
        yield span
    except Exception as exc:
        span.record_exception(exc)
        span.set_attribute("error", True)
        span.set_attribute("error.type", type(exc).__name__)
        span.set_attribute("duration_ms", (time.perf_counter() - start) * 1000)
        raise
    finally:
        span.end()


__all__ = [
    "get_tracer",
    "trace_span",
    "_OTEL_AVAILABLE",
]
