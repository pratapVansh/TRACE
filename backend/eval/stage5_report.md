# TRACE — Stage 5 evaluation report

**Date:** 13 September 2026, resumed 14 September (48 further answers) and 15 September 2026
(43 further answers: rerank_off completed 40/40, chunk512 reached 39/40 before the Groq daily
cap) · **Code:** baseline at `e647562`, graph_off at `6d57238`, the 15 September runs at
`bbf5806`, each plus an uncommitted working tree · **Corpus:** frozen 25 documents / 134 chunks
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

**Three of the four answer ablations are now complete; chunk512 is one item short.** The
free tier allows 200,000 tokens per day. On 15 September the quota reset, `rerank_off`
finished with 3 further calls, and `chunk512` generated 39 of its 40 answers before the
daily cap returned at 197,749 / 200,000 — leaving only **N05**, a negative.

| Config | Answers generated | Status |
| --- | ---: | --- |
| baseline | 40 / 40 | ✅ complete (13 Sep) |
| graph_off | 40 / 40 | ✅ complete (14 Sep) — 23 cached + 17 new |
| rerank_off | **40 / 40** | ✅ **complete (15 Sep)** — 37 cached + 3 new |
| chunk512 | **39 / 40** | 🟡 **N05 only** — all 35 answerable items done; 4 of 5 negatives |

Because every answerable item is present in all four configs, the answerable metrics
(fact coverage, fully correct, citations, grounding) are directly comparable across all
four; only chunk512's 5-item negatives slice is short one item. The run stopped cleanly at
the cap as instructed; every generated answer is cached in `eval/cache/llm/` (159 files)
and chunk512 was scored with `--cache-only`, so no work was wasted and nothing was rerun.

Per-minute limits, not the daily cap, set the pace: at 512 tokens per chunk a prompt runs
≈5,200 tokens against a TPM limit of 8,000, so generation settled at roughly 1.5 answers
per minute with the runner's back-off absorbing the 429s.

### Graph on vs off — all 40 items

This is the ablation the quota blocked yesterday, now complete:

| Metric (all 40 items) | baseline | graph_off |
| --- | ---: | ---: |
| Fact coverage (35 answerable) | 72.6% | 73.6% (+1.0) |
| Fully correct | 60.0% | 62.9% (+2.9) |
| Fact coverage — single_hop | 62.5% | 64.2% (+1.7) |
| Fact coverage — **multi_hop** | 89.2% | **89.2% (no change)** |
| Fact coverage — **follow_up** | 80.0% | **80.0% (no change)** |
| False refusal | 11.4% | 11.4% |
| Correct refusal (5 negatives) | 100.0% | 100.0% (after the N04 fix) |
| Citation precision | 77.8% | 84.3% (+6.6) |
| Citation recall | 81.9% | 91.9% (+10.0) |
| Grounded sentence share | 48.8% | 60.8% (+12.0) |
| Graph facts in the prompt (mean) | 12.4 | 0 |

Across all 40 items only **three** answers changed at all once the N04 metric bug was fixed (the fourth row below is that bug):

| Item | With graph | Without graph | Reading |
| --- | --- | --- | --- |
| S18 | 2/3 facts | **3/3 facts** | the only genuine correctness change, and it favours graph-off |
| S12 | false_refusal | answered | 0 facts covered either way — label change only |
| S14 | answered | false_refusal | 0 facts covered either way — label change only |
| N04 | correct_refusal | correct_refusal | was a metric artefact; **fixed 14 Sep**, both now agree |

**N04 was a scoring artefact, and it has since been fixed (14 September).** Both answers say
the same thing: the internal inspection of B-101 was deferred, so there are no findings. The
refusal classifier matched the baseline's "no internal visual findings … **were** recorded"
but not graph-off's "no internal-inspection findings **are** recorded" — `eval/metrics.py`
listed `(were|was|have been|has been)` in its premise-correction pattern and not the present
tense. The pattern is now tense-agnostic. Checked against every cached answer in all four
configs, the fix changes **exactly one** label — graph_off N04 → `correct_refusal` — and
leaves the baseline's numbers identical. Stored answers were rescored with
`python -m eval.run rescore` (no Groq calls), so the table above already reflects it.

**Conclusion: the graph changes nothing on the questions it exists for.** All ten multi-hop
and all five follow-up answers are scored identically with and without it. One sampled run
per question, so read this as "no measurable benefit", not proof of harm.

### 3.1 Reworked graph arm (`graph_v2`) — retrieval only, 14 September

The ablation above says the graph earns nothing. Tracing why: the graph arm ranks entities
by how many query terms their *name* contains, which is a raw count, so long filenames beat
short tags. `Document` entities are 18% of the graph but took **55%** of the five entity
slots, and ~80% of the facts reaching the prompt were a bare name or a document-membership
edge — both of which the retrieved chunk already shows.

| Facts emitted over the 40 questions | before | `graph_v2` |
| --- | ---: | ---: |
| `Document` share | 59.1% | **21.2%** |
| bare "entity exists" facts | 35.3% | 30.0% |
| document-membership edges | 44.8% | 37.9% |
| **domain relationship facts** | **20.0%** | **32.1%** |
| total facts | 496 | 377 |

Three fixes, all gated on `graph_prefer_domain_entities` (default off, so this baseline
stays reproducible): rank by term *density* rather than raw count; rank documents below
domain entities; and count only relationship facts toward the merge boost. Nothing was
removed from Neo4j.

| Metric | baseline | graph_off | **graph_v2** |
| --- | ---: | ---: | ---: |
| Doc recall@5 | 91.9% | 98.6% | **98.6%** |
| Doc hit@5 | 88.6% | 97.1% | **97.1%** |
| Passage recall@5 | 56.7% | 59.5% | **59.5%** |
| MRR | 0.860 | 0.906 | **0.920** |
| Latency p50 (ms) | 6485 | 5511 | 6055 |

`graph_v2` recovers every gain that came from switching the graph off **and beats graph-off
on MRR** — the first Stage 5 result where keeping the graph is better than not having it.
S06 and M10 recover from MRR 0.17 and 0.33 to 1.00; S01 and S03 rise 0.50 → 1.00. F02 drops
1.00 → 0.50, matching graph_off exactly, but its passage recall is 0.0 in all three configs,
so the right passage was never retrieved and the rank never mattered.

**The answer-level effect of `graph_v2` is not measured** — that needs Groq, which was
paused. Retrieval improved; whether the answers follow is open.

### 3.2 Reranker on vs off — ✅ complete, all 40 items (15 September)

The 31-item partial reported on 14 September **understated the cost**. On the full set:

| Metric (all 40 items) | baseline | rerank_off |
| --- | ---: | ---: |
| Fact coverage (35 answerable) | 72.6% | **63.8% (-8.9)** |
| Fully correct | 60.0% | **48.6% (-11.4)** |
| Fact coverage — single_hop | 62.5% | 62.5% (no change) |
| Fact coverage — **multi_hop** | 89.2% | **78.2% (-11.0)** |
| Fact coverage — **follow_up** | 80.0% | **40.0% (-40.0)** |
| False refusal | 11.4% | 14.3% (+2.9) |
| Correct refusal (5 negatives) | 100.0% | **80.0% (-20.0)** |
| Citation precision | 77.8% | 75.0% (-2.8) |
| Citation recall | 81.9% | 81.4% (-0.5) |
| Grounded sentence share | 48.8% | 45.8% (-2.9) |

Turning the reranker off costs **11.4 pts of fully-correct answers** and 8.9 pts of fact
coverage — nearly double the 6.5 pts the matched subset suggested, because the nine items
added today (F02–F05, N01–N05) are exactly where it hurts most. The damage is concentrated,
not diffuse: **single-hop coverage is unchanged at 62.5%**, while multi-hop drops 11.0 pts
and **follow-up drops 40.0 pts** (F03 1.00 → 0.00, false refusal; F05 1.00 → 0.00). Questions
that need the right passage out of several candidates are the ones the reranker was doing
the work for.

The negatives are now informative and they cost the reranker-off run one: **N04 is a genuine
missed refusal.** Without the reranker the answer asserts "Status: Completed – internal
inspection of B-101 performed" and reports the external UT thickness readings as the internal
findings. The baseline, with the same documents available, says the inspection was deferred.
This is the false-premise failure the negatives exist to catch, not a scoring artefact.

### 3.3 Chunk 512 on answers — 🟡 39 / 40 (15 September)

The ablation that had no answer-level evidence at all now has it for every answerable
question. All 35 answerable items were generated; only the negative **N05** was not.

| Metric | baseline | chunk512 |
| --- | ---: | ---: |
| Fact coverage (35 answerable) | 72.6% | **79.3% (+6.7)** |
| Fully correct | 60.0% | **74.3% (+14.3)** |
| Fact coverage — **single_hop** | 62.5% | **80.0% (+17.5)** |
| Fact coverage — **multi_hop** | 89.2% | **77.5% (-11.7)** |
| Fact coverage — follow_up | 80.0% | 80.0% (no change) |
| False refusal | 11.4% | 8.6% (-2.9) |
| Correct refusal (negatives) | 100.0% (5/5) | 75.0% (3/4 scored — see below) |
| Citation precision | 77.8% | **89.8% (+12.1)** |
| Citation recall | 81.9% | 87.1% (+5.2) |
| Grounded sentence share | 48.8% | **60.6% (+11.8)** |

**The retrieval gain reaches the answers, and it is the largest answer-level effect measured
in Stage 5:** +14.3 pts fully-correct, the direct consequence of +20.5 pts passage recall and
+24.8 pts evidence-in-context. It confirms conclusion 1 from the other direction — feed the
pipeline the right passage and the same model and prompt answer correctly.

**The trade-off predicted from retrieval also shows up.** Multi-hop coverage falls 11.7 pts,
matching the −10 pts multi-document recall: **M05 drops 1.00 → 0.00 and M10 1.00 → 0.00**,
both questions needing two documents where the 512 run retrieved one. Single-hop, where one
chunk more often holds the whole answer, gains 17.5 pts. Seven single-hop items that the
baseline answered partially are now fully correct (S01, S02, S03, S10, S14, S18 among them),
and F02 — a baseline false refusal — is answered correctly.

**N04 needs review before it is read as a regression.** The classifier scored it
`missed_refusal`, but the answer's content is right: "The internal inspection of boiler B-101
has not been completed; therefore no findings inside the steam drum are available." The
premise-correction pattern in `eval/metrics.py` accepts `no … findings … are recorded` but not
`… are available`, so this is the same class of vocabulary gap as the tense bug fixed on
14 September. **It has deliberately not been fixed here** — changing the classifier would
rescore stored answers, which was out of scope for this run. It is logged as the next metric
task; until then chunk512's negatives figure should be read as "3 of 4 scored, one contested".

**No latency figures for chunk512 answers.** The generating run was interrupted by the daily
cap before it could write its results, so the run was scored from cache; `llm_ms` is null for
cached items by design. Retrieval latency (p50 7542 ms, p95 9443 ms) is unaffected and stands.

## 4. Conclusions — what actually improves TRACE

1. **Answer quality is limited by passage retrieval, not by the LLM.** When all expected
   evidence reached the context the answer covered **98%** of expected facts (17 items);
   partially, 71% (9); none, 26% (9). All four false refusals (S05, S12, S15, F02) had
   **zero** expected evidence in context — the model refused instead of inventing, which
   is the right failure. Improvements should target getting the right *passage* in, not
   the prompt or model.

2. **The reranker earns its quality — now confirmed on all 40 answers — but its cost is
   dangerous.** Turning it off loses 6.7 pts passage recall, 0.077 MRR, and 16.7 pts on
   long-document and compound questions. On the complete answer ablation that retrieval loss
   **reaches the answer, harder than the partial suggested**: fact coverage 63.8% vs 72.6%
   and fully-correct **48.6% vs 60.0% (−11.4 pts**, against the −6.5 pts estimated from 31
   items). It is concentrated where ranking matters — single-hop coverage is unchanged,
   multi-hop falls 11.0 pts, follow-up 40.0 pts — and it costs one negative to a genuine
   missed refusal (N04). The cost is **~40× the latency** (132 ms vs ~5.5 s p50) on this CPU. The
   slowest baseline query took 9.4 s against the 10 s timeout that silently disables
   reranking for the whole process; the 512-token run crossed it and did disable
   (detected, discarded, rerun with a 60 s eval-only timeout). Keep the reranker; reduce
   its candidate count or move it off CPU before deployment.

3. **The knowledge graph, as wired today, makes retrieval worse and does nothing for
   answers.** With the graph off, doc hit@5 rises from 88.6% to **97.1%** and MRR from
   0.860 to 0.906. Cause, confirmed per item: `ContextMerger` adds up to +0.1 to a chunk's
   score per attached graph fact, and entity-dense documents (MAN-003, Equipment Register,
   shift logs) collect many facts, so they are lifted above the reranker's best passage
   regardless of relevance — S05 loses PPT-002 from the top 5, S06 drops MNT-001 from rank 1
   to 6, M10 drops MNT-001 to rank 3. **The answer ablation is now complete across all 40
   items and finds no benefit either:** fact coverage 73.6% without the graph vs 72.6% with
   it, citation precision 84.3% vs 77.8%, grounded share 60.8% vs 48.8%. Decisively, **all
   ten multi-hop and all five follow-up answers score identically** with and without it —
   the graph changes nothing on exactly the questions it was added for. Only three answers
   differ at all, and the one real correctness change (S18, 2/3 → 3/3 facts) favours
   graph-off; the apparent negatives regression (N04) was a refusal-classifier tense gap,
   since fixed. **This conclusion is about the graph as it was wired on 13 September.** The
   score boost has since been reworked — see §3.1 — and at the retrieval level the
   reworked graph now beats having no graph at all (MRR 0.920 vs 0.906). Whether that
   reaches the answers is not yet measured.

4. **Larger chunks are the biggest single lever in Stage 5 — now measured on answers, and
   the trade-off is real.** 512/64 raises passage recall@5 by **20.5 pts** and
   evidence-in-context by 24.8, because one chunk more often holds the whole answer. That
   reaches the answers: fact coverage **79.3% vs 72.6%** and fully-correct **74.3% vs 60.0%
   (+14.3 pts)** — the largest answer-level gain measured in Stage 5, and single-hop coverage
   rises 17.5 pts. It costs 2.9 pts doc recall and **10 pts multi-document recall**, and that
   cost is now visible in the answers too: **multi-hop coverage drops 11.7 pts**, with M05 and
   M10 falling from fully correct to zero. Add 16% more reranker latency and an embedding
   model (`all-MiniLM-L6-v2`, 256-wordpiece window) that silently truncates every 512-token
   chunk. The right next move is therefore **not** a flat switch to 512: it is to keep the
   recall gain while restoring multi-document coverage — a larger chunk with an embedding
   model whose window fits it, or retrieval that returns more than one document's chunk.

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
- **One answer call outstanding** (Groq daily cap of 200,000 tokens): graph_off **40/40 ✅**,
  rerank_off **40/40 ✅**, chunk512 **39/40** — only the negative **N05** remains
  (≈5,200 tokens). Every answerable item exists in all four configs, so the answerable
  metrics are fully comparable; only chunk512's negatives slice is short one item. Resume
  with `python -m eval.run answers --config chunk512`; cached answers are reused, and
  `--cache-only` scores whatever has been generated without calling Groq.
- **The answer-level effect of `graph_v2` is still unmeasured** — 40 calls (≈136,000 tokens),
  deliberately not run on 15 September so the day's quota went to closing the three baseline
  ablations. It is the next tracked step.
- **A second refusal-classifier vocabulary gap is open and unfixed** (chunk512 N04, §3.3):
  the premise-correction pattern accepts "no findings … are **recorded**" but not "… are
  **available**". Fixing it would rescore stored answers, so it was left for a separate
  change; chunk512's negatives figure is reported as 3 of 4 scored with one contested.
- **Lexical scoring.** Fact coverage and refusal detection are phrase/regex based; they were
  checked against every low-scoring answer and two artefacts were fixed (markdown emphasis,
  premise-correction refusals), but paraphrased correct answers can still be missed.
  **A third artefact was found and fixed on 14 September:** the premise-correction
  pattern accepted `(were|was|have been|has been) recorded` but not the present tense, so
  graph_off's N04 ("no internal-inspection findings **are** recorded") scored
  `missed_refusal` while the baseline's past-tense wording of the same content scored
  `correct_refusal`. The pattern is now tense-agnostic; the fix moves exactly one label
  across all four configs and leaves the baseline unchanged. 8 tests cover it.
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
