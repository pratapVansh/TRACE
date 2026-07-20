import time
import logging
from contextlib import contextmanager
from typing import Any, Generator

# Import the pre-configured JSON-aware logger
from app.core.logging import logger

class TelemetryTracker:
    """Lightweight metrics and tracing tracker for production hardening."""
    
    @staticmethod
    def record_metric(name: str, value: float, tags: dict[str, Any] | None = None) -> None:
        """Record a numerical metric (e.g., latency, confidence)."""
        payload = {
            "metric_name": name,
            "metric_value": value,
            "tags": tags or {},
            "type": "metric"
        }
        logger.info(f"METRIC: {name}={value}", extra={"telemetry": payload})

    @staticmethod
    def record_event(name: str, payload: dict[str, Any] | None = None) -> None:
        """Record a structured event (e.g., agent_start, tool_failure)."""
        data = {
            "event_name": name,
            "payload": payload or {},
            "type": "event"
        }
        logger.info(f"EVENT: {name}", extra={"telemetry": data})

@contextmanager
def trace_span(name: str, tags: dict[str, Any] | None = None) -> Generator[None, None, None]:
    """Context manager for tracing execution time and success/failure."""
    start_time = time.perf_counter()
    tags = tags or {}
    TelemetryTracker.record_event(f"{name}_start", tags)
    try:
        yield
        duration = time.perf_counter() - start_time
        TelemetryTracker.record_metric(f"{name}_duration_sec", duration, tags)
        TelemetryTracker.record_event(f"{name}_success", tags)
    except Exception as exc:
        duration = time.perf_counter() - start_time
        tags["error"] = type(exc).__name__
        tags["error_message"] = str(exc)
        TelemetryTracker.record_metric(f"{name}_duration_sec", duration, tags)
        TelemetryTracker.record_event(f"{name}_failure", tags)
        raise

metrics = TelemetryTracker()
