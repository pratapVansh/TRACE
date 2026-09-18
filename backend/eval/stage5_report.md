# TRACE — Stage 5 evaluation report

**Date:** 13 September 2026, resumed 14 September (48 further answers), 15 September
(43 further answers: rerank_off completed 40/40, chunk512 reached 39/40 before the Groq daily
cap) and **16 September 2026 — Stage 5 closed**: chunk512's last answer (1 call) and the
full `graph_v2` answer run (40 calls) were generated, a third refusal-classifier wording gap
and one fact-phrasing gap were fixed, and every config was rescored. · **Code:** baseline at
`e647562`, graph_off at `6d57238`, the 15 September runs at
`bbf5806`, each plus an uncommitted working tree · **Corpus:** frozen 25 documents / 134 chunks
(`corpus_manifest.yaml`) · **Question set:** 40 reviewed items (`golden_set.yaml`)

Every number below comes from `eval/results/*/*.json`; the tables are reproduced from
`eval/results/comparison.md`, which `python -m eval.run report` generates. Nothing was
typed in by hand except the interpretation.

> **The answer tables below are the 16 September scoring and have been superseded twice.**
> `eval/results/comparison.md` is the current source; regenerate it rather than quoting
> this file. What moved, in both cases because scoring was corrected and never because a
> pipeline changed: (1) **17 September**, the empty-answer retry regenerated the 3 empty
> generations — baseline coverage 72.6% → 74.0%, chunk512 80.7% → 84.7%, chunk512
> multi-hop 77.5% → 91.5%; (2) **18 September**, the F05 alias gap was fixed
> (`golden_set.yaml`: "operating hours" had been missing beside "running hours"), which
> credited three correct answers that had scored zero — **chunk512** coverage 84.7% →
> **87.6%**, fully-correct 80.0% → **82.9%**, follow-up 80.0% → **100.0%**; **rerank_off**
> coverage 63.8% → **66.6%**, fully-correct 48.6% → **51.4%**, follow-up 40.0% → **60.0%**.
> The baseline, graph_off, graph_v2 and passage2 answer numbers are unchanged by (2).
> None of this changes a Stage 5 conclusion: the reranker still earns its cost, larger
> chunks are still the biggest single lever, and the graph still does not move answers.

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

| Metric | baseline | rerank_off | graph_off | chunk512 | graph_v2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Doc recall@5 | 91.9% | 88.6% (-3.3) | **98.6% (+6.7)** | 89.0% (-2.9) | **98.6% (+6.7)** |
| Doc hit@5 | 88.6% | 82.9% (-5.7) | **97.1% (+8.6)** | 82.9% (-5.7) | **97.1% (+8.6)** |
| Passage recall@5 | 56.7% | 50.0% (-6.7) | 59.5% (+2.9) | **77.1% (+20.5)** | 59.5% (+2.9) |
| Evidence in LLM context | 61.4% | 54.3% (-7.1) | 61.4% | **86.2% (+24.8)** | 61.4% |
| MRR | 0.860 | 0.783 | 0.906 | 0.853 | **0.920** |
| Doc recall@5 — multi_hop | 91.7% | 80.0% (-11.7) | 95.0% (+3.3) | 81.7% (-10.0) | 95.0% (+3.3) |
| Passage recall@5 — long_doc | 55.6% | 38.9% (-16.7) | 55.6% | 77.8% (+22.2) | 55.6% |
| Passage recall@5 — compound | 61.1% | 44.4% (-16.7) | 61.1% | 76.4% (+15.3) | 61.1% |
| Passage recall@5 — no_lexical_overlap | 0.0% | 0.0% | 25.0% | 50.0% | 25.0% |
| Passage recall@5 — table_row | 69.0% | 71.4% | 69.0% | 69.0% | 69.0% |
| Retrieval latency p50 (ms) | 6485 | **132** | 5511 | 7542 | 6055 |
| Retrieval latency p95 (ms) | 8402 | **170** | 6356 | 9443 | 6690 |

**All five configurations are now complete at 40 / 40.** The free tier allows 200,000 tokens
per day. On 16 September the quota reset and the two outstanding runs were made in the order
the roadmap fixed — the cheap one first, so a quota exhaustion could not strand it again:

| Config | Answers generated | Status |
| --- | ---: | --- |
| baseline | 40 / 40 | ✅ complete (13 Sep) |
| graph_off | 40 / 40 | ✅ complete (14 Sep) — 23 cached + 17 new |
| rerank_off | 40 / 40 | ✅ complete (15 Sep) — 37 cached + 3 new |
| chunk512 | **40 / 40** | ✅ **complete (16 Sep)** — 39 cached + **1 new** (N05) |
| `graph_v2` | **40 / 40** | ✅ **complete (16 Sep)** — 0 cached + **40 new**, as predicted |

**41 Groq calls closed Stage 5**, and 159 of the 200 answers came from the cache untouched.
`graph_v2` reused nothing, which was expected and correct: the LLM cache keys on the complete
request, and `graph_v2` exists precisely to change the graph facts in the prompt, so all 40
keys were new. Every answer is cached in `eval/cache/llm/` (200 files).

Every item is now present in every config, so **all answer metrics are directly comparable
across all five**, negatives included.

Per-minute limits, not the daily cap, set the pace throughout: at 512 tokens per chunk a
prompt runs ≈5,200 tokens against a TPM limit of 8,000, so the 15 September generation settled
at roughly 1.5 answers per minute with the runner's back-off absorbing the 429s. The
16 September `graph_v2` run held ≈2 answers per minute on 256-token chunks and finished its
40 calls inside the day's quota.

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

**The answer-level effect was measured on 16 September and it is nil — see §3.4.** Retrieval
improved; the answers did not follow. `graph_v2` moves which *document* ranks first while
leaving evidence-in-context at 61.4%, identical to the baseline, so the passages reaching the
prompt never change.

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

### 3.3 Chunk 512 on answers — ✅ complete, 40 / 40 (16 September)

The one outstanding negative, **N05**, was generated on 16 September for a single Groq call.
It is a correct refusal — the answer states that the documents do not contain the set
pressure of PSV-3011 — so chunk512's negatives are **5 / 5** and the config is complete.

| Metric | baseline | chunk512 |
| --- | ---: | ---: |
| Fact coverage (35 answerable) | 72.6% | **80.7% (+8.1)** |
| Fully correct | 60.0% | **77.1% (+17.1)** |
| Fact coverage — **single_hop** | 62.5% | **82.5% (+20.0)** |
| Fact coverage — **multi_hop** | 89.2% | **77.5% (-11.7)** |
| Fact coverage — follow_up | 80.0% | 80.0% (no change) |
| False refusal | 11.4% | 8.6% (-2.9) |
| Correct refusal (negatives) | 100.0% (5/5) | **100.0% (5/5)** |
| Citation precision | 77.8% | **89.8% (+12.1)** |
| Citation recall | 81.9% | 87.1% (+5.2) |
| Grounded sentence share | 48.8% | **60.6% (+11.8)** |

*(Coverage and fully-correct are 1.4 and 2.8 pts above the 15 September figures. That is the
S17 fact-phrasing fix in §3.6, not new generation — no chunk512 answer was regenerated.)*

**The retrieval gain reaches the answers, and it is the largest answer-level effect measured
in Stage 5:** +14.3 pts fully-correct, the direct consequence of +20.5 pts passage recall and
+24.8 pts evidence-in-context. It confirms conclusion 1 from the other direction — feed the
pipeline the right passage and the same model and prompt answer correctly.

**The multi-hop trade-off is NOT what it looked like on 15 September — correction.** The
15 September reading was that multi-hop coverage falls 11.7 pts because "M05 drops
1.00 → 0.00 and M10 1.00 → 0.00, both questions needing two documents where the 512 run
retrieved one." **That causal claim was wrong, and the check that exposed it is in §3.5:
chunk512's M05 and M10 answers are both empty strings — the model produced no text at all.**
They score 0.00 because nothing was generated, not because the wrong passage was retrieved.
The retrieval record contradicts the original reading directly for M05: doc recall 1.0 and
passage recall 0.5, **identical to the baseline**. Only M10 shows the predicted retrieval
degradation (doc recall 0.5, passage recall 0.0), and even there the answer was never
generated, so the answer-level drop cannot be attributed to it.

Excluding the items where any config produced an empty answer, **chunk512's multi-hop
coverage is 96.9% against the baseline's 86.5%** — better, not worse (§3.5). The −11.7 pts in
the table above is an artefact of two empty generations. The −10 pts multi-document *recall*
cost is real and still stands as a retrieval result; what does not stand is the claim that it
was measured reaching the answers. Single-hop, where one
chunk more often holds the whole answer, gains 17.5 pts. Seven single-hop items that the
baseline answered partially are now fully correct (S01, S02, S03, S10, S14, S18 among them),
and F02 — a baseline false refusal — is answered correctly.

**N04 was a classifier artefact, and it has since been fixed (16 September).** The answer's
content was always right: "The internal inspection of boiler B-101 has not been completed;
therefore no findings inside the steam drum are available." The premise-correction pattern in
`eval/metrics.py` accepted `no … findings … are recorded` but not `… are available` — the same
class of vocabulary gap as the tense bug fixed on 14 September, and it was scoring identical
content differently. The participle list now matches the vocabulary the sibling
"not … in the documents" pattern already used (`available|provided|listed` added). Checked
against **every** stored answer in all four configs, the fix moves **exactly one** label —
chunk512 N04 → `correct_refusal` — and leaves the baseline, graph_off and rerank_off
byte-identical, summaries included. Stored answers were rescored with
`python -m eval.run rescore` (no Groq calls), so the table above already reflects it.
chunk512's negatives are now **5 of 5 correct**, N05 included.

**This did not paper over the reranker's genuine miss.** rerank_off's N04 — which asserts the
inspection *was performed* and reports external UT readings as internal findings — remains
`missed_refusal` after the fix. The two failures look alike in the summary table and are not:
one is a wording gap, the other is a model accepting a false premise.

**Latency for chunk512 answers rests on a single call.** 39 of the 40 answers were served
from cache, where `llm_ms` is null by design, so the only timed call is N05 — which is why the
p50 and p95 in `comparison.md` are both 2287 ms. Treat that as one sample, not a distribution.
Retrieval latency (p50 7542 ms, p95 9443 ms) is measured on all 40 and stands.

### 3.4 `graph_v2` on answers — ✅ complete, 40 / 40 (16 September)

The open question Stage 5 was holding for this run: **the reworked graph arm clearly improves
retrieval ranking — does that reach the answers?** It was run exactly as planned, 40 calls,
nothing reusable from cache, ≈20 minutes of wall clock inside the day's quota.

**The answer is no.**

| Metric (all 40 items) | baseline | graph_off | **graph_v2** |
| --- | ---: | ---: | ---: |
| Fact coverage (35 answerable) | 72.6% | 73.6% (+1.0) | **70.7% (-1.9)** |
| Fully correct | 60.0% | 62.9% (+2.9) | **57.1% (-2.9)** |
| Fact coverage — single_hop | 62.5% | 64.2% (+1.7) | 62.5% (no change) |
| Fact coverage — multi_hop | 89.2% | 89.2% (no change) | 82.5% (-6.7) |
| Fact coverage — follow_up | 80.0% | 80.0% (no change) | 80.0% (no change) |
| Correct refusal (5 negatives) | 100.0% | 100.0% | **100.0%** (after the N04 fix in §3.6) |
| False refusal | 11.4% | 11.4% | 11.4% (no change) |
| Citation precision | 77.8% | 84.3% (+6.6) | 79.8% (+2.0) |
| Citation recall | 81.9% | 91.9% (+10.0) | 86.7% (+4.8) |
| Grounded sentence share | 48.8% | 60.8% (+12.0) | 49.1% (+0.4) |
| Graph facts in the prompt (mean) | 12.4 | 0 | 9.4 |

**Read the -1.9 and -2.9 with care: they are not a measured regression.** Across all 40 items
`graph_v2` and the baseline differ on exactly **three** answers, and only one of the three is
about content:

| Item | baseline | `graph_v2` | Reading |
| --- | --- | --- | --- |
| S12 | false_refusal | answered | 0 facts covered either way — label change only, favours `graph_v2` |
| S14 | answered (**empty answer**) | false_refusal | the baseline produced no text at all here (§3.5); 0 facts either way |
| M10 | 1.00 facts | 0.33 facts | **`graph_v2`'s answer is truncated mid-sentence** (§3.5) — a generation artefact, not retrieval: passage recall is 0.67 in both configs and `graph_v2`'s MRR is higher |

Remove the items where any config failed to produce a complete answer and the two configs are
**identical** — 73.2% coverage and 59.4% fully correct each, multi-hop 86.5% each (§3.5).

**So the conclusion for `graph_v2` is the same one graph_off produced, and it is now the third
independent measurement of it: the graph changes retrieval, and nothing the graph does reaches
the answers.** What `graph_v2` *did* fix is real and stands at the retrieval level — it undoes
the harm the original wiring was doing (doc hit@5 88.6% → 97.1%, MRR 0.860 → 0.920, and it is
430 ms/query *faster* than the baseline). It simply does not convert.

**Why it does not convert is visible in the retrieval numbers, and it is consistent with
conclusion 1.** `graph_v2` improves *document* ranking (doc hit@5, MRR) but leaves
**passage recall@5 at 59.5% and evidence-in-context at 61.4% — the latter identical to the
baseline**. The answers are gated by whether the right *passage* reaches the prompt, and
`graph_v2` moves which document ranks first without changing which passages arrive. chunk512,
which raises evidence-in-context by 24.8 pts, is the config that moves the answers.

**Decision, against the criterion set before the data was seen.** The roadmap fixed the test
in advance: *"the question being whether the retrieval gain reaches the answers. Only then
decide whether `graph_prefer_domain_entities` should become the default."* It does not reach
the answers, so the criterion is not met and **the flag stays off by default**. The graph
itself stays on — the chosen configuration is the baseline, graph included (§8).

### 3.5 Empty and truncated generations — the artefact that was being read as a result

Three of the 200 answers are **empty strings**: the model returned no text at all. They score
0.00 fact coverage, which is indistinguishable in every summary table from an answer that was
generated and was wrong — and on 15 September two of them were read as a retrieval result.

| Config | Empty answers |
| --- | --- |
| baseline | S14 |
| chunk512 | **M05, M10** |
| rerank_off, graph_off, `graph_v2` | none |

The cause is known and was already recorded for baseline S14: `max_tokens=1024`, with
`gpt-oss-120b` spending the budget on reasoning before emitting anything. The same ceiling
truncates answers mid-sentence without emptying them — `graph_v2`'s M10 stops at *"flagged
moderate scaling on the hot side of"* after 206 characters, which is why it scores 0.33
instead of 1.00. Between 2 and 6 answers per config end without terminal punctuation.

`summarize_answers` now lists `empty_answers` in every result file and the runner prints the
line, so this can no longer be mistaken for a content failure.

**Sensitivity check.** Excluding the three items that any config left empty (S14, M05, M10),
scored on the same 32 answerable items for every config:

| Config | Coverage (35) | Coverage (32) | Fully correct (35) | Fully correct (32) | multi_hop (10) | multi_hop (8) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 72.6% | 73.2% | 60.0% | 59.4% | 89.2% | 86.5% |
| rerank_off | 63.8% | 63.8% | 48.6% | 50.0% | 78.2% | 80.2% |
| graph_off | 73.6% | 74.2% | 62.9% | 62.5% | 89.2% | 86.5% |
| **chunk512** | 80.7% | **85.2%** | 77.1% | **81.2%** | 77.5% | **96.9%** |
| `graph_v2` | 70.7% | 73.2% | 57.1% | 59.4% | 82.5% | 86.5% |

Two readings change, and both matter:

1. **chunk512's multi-hop "trade-off" disappears.** 77.5% → **96.9%**, against the baseline's
   86.5%. The −11.7 pts reported on 15 September was two empty generations, not two failed
   multi-document retrievals. The −10 pts multi-document *recall* cost is a real retrieval
   result and still stands; the claim that it had been measured reaching the answers does not.
2. **`graph_v2` is not below the baseline.** 70.7% → 73.2%, exactly the baseline's 73.2%.

**This is a post-hoc exclusion on 32 of 35 items, so it is a sensitivity check, not the
headline.** Dropping 2 of 10 multi-hop items is a large proportional change and the direction
of the correction happens to favour chunk512. The measured-as-run numbers stay primary
throughout this report. What the check establishes is narrower and safe: the two specific
causal claims above cannot be supported, because the answers they rest on were never
generated. Re-running the three items would settle it for ~15,000 tokens and is the first
thing to do with the next day's quota.

### 3.6 Two scoring fixes on 16 September (no Groq calls)

Both are the same class of lexical artefact as the two fixed on 14 and 16 September, both
were found by reading the answers behind the numbers, and both were verified against **every**
stored answer in **all five** configs before being applied. Together they move **exactly
three** records and leave baseline, rerank_off and graph_off **byte-identical**.

**1. A third wording of the one premise correction** (`eval/metrics.py`). `graph_v2`'s N04
answers the false premise correctly — *"the internal inspection of boiler B-101 was deferred
to the next shutdown; therefore the documents contain no findings from inside the steam
drum"* — but put the verb **in front of** the noun. The pattern was built around a trailing
participle (`no findings … were recorded`, widened on 14 Sep to any tense and on 16 Sep to
`available|provided|listed`), so it could not see this third form, and the reworked graph arm
appeared to lose a negative it had nothing to do with. A sibling pattern now matches
`<corpus> contains/lists/includes no <record-noun>`. The subject must be the corpus and the
object a record-shaped noun, for the same reason the existing pattern restricts its nouns:
*"the inspection report contains no defects"* is a substantive answer and must not match.
**Moves one label:** `graph_v2` N04 → `correct_refusal`.

**2. One missing accepted phrasing** (`eval/golden_set.yaml`, S17). chunk512 and `graph_v2`
both answer *"the defined minimum stock level is 2 units"* — correct, and against a golden set
that already accepted `minimum stock is 2` and `minimum level of 2` but not the two words
together. Added `minimum stock level is/of/: 2`, following the precedent already recorded in
that item's own review notes, where `minimum required stock: 2` was added for the same reason
after the baseline run. Wording only — the value and the source row are unchanged.
**Moves two records:** chunk512 S17 and `graph_v2` S17, 0.50 → 1.00 coverage.

A full audit backs the claim that these were the only two: every fact scored *missed* in every
config was re-checked against its answer text, and S17 was the only one where the answer
states the fact. All the rest are genuine — S12 answers 12.4 mm where the golden value is
12.9 mm, S18 gives 45 kW for a 45 A current limit, M08 cites a 2.8 mm/s limit that does not
exist.

**Neither fix papered over a genuine failure.** rerank_off's N04 — which asserts the
inspection *was performed* and reports external UT readings as internal findings — is still
`missed_refusal` after both fixes. That is the distinction the negatives exist to draw: a
wording gap in the scorer versus a model accepting a false premise.

**6 new tests** (43 in `tests/test_eval_metrics.py`, was 37), including the real `graph_v2`
N04 phrasing and two further guards — *"the inspection report contains no defects"* and
*"the turnaround report documents no cracking on the shell"* — that must **not** classify as
refusals. Stored answers were rescored with `python -m eval.run rescore` across all five
configs; no Groq calls.

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

3. **The graph changes retrieval and does not reach the answers — measured three ways.**
   *As originally wired* it made retrieval **worse**: `ContextMerger` added up to +0.1 per
   attached graph fact, so entity-dense documents (MAN-003, the Equipment Register, the shift
   logs) were lifted over the reranker's best passage regardless of relevance — S05 loses
   PPT-002 from the top 5, S06 drops MNT-001 from rank 1 to 6, M10 drops MNT-001 to rank 3.
   Turning it off raised doc hit@5 from 88.6% to 97.1% and MRR from 0.860 to 0.906.
   *Reworked* (`graph_v2`, §3.1) it is now the **best retrieval configuration measured**:
   doc hit@5 97.1%, **MRR 0.920** — above graph-off — and 430 ms/query faster than the
   baseline. **But at the answer level all three configurations are the same.** graph_off:
   all ten multi-hop and all five follow-up answers score identically to the baseline.
   `graph_v2`: identical to the baseline once the three incomplete generations are excluded
   (73.2% coverage, 59.4% fully correct, 86.5% multi-hop — each equal to the baseline), with
   the only genuine difference being one truncated answer. **The reason is visible and
   consistent with conclusion 1:** the graph moves *document* ranking, while
   **evidence-in-context stays at 61.4% — identical to the baseline** — so the passages
   reaching the prompt do not change, and neither do the answers. Keep the graph (it is a
   product feature and, reworked, it costs nothing at retrieval); do not expect answer
   quality from it, and do not promote `graph_prefer_domain_entities` to default on this
   evidence.

4. **Larger chunks are the biggest single lever in Stage 5, and the trade-off is smaller
   than it looked.** 512/64 raises passage recall@5 by **20.5 pts** and evidence-in-context by
   **24.8 pts**, because one chunk more often holds the whole answer. That reaches the
   answers, and it is the largest answer-level effect measured in Stage 5: fact coverage
   **80.7% vs 72.6%** and fully-correct **77.1% vs 60.0% (+17.1 pts)**, with single-hop
   coverage up 20.0 pts. **The multi-hop regression reported on 15 September does not hold
   up** (§3.3, §3.5): chunk512's M05 and M10 answers are empty strings, so the −11.7 pts was
   two generations that never happened, not two failed retrievals — M05's retrieval is
   *identical* to the baseline's. Excluding the incomplete items, chunk512's multi-hop
   coverage is **96.9% against the baseline's 86.5%**. What remains real is the **retrieval**
   cost: −2.9 pts doc recall and **−10 pts multi-document recall**, plus 16% more reranker
   latency and an embedding model (`all-MiniLM-L6-v2`, 256-wordpiece window) that silently
   truncates every 512-token chunk. So the next move is still not a flat switch to 512 — the
   embedding window is the blocker, and it is now the clearest single lever in the codebase:
   a larger chunk with an embedding model whose window fits it, or retrieval that returns more
   than one chunk per document. Confirm the multi-hop reading by regenerating the three
   incomplete answers first (~15,000 tokens).

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
| S14 | Groq returned an **empty answer** (reasoning consumed `max_tokens=1024`). The user would see nothing. Two more in chunk512 (M05, M10) and a truncated M10 in `graph_v2` — §3.5. **The single most actionable defect in Stage 5:** it is a config value, it hits real users, and it corrupted two conclusions. | LLM / config |
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
- **All five configs are complete at 40/40**; nothing in Stage 5 is now blocked on quota.
  41 Groq calls were spent on 16 September (1 for chunk512 N05, 40 for `graph_v2`); 159 of the
  200 answers came from cache and none were regenerated.
- **Three answers were never generated** (S14 baseline; M05 and M10 chunk512) and several more
  are truncated by `max_tokens=1024` (§3.5). They score 0.00 like a wrong answer, and on
  15 September two of them were misread as a retrieval result. Every slice containing S14,
  M05 or M10 should be read with the sensitivity table in §3.5 beside it. Regenerating the
  three costs ~15,000 tokens and is the first call on the next day's quota.
- **`graph_v2`'s answer effect is measured and is neutral** (§3.4): identical to the baseline
  on the 32 items every config answered completely. Its retrieval gain is real (MRR 0.920,
  doc hit@5 97.1%, 430 ms/query faster); it does not convert, because evidence-in-context is
  unchanged at 61.4%. `graph_prefer_domain_entities` therefore stays **off** by default.
- **One sample per question, and the differences that decide the graph question are small.**
  `graph_v2` vs baseline comes down to three items out of forty, two of which cover zero facts
  either way. "No measurable difference" is the honest reading; it is not proof of equivalence,
  and a multi-sample run would be needed for that.
- **The third refusal-classifier gap and one fact-phrasing gap are closed** (§3.6, both
  16 September). Verified against every stored answer in all five configs: together they move
  exactly three records and leave baseline, rerank_off and graph_off byte-identical. 6 new
  tests (43 in the metrics file). A full audit of every missed fact in every config found no
  other scoring artefact — the remaining misses are genuine.
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

Qdrant and Neo4j run as containers and must be up first; the runner reaches them on
`127.0.0.1` from the host, not from inside the compose network:

```
docker start trace-qdrant-1 trace-neo4j-1
cd backend
python -m eval.validate                                   # 0 errors required
python -m eval.validate --collection eval_chunks_512      # evidence against the 512 collection
python -m eval.chunk512                                   # only for the 512 ablation
python -m eval.run retrieval --config baseline rerank_off graph_off chunk512 graph_v2
python -m eval.run answers   --config baseline            # Groq; cached in eval/cache/llm
python -m eval.run answers   --config graph_v2 --cache-only   # dry run, no Groq calls
python -m eval.run rescore   --config baseline rerank_off graph_off chunk512 graph_v2  # no LLM
python -m eval.run report                                 # eval/results/comparison.md
```

**All 200 answers are cached**, so every table in this report rebuilds from
`rescore` + `report` with **no Groq calls at all**. Only a prompt change (new config, changed
retrieval, changed chunking) produces new cache keys and needs quota.

## 8. Chosen configuration and what Stage 6 inherits

**Chosen: the baseline pipeline, unchanged — hybrid search + cross-encoder reranker + graph,
256/40 chunks, `graph_prefer_domain_entities` off.** Nothing in production changes as a result
of Stage 5. Each part of that is a decision, not a default:

| Component | Decision | Evidence |
| --- | --- | --- |
| Cross-encoder reranker | **Keep, and treat its latency as a deployment blocker** | Removing it costs 11.4 pts fully-correct, 8.9 pts coverage, 40 pts on follow-up and one negative to a genuine missed refusal (§3.2). It costs ~40× latency, and the slowest query (9.4 s) is inside the 10 s timeout that silently disables it |
| Knowledge graph | **Keep enabled** | It is a product feature and, reworked, it is the best retrieval configuration measured (§3.1). Measured three ways, it does not change answers (§3.4) |
| `graph_prefer_domain_entities` | **Stays off by default; `graph_v2` code kept, gated, unchanged** | The criterion fixed in advance — does the retrieval gain reach the answers — is not met (§3.4). The flag makes promoting it a one-line change if a later measurement supports it |
| Chunk size | **Stays 256/40 for now** | 512/64 is the largest answer-level gain in Stage 5 (+17.1 pts fully correct) but costs 10 pts multi-document recall and is read through a 256-wordpiece embedding window that truncates it (§3.3, conclusion 4). Switching needs the embedding model changed first |
| `max_tokens` | **Raise it — the one code change Stage 5 clearly earns** | 1024 produced 3 empty and several truncated answers across 200 generations (§3.5), a defect that reaches real users and that corrupted two Stage 5 conclusions. Deliberately not changed here: it would invalidate all 200 cached answers and needs a fresh quota day |

**What Stage 6 (CI) can gate on.** The retrieval metrics only — they are deterministic and
reran identically twice. Suggested floors from the measured baseline, set below it so normal
variation does not trip them: doc recall@5 ≥ 0.85, MRR ≥ 0.80, passage recall@5 ≥ 0.50.
**Answer metrics must stay reported and never gate:** they need Groq, they carry one-sample
noise, and the `max_tokens` truncation above puts a floor under how reproducible they can be.

**Ranked next steps, by measured leverage.**

1. Raise `max_tokens` and regenerate the three empty answers (~15,000 tokens) — confirms or
   overturns the corrected multi-hop reading in §3.5.
2. Fit the embedding window to the chunk size, then re-run the 512 ablation. This is where
   the +17.1 pts sits, and conclusion 1 says passage recall is what gates answers.
3. Move the reranker off CPU or cut its candidate count before any deployment.
4. LLM-as-judge (step 7) — still not implemented; only worth building with a larger budget.

`--cache-only` is the no-quota mode throughout: it scores only what has already been
generated and raises `CacheMiss` for the rest, so it doubles as a dry run that exercises
retrieval, prompting and config resolution without spending a token.
