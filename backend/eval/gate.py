"""Retrieval floors — the CI gate for Stage 6.

    python -m eval.gate                      # gate the shipped config (passage2)
    python -m eval.gate --config baseline    # gate a different stored run

Reads a stored ``eval/results/<config>/retrieval.json`` and fails when a
summary metric has fallen below its floor. Retrieval is the only thing gated:
it is deterministic and reran identically twice, while answer metrics need
Groq and carry one-sample noise. Answer metrics are reported by
``eval/results/comparison.md`` and must never gate.

**What this does and does not prove.** It checks the *recorded* numbers, not a
fresh run — CI has no corpus to retrieve from (an empty Qdrant and Neo4j prove
nothing, and the 138 production chunks are not in the repository). So the gate
catches a regression at the moment new results are committed, which is the
moment a retrieval change is measured. It cannot catch a retrieval change that
ships without being re-measured. Closing that gap needs a seeded corpus in CI;
until then the freshness check below is what stands in for it.

**The floors** are set against ``passage2`` — the configuration production
actually runs — and not against the Stage 5 baseline, which it no longer
matches. Each floor sits roughly five points under its measured value. One
golden-set item is worth 2.9 points, so that is about two items of slack:
enough that ordinary churn does not trip the gate, tight enough that a
systematic regression does. ``passage_recall_at_5`` is the one to watch — Stage
5 identified it as the metric that gates answer quality, and a floor carried
over from the old baseline (0.50) would have let a 23-point regression through.
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from eval.schema import EVAL_DIR

RESULTS_DIR = EVAL_DIR / "results"

# The shipped configuration. Gate what production runs, not what Stage 5 froze.
DEFAULT_CONFIG = "passage2"

# metric -> (floor, measured value it was derived from)
FLOORS: dict[str, tuple[float, float]] = {
    "doc_recall_at_5": (0.84, 0.890476),
    "doc_hit_rate_at_5": (0.80, 0.857143),
    "passage_recall_at_5": (0.68, 0.733333),
    "evidence_in_context": (0.81, 0.861905),
    "mrr": (0.80, 0.850794),
}

# The stored run must still describe the pipeline the code ships, or the gate is
# measuring something nobody runs. Each entry is a key in the result's
# ``settings`` snapshot and the ``settings`` attribute it must agree with.
PRODUCTION_SETTINGS = {
    "chunks_per_document": "retrieval_chunks_per_document",
    "rerank_enabled": "rerank_enabled",
    "graph_prefer_domain_entities": "graph_prefer_domain_entities",
    "retrieval_top_k": "retrieval_top_k",
    "embedding_model": "embedding_model_name",
}


@dataclass(frozen=True)
class Breach:
    """One failed check, rendered as a line of the gate's output."""

    metric: str
    actual: float | str
    expected: float | str
    kind: str  # "floor" or "drift"

    def __str__(self) -> str:
        if self.kind == "floor":
            return f"FAIL  {self.metric:<22} {self.actual:.4f} < floor {self.expected:.4f}"
        return f"FAIL  {self.metric:<22} run has {self.actual!r}, code ships {self.expected!r}"


def result_path(config: str) -> Path:
    return RESULTS_DIR / config / "retrieval.json"


def load_result(config: str) -> dict:
    path = result_path(config)
    if not path.exists():
        raise FileNotFoundError(
            f"no stored retrieval run for {config!r} at {path}. "
            f"Generate one with: python -m eval.run retrieval --config {config}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def check_floors(result: dict, floors: dict[str, tuple[float, float]] = FLOORS) -> list[Breach]:
    """Compare the run's answerable summary against the floors."""
    summary = result["summary"]["answerable"]
    breaches = []
    for metric, (floor, _measured) in floors.items():
        actual = summary[metric]
        if actual < floor:
            breaches.append(Breach(metric, actual, floor, "floor"))
    return breaches


def check_config_drift(result: dict, settings) -> list[Breach]:
    """Fail when the stored run no longer describes what the code ships.

    A green gate over a configuration production stopped running is worse than
    no gate: it reports safety it is not measuring.
    """
    stored = result["settings"]
    breaches = []
    for key, attribute in PRODUCTION_SETTINGS.items():
        if key not in stored:
            continue
        shipped = getattr(settings, attribute)
        if stored[key] != shipped:
            breaches.append(Breach(key, stored[key], shipped, "drift"))
    return breaches


def report(config: str, result: dict, breaches: list[Breach]) -> str:
    summary = result["summary"]["answerable"]
    lines = [
        f"Retrieval gate — config {config!r}, {summary['n']} answerable items, "
        f"run {result.get('run_at', 'unknown')}",
        "",
    ]
    for metric, (floor, measured) in FLOORS.items():
        actual = summary[metric]
        mark = "ok  " if actual >= floor else "FAIL"
        lines.append(
            f"  {mark} {metric:<22} {actual:.4f}  floor {floor:.2f}  "
            f"(measured {measured:.4f} when the floor was set)"
        )
    lines.append("")
    if breaches:
        lines.append(f"{len(breaches)} check(s) failed:")
        lines.extend(f"  {b}" for b in breaches)
    else:
        lines.append("All floors met; the stored run still matches the shipped configuration.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=DEFAULT_CONFIG, help=f"stored run to gate (default: {DEFAULT_CONFIG})")
    args = parser.parse_args(argv)

    from app.core.config import settings

    result = load_result(args.config)
    breaches = check_floors(result) + check_config_drift(result, settings)
    print(report(args.config, result, breaches))
    return 1 if breaches else 0


if __name__ == "__main__":
    raise SystemExit(main())
