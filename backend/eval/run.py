"""Stage 5 evaluation runner.

    python -m eval.run retrieval --config baseline rerank_off graph_off chunk512
    python -m eval.run answers   --config baseline graph_off
    python -m eval.run rescore   --config baseline     # re-apply answer metrics, no LLM
    python -m eval.run report

Each config runs in its own subprocess (settings and in-process caches are
global). Results go to eval/results/<config>/{retrieval,answers}.{json,md};
``report`` writes eval/results/comparison.md from whatever results exist.

Retrieval metrics are deterministic for a fixed corpus and are the ones safe to
gate on. Answer metrics depend on the LLM and are reported, never enforced:
the answer command always exits 0 once it has produced results.
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from eval import metrics as m
from eval.schema import EVAL_DIR, GoldenItem, load_golden_set, load_manifest

RESULTS_DIR = EVAL_DIR / "results"
CACHE_DIR = EVAL_DIR / "cache" / "llm"
TOP_K = 5


def _git_state() -> dict:
    def git(*args):
        return subprocess.run(["git", *args], capture_output=True, text=True, cwd=EVAL_DIR).stdout.strip()
    return {"head": git("rev-parse", "--short", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


def _history(item: GoldenItem) -> list[dict] | None:
    return [turn.model_dump() for turn in item.history] or None


def _quiet_logs() -> None:
    logging.getLogger().setLevel(logging.WARNING)
    for name in ("trace", "httpx", "sentence_transformers", "neo4j", "huggingface_hub"):
        logging.getLogger(name).setLevel(logging.WARNING)


# ── retrieval ────────────────────────────────────────────────────────────────


async def evaluate_retrieval(config_name: str) -> dict:
    from app.services.query_understanding import QueryUnderstanding
    from app.services.rag_service import _extract_chunks_from_unified, _understand_turn
    from eval.pipeline import CONFIGS, Pipeline, settings_snapshot

    golden, manifest = load_golden_set(), load_manifest()
    excluded = manifest.excluded_filenames()
    pipeline = Pipeline(CONFIGS[config_name])
    await pipeline.start()
    records = []
    try:
        for item in golden.active_items():
            resolved, _ = _understand_turn(QueryUnderstanding(), item.question, _history(item))
            started = time.perf_counter()
            unified = await pipeline.retrieve(resolved.search_query)
            latency_ms = (time.perf_counter() - started) * 1000

            all_chunks = _extract_chunks_from_unified(unified)
            chunks = [c for c in all_chunks if c.document_name not in excluded]
            ranked_docs = m.unique_in_order(c.document_name for c in chunks)
            pairs = [(c.document_name, c.content) for c in chunks]
            evidence = [(e.doc, e.contains) for e in item.expected_evidence]
            facts = [f for c in unified.items for f in c.graph_facts]

            records.append({
                "id": item.id,
                "type": item.type,
                "tags": item.tags,
                "question": item.question,
                "search_query": resolved.search_query,
                "rewritten": resolved.was_rewritten,
                "follow_up_resolved": m.follow_up_resolved(resolved.search_query, item.expected_resolution),
                "expected_docs": item.expected_docs,
                "ranked_docs": ranked_docs,
                "top_chunks": [
                    {"doc": c.document_name, "chunk_index": c.chunk_index, "score": round(c.score, 6)}
                    for c in chunks[:TOP_K]
                ],
                "doc_recall_at_5": m.doc_recall_at_k(ranked_docs, item.expected_docs, TOP_K),
                "mrr": m.reciprocal_rank(ranked_docs, item.expected_docs),
                "passage_recall_at_5": m.passage_recall(pairs, evidence, TOP_K),
                "evidence_in_context": m.passage_recall(pairs, evidence, None),
                "top_score": round(chunks[0].score, 6) if chunks else None,
                "chunks_in_context": len(all_chunks),
                "excluded_fixture_chunks": len(all_chunks) - len(chunks),
                "graph_facts": len({(f.entity_name, f.relationship_type, f.related_entity) for f in facts}),
                "graph_only_items": sum(1 for i in unified.items if i.source == "graph"),
                "latency_ms": round(latency_ms, 1),
            })
    finally:
        await pipeline.close()

    return {
        "kind": "retrieval",
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": _git_state(),
        "settings": settings_snapshot(pipeline.config),
        "graph_connected": pipeline.graph_enabled,
        "summary": summarize_retrieval(records),
        "items": records,
    }


def _retrieval_block(records: list[dict]) -> dict:
    return {
        "n": len(records),
        "doc_recall_at_5": m.mean(r["doc_recall_at_5"] for r in records),
        "doc_hit_rate_at_5": m.mean(r["doc_recall_at_5"] == 1.0 for r in records),
        "passage_recall_at_5": m.mean(r["passage_recall_at_5"] for r in records),
        "evidence_in_context": m.mean(r["evidence_in_context"] for r in records),
        "mrr": m.mean(r["mrr"] for r in records),
    }


def summarize_retrieval(records: list[dict]) -> dict:
    answerable = [r for r in records if r["type"] != "negative"]
    negatives = [r for r in records if r["type"] == "negative"]
    tags = sorted({t for r in answerable for t in r["tags"]})
    latencies = [r["latency_ms"] for r in records]
    return {
        "answerable": _retrieval_block(answerable),
        "by_type": {t: _retrieval_block([r for r in answerable if r["type"] == t])
                    for t in ("single_hop", "multi_hop", "follow_up")},
        "by_tag": {t: _retrieval_block([r for r in answerable if t in r["tags"]]) for t in tags},
        "follow_up_resolution_rate": m.mean(r["follow_up_resolved"] for r in records if r["type"] == "follow_up"),
        "negative_top_score_mean": m.mean(r["top_score"] for r in negatives),
        "negative_top_score_max": max((r["top_score"] or 0) for r in negatives) if negatives else None,
        "answerable_top_score_mean": m.mean(r["top_score"] for r in answerable),
        "latency_ms_p50": m.percentile(latencies, 50),
        "latency_ms_p95": m.percentile(latencies, 95),
    }


# ── answers ──────────────────────────────────────────────────────────────────


async def evaluate_answers(config_name: str, cache_only: bool = False) -> dict:
    from eval.pipeline import CONFIGS, CacheMiss, Pipeline, settings_snapshot

    golden, manifest = load_golden_set(), load_manifest()
    corpus_names = manifest.filenames()
    pipeline = Pipeline(CONFIGS[config_name])
    await pipeline.start()
    service = await pipeline.rag_service(CACHE_DIR, cache_only=cache_only)
    records, skipped = [], []
    try:
        for item in golden.active_items():
            started = time.perf_counter()
            try:
                response = await service.query(question=item.question, history=_history(item))
            except CacheMiss:
                # cache-only mode: this prompt was never answered (e.g. Groq's
                # daily token cap was reached) - score only what exists.
                skipped.append(item.id)
                continue
            total_ms = (time.perf_counter() - started) * 1000
            pipeline.assert_not_degraded()
            if response.retrieval_source != "hybrid":
                raise RuntimeError(f"{item.id}: GraphRagService fell back to {response.retrieval_source} - aborting")
            llm = dict(pipeline.llm.last)
            pipeline.llm.last = {}

            answer = response.answer
            facts = [f.model_dump() for f in item.expected_facts]
            coverage, hits = m.fact_coverage(answer, facts)
            cited = m.cited_documents(answer, corpus_names)
            precision, recall = m.citation_precision_recall(cited, item.expected_docs)
            records.append({
                "id": item.id,
                "type": item.type,
                "tags": item.tags,
                "question": item.question,
                "answer": answer,
                "fact_coverage": coverage,
                "facts_hit": {f["fact"]: hit for f, hit in zip(facts, hits)},
                "refusal": m.refusal_outcome(answer, item.must_refuse, coverage),
                "cited_docs": sorted(cited),
                "citation_precision": precision,
                "citation_recall": recall,
                "grounding": m.grounding_summary(answer, response.citations),
                "context_docs": m.unique_in_order(c.document_name for c in response.citations),
                "graph_facts": len(response.graph_facts),
                "retrieval_source": response.retrieval_source,
                "llm_cached": llm.get("cached"),
                "llm_ms": round(llm["llm_ms"], 1) if llm.get("llm_ms") else None,
                "total_ms": round(total_ms, 1),
            })
    finally:
        await pipeline.close()

    return {
        "kind": "answers",
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": _git_state(),
        "settings": settings_snapshot(pipeline.config),
        "llm_cache": {"hits": pipeline.llm.hits, "misses": pipeline.llm.misses},
        "cache_only": cache_only,
        "skipped_uncached": skipped,
        "summary": summarize_answers(records),
        "items": records,
    }


def rescore_answers(config_name: str) -> dict:
    """Re-apply the answer metrics to stored answers - no retrieval, no LLM call.

    Grounding is kept from the original run (it needs the retrieved citations).
    """
    path = RESULTS_DIR / config_name / "answers.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    golden = {item.id: item for item in load_golden_set().active_items()}
    corpus_names = load_manifest().filenames()
    for record in result["items"]:
        item = golden[record["id"]]
        facts = [f.model_dump() for f in item.expected_facts]
        coverage, hits = m.fact_coverage(record["answer"], facts)
        cited = m.cited_documents(record["answer"], corpus_names)
        precision, recall = m.citation_precision_recall(cited, item.expected_docs)
        record.update({
            "fact_coverage": coverage,
            "facts_hit": {f["fact"]: hit for f, hit in zip(facts, hits)},
            "refusal": m.refusal_outcome(record["answer"], item.must_refuse, coverage),
            "cited_docs": sorted(cited),
            "citation_precision": precision,
            "citation_recall": recall,
        })
    result["summary"] = summarize_answers(result["items"])
    result["rescored_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    return result


def _answer_block(records: list[dict]) -> dict:
    return {
        "n": len(records),
        "fact_coverage": m.mean(r["fact_coverage"] for r in records),
        "fully_correct_rate": m.mean(r["fact_coverage"] == 1.0 for r in records),
        "false_refusal_rate": m.mean(r["refusal"] == "false_refusal" for r in records),
        "citation_precision": m.mean(r["citation_precision"] for r in records),
        "citation_recall": m.mean(r["citation_recall"] for r in records),
        "grounded_share": m.mean(r["grounding"]["grounded_share"] for r in records),
    }


def summarize_answers(records: list[dict]) -> dict:
    answerable = [r for r in records if r["type"] != "negative"]
    negatives = [r for r in records if r["type"] == "negative"]
    llm_ms = [r["llm_ms"] for r in records if r["llm_ms"]]
    return {
        "answerable": _answer_block(answerable),
        "by_type": {t: _answer_block([r for r in answerable if r["type"] == t])
                    for t in ("single_hop", "multi_hop", "follow_up")},
        "correct_refusal_rate": m.mean(r["refusal"] == "correct_refusal" for r in negatives),
        "grounding_totals": {k: sum(r["grounding"][k] for r in records) for k in ("grounded", "hedged", "unsupported")},
        "llm_ms_p50_uncached": m.percentile(llm_ms, 50),
        "llm_ms_p95_uncached": m.percentile(llm_ms, 95),
    }


# ── output ───────────────────────────────────────────────────────────────────


def _fmt(value, pct=True):
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return f"{value * 100:.1f}%" if pct else f"{value:.0f}"


def retrieval_markdown(result: dict) -> str:
    s = result["summary"]
    lines = [
        f"# Retrieval — {result['settings']['name']}",
        "",
        f"{result['settings']['description']}  ",
        f"Run {result['run_at']} · git {result['git']['head']}{' (dirty)' if result['git']['dirty'] else ''} · "
        f"collection `{result['settings']['qdrant_collection']}` · reranker {result['settings']['rerank_enabled']} · "
        f"graph {result['graph_connected']}",
        "",
        "| Slice | n | Doc recall@5 | Doc hit@5 | Passage recall@5 | Evidence in context | MRR |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    rows = [("All answerable", s["answerable"])] + list(s["by_type"].items()) + [(f"tag: {t}", b) for t, b in s["by_tag"].items()]
    for name, b in rows:
        mrr = "—" if b["mrr"] is None else f"{b['mrr']:.3f}"
        lines.append(f"| {name} | {b['n']} | {_fmt(b['doc_recall_at_5'])} | {_fmt(b['doc_hit_rate_at_5'])} | "
                     f"{_fmt(b['passage_recall_at_5'])} | {_fmt(b['evidence_in_context'])} | {mrr} |")
    lines += [
        "",
        f"- Follow-up resolution: {_fmt(s['follow_up_resolution_rate'])}",
        f"- Top score, negatives: mean {s['negative_top_score_mean']:.4f}, max {s['negative_top_score_max']:.4f}; "
        f"answerable mean {s['answerable_top_score_mean']:.4f}",
        f"- Retrieval latency: p50 {s['latency_ms_p50']:.0f} ms, p95 {s['latency_ms_p95']:.0f} ms",
        "",
        "## Per item",
        "",
        "| Id | Type | Doc R@5 | Passage R@5 | In context | MRR | Top docs |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in result["items"]:
        top = ", ".join(d.split("_")[0] for d in r["ranked_docs"][:5])
        mrr = "—" if r["mrr"] is None else f"{r['mrr']:.2f}"
        lines.append(f"| {r['id']} | {r['type']} | {_fmt(r['doc_recall_at_5'])} | {_fmt(r['passage_recall_at_5'])} | "
                     f"{_fmt(r['evidence_in_context'])} | {mrr} | {top} |")
    return "\n".join(lines) + "\n"


def answers_markdown(result: dict) -> str:
    s = result["summary"]
    a = s["answerable"]
    lines = [
        f"# Answers — {result['settings']['name']}",
        "",
        f"Run {result['run_at']} · model `{result['settings']['llm_model']}` · LLM cache hits {result['llm_cache']['hits']}, "
        f"calls {result['llm_cache']['misses']}",
        "",
        *([f"**PARTIAL (cache-only): {len(result['skipped_uncached'])} items skipped, never answered:** "
           + ", ".join(result['skipped_uncached']), ""] if result.get("skipped_uncached") else []),
        "| Slice | n | Fact coverage | Fully correct | False refusal | Citation P | Citation R | Grounded share |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, b in [("All answerable", a)] + list(s["by_type"].items()):
        lines.append(f"| {name} | {b['n']} | {_fmt(b['fact_coverage'])} | {_fmt(b['fully_correct_rate'])} | "
                     f"{_fmt(b['false_refusal_rate'])} | {_fmt(b['citation_precision'])} | {_fmt(b['citation_recall'])} | "
                     f"{_fmt(b['grounded_share'])} |")
    g = s["grounding_totals"]
    lines += [
        "",
        f"- Correct refusal on negatives: {_fmt(s['correct_refusal_rate'])}",
        f"- Grounding sentences: {g['grounded']} grounded, {g['hedged']} hedged, {g['unsupported']} unsupported",
        f"- LLM latency (uncached calls): p50 {_fmt(s['llm_ms_p50_uncached'], False)} ms, p95 {_fmt(s['llm_ms_p95_uncached'], False)} ms",
        "",
        "## Per item",
        "",
        "| Id | Type | Facts | Refusal | Cited | Grounded |",
        "| --- | --- | ---: | --- | --- | ---: |",
    ]
    for r in result["items"]:
        cited = ", ".join(d.split("_")[0] for d in r["cited_docs"]) or "—"
        lines.append(f"| {r['id']} | {r['type']} | {_fmt(r['fact_coverage'])} | {r['refusal']} | {cited} | "
                     f"{_fmt(r['grounding']['grounded_share'])} |")
    return "\n".join(lines) + "\n"


def write_result(result: dict) -> Path:
    out = RESULTS_DIR / result["settings"]["name"]
    out.mkdir(parents=True, exist_ok=True)
    kind = result["kind"]
    (out / f"{kind}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    render = retrieval_markdown if kind == "retrieval" else answers_markdown
    (out / f"{kind}.md").write_text(render(result), encoding="utf-8")
    return out


def run_single(kind: str, config: str, cache_only: bool = False) -> None:
    _quiet_logs()
    coroutine = evaluate_retrieval(config) if kind == "retrieval" else evaluate_answers(config, cache_only)
    result = asyncio.run(coroutine)
    out = write_result(result)
    print(f"{kind}/{config}: wrote {out}")


def main(argv: list[str] | None = None) -> int:
    from eval.pipeline import CONFIGS

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", choices=["retrieval", "answers", "rescore", "report"])
    parser.add_argument("--config", nargs="+", default=["baseline"], choices=sorted(CONFIGS))
    parser.add_argument("--cache-only", action="store_true",
                        help="answers: score only items with a cached LLM response; make no LLM calls")
    parser.add_argument("--in-process", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.kind == "rescore":
        for config in args.config:
            print(f"rescore/{config}: wrote {write_result(rescore_answers(config))}")
        return 0

    if args.kind == "report":
        from eval.report import write_comparison
        print(f"wrote {write_comparison(RESULTS_DIR)}")
        return 0

    if args.in_process:
        run_single(args.kind, args.config[0], args.cache_only)
        return 0

    failed = False
    for config in args.config:
        extra = ["--cache-only"] if args.cache_only else []
        proc = subprocess.run([sys.executable, "-m", "eval.run", args.kind, "--config", config, "--in-process", *extra],
                              cwd=EVAL_DIR.parent, env={**os.environ, "PROCESSING_QUEUE_WORKER_ENABLED": "false"})
        failed |= proc.returncode != 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
