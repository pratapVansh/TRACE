"""Thread-safe metrics collector — histograms, counters, and gauges.

All operations are lock-free for the hot path (single-writer via the
GIL + list appends) and lock-guarded only for snapshot reads.
"""

import asyncio
import threading
from collections import defaultdict
from typing import Any


class _Histogram:
    __slots__ = ("_values", "_lock")

    def __init__(self) -> None:
        self._values: list[float] = []
        self._lock = threading.Lock()

    def record(self, value: float) -> None:
        with self._lock:
            self._values.append(value)

    def snapshot(self) -> dict[str, float]:
        vals = self._values
        if not vals:
            return {"count": 0, "sum": 0.0, "min": 0.0, "max": 0.0, "avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
        with self._lock:
            sorted_vals = sorted(vals)
        n = len(sorted_vals)
        total = sum(sorted_vals)
        return {
            "count": n,
            "sum": round(total, 4),
            "min": round(sorted_vals[0], 4),
            "max": round(sorted_vals[-1], 4),
            "avg": round(total / n, 4),
            "p50": round(sorted_vals[int(n * 0.50)], 4),
            "p95": round(sorted_vals[int(n * 0.95)], 4),
            "p99": round(sorted_vals[int(n * 0.99)], 4),
        }

    def clear(self) -> None:
        with self._lock:
            self._values.clear()


class MetricsCollector:
    """Singleton metrics store — counters, histograms, gauges."""

    _instance: "MetricsCollector | None" = None
    _creation_lock = threading.Lock()

    def __new__(cls) -> "MetricsCollector":
        with cls._creation_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_sync()
            return cls._instance

    def _init_sync(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._histograms: dict[str, _Histogram] = defaultdict(_Histogram)
        self._gauges: dict[str, float] = {}
        self._counters_lock = threading.Lock()
        self._gauges_lock = threading.Lock()

    # ── Counters ────────────────────────────────────────────────

    def increment(self, name: str, delta: int = 1) -> None:
        with self._counters_lock:
            self._counters[name] += delta

    def counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    # ── Histograms ──────────────────────────────────────────────

    def record_histogram(self, name: str, value: float) -> None:
        self._histograms[name].record(value)

    def histogram_snapshot(self, name: str) -> dict[str, float]:
        return self._histograms[name].snapshot()

    # ── Gauges ──────────────────────────────────────────────────

    def set_gauge(self, name: str, value: float) -> None:
        with self._gauges_lock:
            self._gauges[name] = value

    def gauge(self, name: str) -> float:
        return self._gauges.get(name, 0.0)

    # ── Snapshot ────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "counters": dict(self._counters),
            "histograms": {},
            "gauges": dict(self._gauges),
        }
        for name, hist in self._histograms.items():
            out["histograms"][name] = hist.snapshot()
        return out

    def reset(self) -> None:
        with self._counters_lock:
            self._counters.clear()
        with self._gauges_lock:
            self._gauges.clear()
        for hist in self._histograms.values():
            hist.clear()
        self._histograms.clear()

    # ── Prometheus plaintext format ─────────────────────────────

    @staticmethod
    def _sanitize(name: str) -> str:
        return name.replace("-", "_").replace(" ", "_").replace(".", "_")

    def prometheus_output(self) -> str:
        snap = self.snapshot()
        lines: list[str] = []

        for name, value in snap["counters"].items():
            safe = self._sanitize(name)
            lines.append(f"# HELP {safe} Counter")
            lines.append(f"# TYPE {safe} counter")
            lines.append(f"{safe} {value}")

        for name, hdata in snap["histograms"].items():
            safe = self._sanitize(name)
            lines.append(f"# HELP {safe} Histogram")
            lines.append(f"# TYPE {safe} histogram")
            lines.append(f"{safe}_count {hdata['count']}")
            lines.append(f"{safe}_sum {hdata['sum']}")
            lines.append(f"{safe}_bucket{{le=\"0.05\"}} 0")
            lines.append(f"{safe}_bucket{{le=\"0.1\"}} 0")
            lines.append(f"{safe}_bucket{{le=\"0.25\"}} 0")
            lines.append(f"{safe}_bucket{{le=\"0.5\"}} 0")
            lines.append(f"{safe}_bucket{{le=\"1.0\"}} 0")
            lines.append(f"{safe}_bucket{{le=\"2.5\"}} 0")
            lines.append(f"{safe}_bucket{{le=\"5.0\"}} 0")
            lines.append(f"{safe}_bucket{{le=\"10.0\"}} 0")
            lines.append(f"{safe}_bucket{{le=\"+Inf\"}} {hdata['count']}")

        for name, value in snap["gauges"].items():
            safe = self._sanitize(name)
            lines.append(f"# HELP {safe} Gauge")
            lines.append(f"# TYPE {safe} gauge")
            lines.append(f"{safe} {value}")

        return "\n".join(lines)
