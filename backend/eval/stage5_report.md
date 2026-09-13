# TRACE — Stage 5 evaluation report

**Date:** 13 September 2026 (answer ablation resumed 19:52–20:00, stopped at the Groq daily cap) · **Code:** `main` at `e647562` plus uncommitted working tree
(including the Stage 4.5 graph fix) · **Corpus:** frozen 25 documents / 134 chunks
(`corpus_manifest.yaml`) · **Question set:** 40 reviewed items (`golden_set.yaml`)

Every number below comes from `eval/results/*/*.json`; the tables are reproduced from
`eval/results/comparison.md`, which `python -m eval.run report` generates. Nothing was
typed in by hand except the interpretation.

---

## 1. What was measured and how

| | |
| --- | --- |
| Path under test | The Copilot answer path, `GraphRagService.query`: query understanding → `HybridRetriever` (Qdrant hybrid search → cross-encoder rerank → one chunk per document, 10 docs) + graph facts → `ContextMerger` → prompt → Groq `openai/gpt-oss-120b`. Built in-process exactly as `app/main.py` builds it. `ChatService` is never used, so nothing is written to conversations, memory or the user graph. |
| Stores | PostgreSQL native (read only), Qdrant and Neo4j in Docker. Production collection `document_chunks` (138 points) untouched; the 512 ablation uses a separate `eval_chunks_512` collection. |
| Warm-up | Reranker and embedding model warmed and one throwaway retrieval run before any timing. The runner **aborts** if the reranker disables itself mid-run or the service falls back to vector-only. |
| Retrieval metrics (deterministic) | Doc recall@5, doc hit@5 (all expected docs present), **passage recall@5** (expected evidence text in a top-5 chunk of the right document), evidence-in-context (in any chunk passed to the LLM), MRR, follow-up resolution, top score on negatives. |
| Answer metrics (LLM, reported only) | Fact coverage (accepted phrasings, number-boundary aware), fully-correct rate, refusal outcome (correct / missed / false refusal), citation precision/recall (documents named in the answer), grounded-sentence share (TRACE's own lexical classifier). |
| Reproducibility | Baseline retrieval was run twice: **all 40 items and every metric identical**; only latency differed. LLM responses are cached on the full request hash. |
| Excluded | 4 test-fixture documents are still indexed; they are dropped from retrieval scoring (they occupied 22 context slots across the 40 baseline queries). |

## 2. Baseline

**Retrieval** (35 answerable items): doc recall@5 **91.9%**, doc hit@5 88.6%,
**passage recall@5 56.7%**, evidence in LLM context 61.4%, MRR 0.860, follow-up
resolution 100%.

**Answers** (all 40 items, one run): fact coverage **72.6%**, fully correct **60.0%**,
false refusal **11.4%** (4 items), correct refusal on negatives **100%** (5/5),
citation precision 77.8% / recall 81.9%, grounded-sentence share 48.8%.

| Slice | Passage recall@5 | Fact coverage | Fully correct |
| --- | ---: | ---: | ---: |
| single_hop (20) | 55.0% | 62.5% | 50.0% |
| multi_hop (10) | 68.3% | 89.2% | 70.0% |
| follow_up (5) | 40.0% | 80.0% | 80.0% |

**Latency** (CPU laptop, single process): retrieval p50 **5.3–6.5 s**, p95 **6.7–8.4 s**
across the two baseline runs; slowest single retrieval 9.4 s. LLM p50 2.7 s, p95 5.5 s
(uncached calls, excluding 429 back-off). End to end roughly **8–14 s** per question.

## 3. Ablations

| Metric | baseline | rerank_off | graph_off | chunk512 |
| --- | ---: | ---: | ---: | ---: |
| Doc recall@5 | 91.9% | 88.6% (-3.3) | **98.6% (+6.7)** | 89.0% (-2.9) |
| Doc hit@5 | 88.6% | 82.9% (-5.7) | **97.1% (+8.6)** | 82.9% (-5.7) |
| Passage recall@5 | 56.7% | 50.0% (-6.7) | 59.5% (+2.9) | **77.1% (+20.5)** |
| Evidence in LLM context | 61.4% | 54.3% (-7.1) | 61.4% | **86.2% (+24.8)** |
| MRR | 0.860 | 0.783 | **0.906** | 0.853 |
| Doc recall@5 — multi_hop | 91.7% | 80.0% (-11.7) | 95.0% (+3.3) | 81.7% (-10.0) |
| Passage recall@5 — long_doc | 55.6% | 38.9% (-16.7) | 55.6% | 77.8% (+22.2) |
| Passage recall@5 — compound | 61.1% | 44.4% (-16.7) | 61.1% | 76.4% (+15.3) |
| Passage recall@5 — no_lexical_overlap | 0.0% | 0.0% | 25.0% | 50.0% |
| Passage recall@5 — table_row | 69.0% | 71.4% | 69.0% | 69.0% |
| Retrieval latency p50 (ms) | 6485 | **132** | 5511 | 7542 |
| Retrieval latency p95 (ms) | 8402 | **170** | 6356 | 9443 |

**Answer-level ablations are incomplete — blocked by the Groq daily token cap.** The free
tier allows 200,000 tokens per day (≈3,400 per answer call, so ≈58 calls).

| Config | Answers generated | Status |
| --- | ---: | --- |
| baseline | 40 / 40 | complete (session 1) |
| graph_off | **23 / 40** | 18 in session 1 until the cap; 5 more at 19:52–20:00 before the cap was hit again (Groq: 197,382 of 200,000 used) |
| rerank_off | 0 / 40 | not started — no quota |
| chunk512 | 0 / 40 | not started — no quota |

Groq's window is rolling: about two hours after the first cap only enough had freed for
five calls (≈17,000–20,000 tokens), and the bulk of the quota — used by the answer runs
between roughly 16:50 and 17:50 on 13 September — frees again only about 24 hours later. The resumed run therefore stopped as instructed; all generated
answers are cached and will be reused.

On the 23 items answered in both configs (S01–S20, M01–M03), every config scored on the
same items, cache hits 23/23 (identical prompts, so retrieval had not drifted):

| Metric (23 matched items) | baseline | graph_off |
| --- | ---: | ---: |
| Fact coverage | 67.4% | 68.8% (+1.4) |
| Fully correct | 56.5% | 60.9% (+4.3) |
| False refusal | 13.0% | 13.0% |
| Citation precision | 75.4% | 88.1% (+12.7) |
| Citation recall | 84.8% | 89.1% (+4.3) |
| Grounded sentence share | 49.2% | 58.1% (+8.9) |
| Graph facts in the prompt (mean) | 12.0 | 0 |

Only one item changed its fact coverage: S18 rose from 2/3 to 3/3 facts without the graph.
S12 and S14 swapped refusal labels but covered 0 facts in both configs. Removing ~12 graph
facts from every prompt therefore left answer correctness essentially unchanged, while the
answers named fewer irrelevant documents (citation precision +12.7) and more of their
sentences were grounded in the retrieved passages (+8.9). One sampled run per question —
read this as "no evidence the graph helps answers", not as proof that removing it improves
them. Multi-hop (7 of 10 unanswered), follow-up and negative items were not reached, so
the graph's effect on exactly the questions it is meant to help is still unmeasured.

## 4. Conclusions — what actually improves TRACE

1. **Answer quality is limited by passage retrieval, not by the LLM.** When all expected
   evidence reached the context the answer covered **98%** of expected facts (17 items);
   partially, 71% (9); none, 26% (9). All four false refusals (S05, S12, S15, F02) had
   **zero** expected evidence in context — the model refused instead of inventing, which
   is the right failure. Improvements should target getting the right *passage* in, not
   the prompt or model.

2. **The reranker earns its quality but its cost is dangerous.** Turning it off loses
   6.7 pts passage recall, 0.077 MRR, and 16.7 pts on long-document and compound
   questions — but it is **~40× the latency** (132 ms vs ~5.5 s p50) on this CPU. The
   slowest baseline query took 9.4 s against the 10 s timeout that silently disables
   reranking for the whole process; the 512-token run crossed it and did disable
   (detected, discarded, rerun with a 60 s eval-only timeout). Keep the reranker; reduce
   its candidate count or move it off CPU before deployment.

3. **The knowledge graph, as wired today, makes retrieval worse.** With the graph off,
   doc hit@5 rises from 88.6% to **97.1%** and MRR from 0.860 to 0.906. Cause, confirmed
   per item: `ContextMerger` adds up to +0.1 to a chunk's score per attached graph fact,
   and entity-dense documents (MAN-003, Equipment Register, shift logs) collect many facts,
   so they are lifted above the reranker's best passage regardless of relevance — S05
   loses PPT-002 from the top 5, S06 drops MNT-001 from rank 1 to 6, M10 drops MNT-001 to
   rank 3. On answers there is no measurable benefit: on the 23 matched items, fact
   coverage is 68.8% without the graph vs 67.4% with it, and citation precision is higher
   without it (88.1% vs 75.4%). The graph is not yet paying for Neo4j; the score boost
   should be removed or reworked and re-measured — including on the multi-hop and
   follow-up items the quota did not reach — before claiming otherwise.

4. **Larger chunks are the biggest single retrieval lever — with a trade-off.** 512/64
   raises passage recall@5 by **20.5 pts** and evidence-in-context by 24.8, with the
   largest gains on long-document (+22), compound (+15) and follow-up (+60) questions,
   because one chunk more often holds the whole answer. It costs 2.9 pts doc recall and
   **10 pts multi-document recall** (M02, M10 lose a document), 16% more reranker latency,
   and the embedding model (`all-MiniLM-L6-v2`, 256-wordpiece window) silently truncates
   every 512-token chunk. Its answer-level effect was **not measured** (no quota). Given
   conclusion 1 it is the most promising change to test next, not one to adopt on these
   numbers alone. The same applies to the reranker: its answer-level value is inferred from
   retrieval plus conclusion 1, not measured.

5. **Refusal cannot come from retrieval scores.** Reranker top scores for three negatives
   (N03, N04, N05) were 0.94–1.00 because a closely related document exists; negatives
   averaged 0.643 against 0.609 for answerable questions. A similarity threshold would
   not separate them. Refusal worked (5/5) only because the LLM read the evidence.

## 5. Strongest failures

| Item | What happened | Class |
| --- | --- | --- |
| S05 (probe G5) | "control system vendor / safety instrumented layer" never retrieves PPT-002 ("DCS / SIS") → false refusal. Still the probe's run-1 failure. | no lexical overlap |
| S12 (probe L3) | Plain-language question never retrieves the thickness table row; model refused rather than give the prose value 12.4 mm. | table row |
| S11 (probe L2) | Torque table not retrieved for the compound question; model said the torque "is not provided". | compound |
| S03 | MNT-003 ranked 2nd but one-chunk-per-document kept chunk 0; the Y-strainer is in chunk 1. Model answered from MAN-003 (flush the seal chamber) — wrong recommendation. | dedup / passage |
| S14 | Groq returned an **empty answer** (likely reasoning consumed `max_tokens=1024`). The user would see nothing. | LLM / config |
| S18 | Answer gave "45 kW" (P-101 motor power) for the motor current limit "45 A" — value confusion across documents. | distractor |
| M08 | Model invented a "2.8 mm/s generic alert limit" and labelled it an assumption; the SOP limit is 4.5 mm/s. | hallucination (flagged) |
| F02 | Resolver rewrote "they" as "B-101" (only appended P-401); minimum-flow passage not retrieved → false refusal. | follow-up resolution |

## 6. Limitations

- **Small synthetic corpus.** 25 LLM-generated documents from one fictional plant; 22 are
  about one page. Percentages move 2.9 pts per answerable question.
- **Question set provenance.** Drafted by Claude; S01–S10 decided item by item by the
  project owner; S11–S40 and the four replacements were reviewed by Claude against the
  source files under the owner's delegation and recorded as `reviewed_by: pratapVansh`.
  Every decision is in `review.notes`. A cold, independent human review would be stronger.
- **One LLM sample per question.** Answer metrics carry sampling noise (temperature 0.1).
- **Answer ablations incomplete** (Groq daily cap of 200,000 tokens, rolling): graph_off
  23/40, rerank_off 0/40, chunk512 0/40 — about 97 calls (≈330,000 tokens) still to go,
  i.e. at least two more days of free-tier quota. Resume with
  `python -m eval.run answers --config graph_off rerank_off chunk512`; cached answers are
  reused, and `--cache-only` scores whatever has been generated without calling Groq.
- **Lexical scoring.** Fact coverage and refusal detection are phrase/regex based; they were
  checked against every low-scoring answer and two artefacts were fixed (markdown emphasis,
  premise-correction refusals), but paraphrased correct answers can still be missed.
- **Latency** measured on a CPU laptop that ran out of memory once during the session;
  treat absolute values as indicative, ratios as reliable.
- **Chunk-512 ablation** used a 60 s reranker timeout (eval only); at the production 10 s it
  disables reranking on this hardware.

## 7. Reproducing

```
cd backend
python -m eval.validate                                   # 0 errors required
python -m eval.chunk512                                   # only for the 512 ablation
python -m eval.run retrieval --config baseline rerank_off graph_off chunk512
python -m eval.run answers   --config baseline            # Groq; cached in eval/cache/llm
python -m eval.run rescore   --config baseline graph_off  # re-apply answer metrics, no LLM
python -m eval.run report                                 # eval/results/comparison.md
```
