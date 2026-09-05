# Retrieval probe — TRACE

Five runs. The first three use the same 10 questions on a corpus of 22 short
documents; run 4 adds three genuinely long documents and three questions written
against them; run 5 fixes the OCR page segmentation those documents exposed.
Questions are never revised once written.

| | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 (current) |
|---|---|---|---|---|---|
| `chunk_size` / `chunk_overlap` | 512 / 64 | 256 / 40 | 256 / 40 | 256 / 40 | 256 / 40 |
| Chunks in corpus | 24 / 22 docs | 52 / 22 docs | 52 / 22 docs | 136 / 29 docs | **138 / 29 docs** |
| `RETRIEVAL_SIMILARITY_THRESHOLD` | 0.25 | 0.0 | 0.0 | 0.0 | 0.0 |
| Document dedup in the Copilot path | none | none | **yes** | yes | yes |
| **Score** | 9 / 10 | 10 / 10 | 10 / 10 | 13 / 13† | **13 / 13**† |
| Tag questions | 3 / 3 | 3 / 3 | 3 / 3 | 3 / 3 | 3 / 3 |
| Trap top score (lower is better) | 0.0049 | 0.0015 | 0.0015 | 0.0015 | 0.0015 |
| Median correct score, short docs | 0.0091* | 0.0068 | 0.0068 | 0.0068 | 0.0068 |
| Median correct score, long docs | — | — | — | 0.1671 | 0.1671 |
| Scanned-table markers recovered | — | — | — | 9 / 18 | **17 / 18** |
| Correct answers scoring above the trap | 6 / 8 | 7 / 8 | 7 / 8 | 7 / 8 | 7 / 8 |

† 13/13 counts a question right when the expected *document* reaches the top 5.
Two of the three long-document questions return a passage that cannot answer
them; see *Limitation: retrieval scores whole questions against whole passages*.
The headline overstates real performance.

\* Run 1's median is over the 8 answers it found; runs 2–4 found 9. The sets
differ, so the short-document medians are not strictly like for like — run 2
recovered a ninth answer scoring 0.0000, which pulls the median down rather than
reflecting worse ranking.

**Path under test:** `VectorRetriever.retrieve()` called in-process — Qdrant hybrid search (dense + BM25, RRF fusion) followed by cross-encoder rerank (`cross-encoder/ms-marco-MiniLM-L-6-v2`).
**LLM:** not involved. No call to `/api/chat`, `/api/chat/stream` or `/api/rag/query`. This measures retrieval only.
**Corpus:** runs 1–3, the 22 short indexed documents. Run 4, those plus the three
long documents described below — 29 documents, 136 chunks. Test fixtures
(`WALKTEST*`, `FAILTEST*`, integration-test uploads) are filtered from results
throughout; `FIX1*` fixtures remain in the index and appear in a few run 4 rows.
**top_k:** 5 — over-fetched to 13, test-junk filenames filtered out, then truncated to 5.

Scoring throughout: right = expected file in top 5; wrong = absent; weak = present but ranked 4th or 5th. Trap: right = nothing above threshold.

---

# Run 5 — OCR page segmentation fixed (current)

`--psm 3` → `--psm 11` in `processing/ocr/engine.py`. One line. The scanned
permit's gas test table, every data row of which run 4 silently lost, now
survives ingestion.

## Before and after, same page, same binary

| Configuration | Values recovered | Intact rows | OCR secs |
|---|---:|---:|---:|
| **`--psm 3` + threshold (run 4, shipped)** | **0 / 8** | 0 / 5 | 0.5 |
| **`--psm 11` + threshold (run 5, current)** | **8 / 8** | 0 / 5 | 0.8 |
| `--psm 6` + threshold | 4 / 8 | 1 / 5 | 1.0 |
| `--psm 4` + threshold | 0 / 8 | 0 / 5 | 0.8 |

Across all three pages the marker count went from **9/18 to 17/18**, for
+0.3 s per page.

## Re-ingestion of SCN-003

Re-queued without deleting its chunks first, relying on the replace-not-append
fix from item 4 — which also re-verified that fix on a real document.

```
BEFORE: chunks = 6   text_len = 2596
AFTER:  chunks = 8   text_len = 2649   extraction = pymupdf+tesseract

06:45  time present, reading 20.9 present
09:00  time present, reading 20.8 present
11:00  time present, reading 20.9 present
13:00  time present, reading 20.7 present
15:00  time present, reading 20.9 present
PASS count in text: 5  (expected 5)
```

All five rows recovered. The detector serial also corrected itself, from
`ASX-88214` to the true `A5X-88214`.

## What is still not recovered: row structure

PSM 11 is sparse-text mode. It finds the glyphs PSM 3 discarded precisely
because it performs no layout analysis — and the same property means it emits
roughly one cell per line, so a time and its reading are no longer on the same
row. Every value from the table is now in the index; their association into rows
is not.

```
extracted lines containing a gas-test time:
    06:45
    ‘(09:00
    11:00
    13:00
    15:00
```

The chunk text reads `06:45 20.9 PASS A. Gupta` only because adjacent lines were
concatenated in the right order, which happens to be correct here and is not
guaranteed. The LEL, H₂S and CO columns — mostly zeros, with a `1` and a `4` in
the 13:00 row — did not survive at all.

No thresholded configuration preserves rows: PSM 6 manages 1 of 5 and loses half
the values. Perfect rows were only ever obtained at PSM 6 on the raw render, and
that path is disqualified below. **This is a narrower, honest residual: values
present but unstructured, rather than the run 4 failure of values silently
absent.**

## `_adaptive_threshold` stays, and the measurement says so

`--psm 11` alone is sufficient. Thresholding was suspected because it was the
single stage that destroyed the digits at PSM 3, but at PSM 11 it is not
implicated — and removing it is actively worse. Page 2, PSM 11 throughout:

| Scan condition | Threshold on | Threshold off | Verdict |
|---|---:|---:|---|
| as generated | **12 / 12** in 0.7 s | 11 / 12 in 1.1 s | threshold better |
| faded toner | 12 / 12 in 0.8 s | 12 / 12 in 1.1 s | tie, threshold faster |
| uneven illumination | 12 / 12 in 0.8 s | 12 / 12 in 1.2 s | tie, threshold faster |
| heavy noise | 0 / 12 in 4.9 s | **did not complete in 730 s** | both bad, off is unusable |

Thresholding wins or ties on every condition and is faster on all of them,
because a binarised page gives Tesseract far less to do. On the heavy-noise
variant, removing it made a single page exceed **twelve minutes** without
finishing — sparse-text mode on an unbinarised noisy image generates an enormous
number of candidate components. Making it conditional would trade a fixed, small
cost for an unbounded one.

Heavy noise is a genuine weak spot for the pipeline as a whole: thresholding
returns 0/12 there. That is a separate problem from the one fixed here, it was
not introduced by this change, and it needs a real noisy scan rather than a
synthetic one to tune against.

## No regression

All 13 probe questions re-run. Every rank and every score **byte-identical** to
run 4:

```
G1 1/0.0279  G2 1/0.0068  G3 1/0.0050  G4 3/0.0110  G5 5/0.0000  G6 1/0.0001
T1 1/0.3008  T2 1/0.0068  T3 1/0.9459  X1 trap 0.0015
L1 1/0.1443  L2 1/0.4967  L3 1/0.1671
hits on 12 answerable: 12/12
```

The prose OCR result that scored 0.9975 in run 4 scores **0.9951** and remains at
rank 1 — the difference is the re-OCR'd text, not a ranking change.

A new query for the recovered readings — *"What oxygen readings were logged
during the hot work on the ethylene transfer line, and who took them?"* — returns
the permit at rank 1 but at **0.0118**, and returns the page-1 header chunk
rather than the table chunk. The data is now in the index; a naturally-phrased
question still does not reach it. That is the deferred retrieval limitation
above, not an OCR problem, and it is why the OCR fix alone does not make this
data usable through Copilot.

---

# Run 4 — long documents

Three genuinely long documents were added to the corpus and three questions written against them. Everything before this point was measured on 22 documents of roughly 1,100 characters each, which cannot say anything about chunking.

## What was added

| Document | Words | Structure | Extraction | Chunks |
|---|---:|---|---|---:|
| `MAN-003_HPX4000_Boiler_Feed_Pump_Manual.docx` | 7,444 | 34 numbered sections, 9 appendices, 22 tables, 243 table rows | python-docx | **53** |
| `INS-004_Turnaround_Inspection_Report_E-301.docx` | 2,416 | 15 sections, 7 tables, 12 numbered photograph references | python-docx | **21** |
| `SCN-003_Hot_Work_Permit_and_Gas_Test_Record.pdf` | — | 3-page permit form rendered to images with photocopier noise and skew, **zero selectable text** | **pymupdf+tesseract** | **6** |

The corpus went from 52 chunks over 22 documents to **136 chunks over 29 documents**.

**Extraction is sound.** The concern was a 30-page manual collapsing to 3 chunks; it produced 53, from 47,390 extracted characters, at 62–328 tokens each. The scanned PDF genuinely exercised the OCR path — `extraction_method` reads `pymupdf+tesseract`, and it is the only document in the corpus carrying a `page_number` on every chunk.

`section_title` is now populated on 52 of 53 manual chunks and 20 of 21 report chunks. It was null everywhere before, because a single-chunk document has no heading preceding it.

## Score

| Metric | Run 3 | Run 4 |
|---|---|---|
| **Original 10** | 10 / 10 | **10 / 10** |
| **New long-document 3** | — | **3 / 3, all at rank 1** (but see the limitation below) |
| **Total** | 10 / 10 | **13 / 13** |

Every original question returned an identical rank and an identical score to run 3. Adding 84 chunks of unrelated long-form technical content displaced nothing.

## The headline: scores behave completely differently on real-length documents

| Question set | Median score of the correct answer |
|---|---:|
| Original 9 answerable, short documents | 0.0068 |
| New 3, long documents | **0.1671** |

Individually: L1 **0.1443**, L2 **0.4967**, L3 **0.1671**, against a short-document median of 0.0068 — a 20× to 70× difference.

L3 was rewritten after its first run: the original wording was answerable from
the prose that interprets the table, so it never exercised the table at all. The
rewrite demands values present only in table rows. It still returns the prose
chunk — see the limitation below. Every number here is from the rewritten run. Targeted follow-up queries scored higher still: a direct read of the fastener torque table returned **0.9669**, the monitoring-limits table **0.8761**, and the OCR'd permit acceptance limits **0.9975**, the highest score recorded anywhere in this exercise.

This confirms the run 1 diagnosis and explains why the earlier numbers were so poor. `ms-marco-MiniLM` is a passage reranker. Given a whole 1,100-character document opening with a letterhead, most of the text is irrelevant to any given query and the pair scores low. Given a focused passage from a long document, it scores the way it was trained to.

**It also means the threshold decision should be revisited later.** The `0.0` default was right for a corpus of tiny documents where hits and misses overlapped. On long documents the separation is wide — correct answers at 0.14 to 0.99 against a noise floor of 0.0001 to 0.006. A threshold becomes viable on a predominantly long-form corpus. It must not be re-enabled while short documents remain, because it would silence them.

## Full results, the three new questions

### L1

> If a feed pump is going to sit idle for months, how often should someone turn the shaft over by hand, and why does it matter where it stops?

**Expected:** `MAN-003_HPX4000_Boiler_Feed_Pump_Manual.docx`

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.1443 | `MAN-003_HPX4000_Boiler_Feed_Pump_Manual.docx` **← expected** |
| 2 | 0.0002 | `LOG-001_Morning_Shift_15-Jul-2026.txt` |
| 3 | 0.0001 | `INC-001_Pump_Oil_Leakage_P-101.docx` |
| 4 | 0.0001 | `SOP-002_Pump_Shut-Down_Procedure.docx` |
| 5 | 0.0001 | `SOP-001_Pump_Start-Up_Procedure.docx` |

### L2

> Fitting a new bearing to the feed pump - how hot can we take it during the shrink fit, and what does the locknut get tightened to?

**Expected:** `MAN-003_HPX4000_Boiler_Feed_Pump_Manual.docx`

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.4967 | `MAN-003_HPX4000_Boiler_Feed_Pump_Manual.docx` **← expected** |
| 2 | 0.0061 | `INC-001_Pump_Oil_Leakage_P-101.docx` |
| 3 | 0.0006 | `MNT-002_Bearing_Replacement_P-101.docx` |
| 4 | 0.0005 | `PPT-001_Monthly_Safety_Training_Jul2026.pptx` |
| 5 | 0.0002 | `MAN-001_Centrifugal_Pump_Manual.docx` |

### L3

> On the E-301 shell survey, what thickness did the north bottom position measure this time round, and what had it been eight years earlier?

**Expected:** `INS-004_Turnaround_Inspection_Report_E-301.docx`

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.1671 | `INS-004_Turnaround_Inspection_Report_E-301.docx` **← expected** |
| 2 | 0.0048 | `INS-001_Pressure_Vessel_Inspection_T-501.docx` |
| 3 | 0.0006 | `LOG-002_Night_Shift_15-16-Jul-2026.txt` |
| 4 | 0.0001 | `Maintenance_Schedule.xlsx` |
| 5 | 0.0001 | `LOG-001_Morning_Shift_15-Jul-2026.txt` |

## Limitation: retrieval scores whole questions against whole passages

**This is the strongest finding in the exercise and it is not fixed.**

Both long-document questions that were written to be hard failed in the same
way, and neither failure is caused by chunking or by document dedup. Each scores
as *right* — the correct document is at rank 1 — while the passage actually
returned cannot answer the question. Document-level scoring hides passage-level
failure.

### Shape 1: a compound question buries the passage answering its second half

L2 needs two facts from two sections of the same manual:

- section 21, **chunk 24** — heat the bearing to a maximum of 120 °C
- section 24, **chunk 28** — bearing locknut KM17 tightened to 210 Nm

Retrieval returns chunk 24 at 0.4967 and never surfaces chunk 28.

| Query | Rank of chunk 28 | Score |
|---|---:|---:|
| L2 as asked, both halves | **22nd** | 0.000083 |
| The torque half asked alone | **4th** | 0.100131 |

**A 1,200× score difference on the same passage, from the same index, depending
only on whether the question also asks something else.**

### Shape 2: a natural question loses the table to prose about the table

L3 was rewritten specifically to require values that exist only in table rows —
the A3 row `North, bottom | 13.6 | 12.9 | 0.7 | 0.088` of the E-301 thickness
survey. Retrieval returns **chunk 13**, the prose paragraph discussing a
*different* grid position (B3), which contains none of the requested numbers.
The table itself is chunk 12.

| Query | Rank of chunk 12 | Score |
|---|---:|---:|
| L3 as asked, in plain language | **20th** | 0.000088 |
| Naming the grid and the table explicitly | **1st** | 0.217502 |

**A 2,470× score difference on the same passage.**

### Why, and why the obvious suspects are innocent

The cross-encoder scores one query against one passage as wholes. Two
consequences follow:

- When a query carries two requirements and a passage satisfies one, the
  unsatisfied half drags the pair score down. The passage matching the first
  requirement wins decisively; passages matching the second are scored against
  the entire question, most of which they do not address, and collapse into the
  noise floor.
- When a query is phrased in natural language and the answer lives in a bare
  table row, the two share almost no surface. Prose that merely *discusses* the
  topic outranks the table that *contains* the answer.

Document dedup was the expected culprit and is **not** the cause. Re-running both
queries with dedup disabled leaves the answer-bearing chunk absent in each case:

```
L2, dedup OFF -> freed slots fill with manual chunks 14 and 2, not 28
L3, dedup OFF -> freed slots fill with report chunks 2, 11 and 0, not 12
```

Keep-best is a *second* barrier standing behind this one — had either chunk
ranked third, dedup would have discarded it, because a higher-scoring chunk from
the same document already held the slot. But fixing dedup alone fixes neither
question.

### What would fix it

**Query decomposition.** Split a multi-part question into its parts, retrieve for
each independently, and merge. That addresses shape 1 directly. Shape 2 needs
either the same treatment with a table-aware sub-query, or table rows serialised
into sentence-shaped text at ingestion so a natural question has something to
match against.

**Deferred.** Decomposition adds an LLM call ahead of every retrieval, changing
both latency and cost on the hot path, and it changes what every consumer of the
RAG path receives. That is exactly the kind of change that needs the evaluation
harness in place first, so the improvement can be measured rather than assumed.
The probe in this file is the beginning of that harness, not a substitute for it.

### How to spot this in the wild

Both questions score as hits under the probe's rule — expected file in the top 5.
Only reading the returned passage reveals that it cannot support an answer. Any
future scoring of this probe should assert on the **passage**, not the document:
check that the retrieved chunk actually contains the expected value. The current
13/13 overstates real performance by at least these two questions.


## OCR silently dropped a table, and it is a bug, not a limit

> **Fixed in run 5.** The investigation below stands as the diagnosis; the
> one-line change and its verification are in run 5 at the top of this file.

Page 2 of the scanned permit carries a five-row gas test record — the readings
the permit exists to capture. Tesseract recovered the section heading, the
detector serial and the column headers, and **not one data row**. The document
reported `indexed`, six chunks, no warning anywhere.

It is not a Tesseract limit. Same page, same binary, sweeping the page
segmentation mode and the preprocessing pipeline:

| Configuration | Times recovered | Readings recovered |
|---|---:|---:|
| **`--psm 3` + preprocessing (shipped)** | **0 / 5** | **0 / 3** |
| `--psm 6` + preprocessing | 3 / 5 | 1 / 3 |
| `--psm 11` + preprocessing | **5 / 5** | **3 / 3** |
| `--psm 12` + preprocessing | **5 / 5** | **3 / 3** |
| `--psm 3`, raw render | 4 / 5 | 3 / 3 |
| `--psm 6`, raw render | **5 / 5** | **3 / 3** |

The shipped configuration is the only one that loses the table completely, and
it is the worst of both contributing causes.

### Root cause: `_adaptive_threshold`

Adding the preprocessing stages one at a time, holding `--psm 3` constant:

| Pipeline stage | Times | Readings |
|---|---:|---:|
| grayscale only | 4 / 5 | 3 / 3 |
| + `_normalize_dpi` | 4 / 5 | 3 / 3 |
| + `_denoise` | 4 / 5 | 3 / 3 |
| **+ `_adaptive_threshold`** | **0 / 5** | **0 / 3** |
| + `_auto_rotate` (full pipeline) | 0 / 5 | 0 / 3 |

The loss is total and happens at a single step. `_adaptive_threshold`
(`processing/ocr/preprocessing.py`) uses a fixed kernel; against small tabular
digits sitting inside ruled cells it destroys the glyphs, while leaving the
larger body text legible — which is why the failure looks like "tables don't OCR"
rather than "OCR is broken".

`--psm 3` compounds it. Automatic page segmentation treats the ruled table as
layout to be analysed and discards the region; the sparse-text modes 11 and 12
do not attempt layout analysis and read every glyph they find.

### What would fix it, and what it costs

Measured across all three pages, counting recovery of 18 known markers:

| Option | Markers recovered | OCR time, 3 pages |
|---|---:|---:|
| shipped: `--psm 3` + preprocessing | 9 / 18 | 2.5 s |
| **`--psm 11` + preprocessing** | **17 / 18** | **2.5 s** |
| `--psm 6`, no preprocessing | 17 / 18 | 3.0 s |
| `--psm 3`, no preprocessing | 15 / 18 | 3.2 s |

**Changing `--psm 3` to `--psm 11` costs nothing measurable and recovers 9 to 17
of 18 markers.** It is a one-line change in `processing/ocr/engine.py`.

Removing or reworking `_adaptive_threshold` recovers as much but costs about 20
per cent more OCR time, because thresholding also downscales.

Neither is applied here — this is a report, and a change to OCR configuration
affects every scanned document ingested, so it belongs behind the evaluation
harness with a before-and-after on a set of real scans rather than one synthetic
permit. What is **not** deferrable is the silence: a page whose table vanished
should not report `indexed` with no signal. The engine already computes a mean
word confidence and `OCR_MIN_CONFIDENCE` already exists in configuration; nothing
currently surfaces either.


## What changed in the caveats with this run

Run 4 is the first result here that says anything at all about chunking. The three documents are still synthetic and still written by the same model that wrote the questions, so the vocabulary-overlap bias described below still applies. But they are structurally real — numbered sections, tables spanning many rows, appendices, photograph cross-references, and in one case genuine scanner noise — and the manual is 40× the size of anything previously in the corpus. Retrieval chose between 24 candidates in run 1 and now chooses between 136.

---

# Run 3 — document dedup in the Copilot path

No retrieval-quality change was expected or observed; this run exists to record
that the dedup fix did not cost anything.

`hybrid_retriever` had no document dedup, so once documents produced several
chunks the same document appeared repeatedly in the top 5 — 10 duplicate rows
across the 10 questions. `retriever_service` deduped but trimmed to `top_k`
*before* collapsing, so asking for 5 returned 4. Both paths now rerank the full
candidate set, collapse to the best chunk per document, then trim, so `top_k`
counts documents.

| Measure | Run 2 | Run 3 |
|---|---:|---:|
| Duplicate rows across all questions | 10 | **0** |
| Questions returning a full 5 rows | 8 / 10 | **10 / 10** |
| `/api/rag/retrieve` at `top_k=5` | 4, 4, 5 results | **5, 5, 5** |
| Hits on the 9 answerable | 9 | 9 |
| Score of every correct answer | — | identical to run 2 |

Every rank and every score was unchanged. Dedup altered which documents filled
the list, not the ranking of what survived: G1 collapsed `SOP-003` (0.0279 and
0.0060) to the better chunk and pulled `LOG-002` into the freed slot; G3, G6 and
T2 behaved the same way, G6 collapsing two separate pairs.

---

# Run 2 — chunk_size 256

## Score

| Metric | Result |
|---|---|
| **Overall** | **10 / 10** |
| **Tag questions** | **3 / 3** |
| General questions | 6 / 6 |
| Trap question | 1 / 1 |
| Weak (correct doc at rank 4 or 5) | 1 (G5) |

## Per-question, against run 1

| Q | Rank @512 | Rank @256 | Score @512 | Score @256 | Change |
|---|---:|---:|---:|---:|---|
| G1 | 1 | 1 | 0.0375 | 0.0279 | 0.7× |
| G2 | 1 | 1 | 0.0053 | 0.0068 | 1.3× |
| G3 | 1 | 1 | 0.0112 | 0.0050 | 0.4× |
| G4 | 3 | 3 | 0.0070 | 0.0110 | 1.6× |
| G5 | **miss** | 5 | — | 0.0000 | recovered in rank only |
| G6 | 1 | 1 | 0.0001 | 0.0001 | 1.0× |
| T1 | 1 | 1 | 0.2117 | 0.3008 | 1.4× |
| T2 | 1 | 1 | 0.0033 | 0.0068 | 2.1× |
| T3 | 1 | 1 | 0.6998 | 0.9459 | 1.4× |
| X1 (trap) | miss | miss | 0.0049 | 0.0015 | 3.3× better |

Hits, of the 9 answerable: **8 → 9**. Median correct score: 0.0091 → 0.0068, over
different sets — run 2 found a ninth answer scoring 0.0000, which lowers the
median without any ranking getting worse. Treat the medians as indicative only.

## Did the absolute scores recover? Partly, and not evenly.

The honest answer is **no, not in the way that would let a threshold work again.**

What did improve, and clearly: the strong signals got stronger (T3 0.70 → 0.95, T1 0.21 → 0.30, T2 and G4 roughly doubled), and the no-answer control got weaker (0.0049 → 0.0015, a 3.3× widening of the gap). Correct answers now outscore the trap 7 of 8 times, up from 6 of 8.

What did not improve: the median did not rise, and the weak signals stayed weak. G6 still scores `0.0001` while ranking its document first. G3 got worse. A threshold that admitted G6 would still admit almost anything.

So the ordering is better and the separation is better, but the score remains an ordering signal rather than a calibrated relevance. The `0.0` default from the previous fix stays correct.

### Why 256 and not smaller

Candidate sizes were scored offline against the real cross-encoder before committing to a re-index:

| chunk_size | chunks | hits /9 | median correct | trap top | correct ≥ trap |
|---:|---:|---:|---:|---:|---:|
| 512 | 35 | 8 | 0.0112 | 0.0049 | 6/8 |
| 320 | 47 | 9 | 0.0070 | 0.0054 | 5/9 |
| **256** | **54** | **9** | **0.0068** | **0.0015** | **7/9** |
| 192 | 60 | 9 | 0.0053 | 0.0011 | 7/9 |
| 128 | 87 | 8 | **0.1203** | 0.0014 | **8/8** |

128 looks the strongest on paper — a 17× better median and clean separation. It was not chosen, for three reasons. It drops a hit and materially weakens two questions that need surrounding context (G3 0.0112 → 0.0033, T1 0.2117 → 0.0806). Part of its gain is the known short-passage bias of ms-marco rather than better relevance. And tuning to 87 chunks of a 22-document synthetic corpus is exactly the overfitting this report's own caveats warn about. 256 is a standard passage size that wins on every axis without those risks; revisit once the corpus contains genuinely long documents.

## Run 2 — what still fails

**G5 is not fixed, despite now scoring as a hit.** It appears at rank 5 with a score of `0.0000`. That is a ranking artifact, not retrieval — the four documents above it also score ~0.0000, so the ordering among them is noise. Chunking cannot fix G5: the question says "control system vendor" and "safety instrumented layer" where the document says `DCS` and `SIS`, and no chunk boundary creates that association. It missed at 512, it misses meaningfully at 256, and it missed again at 128. This is the embedding model's vocabulary gap and needs either a better embedding model or query expansion over an acronym glossary.

Counted as *right (weak)* under the stated rules, but it should be read as a miss.

## Run 2 — a new problem that smaller chunks exposed

With multiple chunks per document, the top 5 now contains **the same document more than once**: G1 has `SOP-003` at ranks 1 and 2, G3 has `MNT-003` at 1 and 2, G6 has `MNT-001` at 1 and 3, T2 has `INS-001` at 1 and 2.

`retrieval_dedup_documents` defaults to `True`, but it is only applied in `retriever_service`. `hybrid_retriever` — the path Copilot uses — has no dedup, so the Copilot sources panel will now show duplicate documents where it previously could not, because every document was a single chunk. This is a pre-existing gap that the chunking change made visible. Not fixed here; it is outside the scope of this change.

## Run 2 — full results

### G1

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.0279 | `SOP-003_Boiler_Start-Up_Procedure.docx` **← expected** |
| 2 | 0.0060 | `SOP-003_Boiler_Start-Up_Procedure.docx` **← expected** |
| 3 | 0.0004 | `INS-003_Boiler_Inspection_B-101.docx` |
| 4 | 0.0001 | `Equipment_Register.xlsx` |
| 5 | 0.0001 | `Spare_Parts_Inventory.xlsx` |

### G2

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.0068 | `MAN-002_Air_Compressor_Manual.docx` **← expected** |
| 2 | 0.0001 | `INC-002_Valve_Failure_V-220.docx` |
| 3 | 0.0000 | `INS-002_Vibration_Analysis_C-201.docx` |
| 4 | 0.0000 | `MAN-002_Air_Compressor_Manual.docx` **← expected** |
| 5 | 0.0000 | `Equipment_Register.xlsx` |

### G3

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.0050 | `MNT-003_Seal_Leakage_Repair_P-102.docx` **← expected** |
| 2 | 0.0019 | `MNT-003_Seal_Leakage_Repair_P-102.docx` **← expected** |
| 3 | 0.0001 | `LOG-001_Morning_Shift_15-Jul-2026.txt` |
| 4 | 0.0000 | `MAN-001_Centrifugal_Pump_Manual.docx` |
| 5 | 0.0000 | `SCN-001_Safety_Inspection_Checklist.pdf` |

### G4

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.0187 | `SOP-003_Boiler_Start-Up_Procedure.docx` |
| 2 | 0.0147 | `INC-002_Valve_Failure_V-220.docx` |
| 3 | 0.0110 | `INS-003_Boiler_Inspection_B-101.docx` **← expected** |
| 4 | 0.0024 | `SOP-003_Boiler_Start-Up_Procedure.docx` |
| 5 | 0.0005 | `LOG-002_Night_Shift_15-16-Jul-2026.txt` |

### G5

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.0001 | `SCN-002_P&ID_Cooling_Water.pdf` |
| 2 | 0.0001 | `MNT-001_Quarterly_PM_Cooling_Tower.docx` |
| 3 | 0.0000 | `MAN-002_Air_Compressor_Manual.docx` |
| 4 | 0.0000 | `SCN-001_Safety_Inspection_Checklist.pdf` |
| 5 | 0.0000 | `PPT-002_Plant_Overview.pptx` **← expected** |

### G6

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.0001 | `MNT-001_Quarterly_PM_Cooling_Tower.docx` **← expected** |
| 2 | 0.0000 | `LOG-001_Morning_Shift_15-Jul-2026.txt` |
| 3 | 0.0000 | `MNT-001_Quarterly_PM_Cooling_Tower.docx` **← expected** |
| 4 | 0.0000 | `LOG-002_Night_Shift_15-16-Jul-2026.txt` |
| 5 | 0.0000 | `LOG-001_Morning_Shift_15-Jul-2026.txt` |

### T1

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.3008 | `MNT-002_Bearing_Replacement_P-101.docx` **← expected** |
| 2 | 0.1825 | `INC-001_Pump_Oil_Leakage_P-101.docx` |
| 3 | 0.0680 | `PPT-001_Monthly_Safety_Training_Jul2026.pptx` |
| 4 | 0.0254 | `Maintenance_Schedule.xlsx` |
| 5 | 0.0126 | `LOG-001_Morning_Shift_15-Jul-2026.txt` |

### T2

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.0068 | `INS-001_Pressure_Vessel_Inspection_T-501.docx` **← expected** |
| 2 | 0.0030 | `INS-001_Pressure_Vessel_Inspection_T-501.docx` **← expected** |
| 3 | 0.0004 | `LOG-001_Morning_Shift_15-Jul-2026.txt` |
| 4 | 0.0001 | `LOG-001_Morning_Shift_15-Jul-2026.txt` |
| 5 | 0.0000 | `LOG-002_Night_Shift_15-16-Jul-2026.txt` |

### T3

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.9459 | `INC-002_Valve_Failure_V-220.docx` **← expected** |
| 2 | 0.0119 | `LOG-002_Night_Shift_15-16-Jul-2026.txt` |
| 3 | 0.0022 | `Equipment_Register.xlsx` |
| 4 | 0.0020 | `LOG-002_Night_Shift_15-16-Jul-2026.txt` |
| 5 | 0.0005 | `LOG-001_Morning_Shift_15-Jul-2026.txt` |

### X1

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.0015 | `MNT-003_Seal_Leakage_Repair_P-102.docx` |
| 2 | 0.0006 | `PPT-001_Monthly_Safety_Training_Jul2026.pptx` |
| 3 | 0.0003 | `INC-002_Valve_Failure_V-220.docx` |
| 4 | 0.0001 | `MNT-003_Seal_Leakage_Repair_P-102.docx` |
| 5 | 0.0001 | `INC-001_Pump_Oil_Leakage_P-101.docx` |


---

# Run 1 — baseline (chunk_size 512)

## Score

| Metric | Result |
|---|---|
| **Overall** | **9 / 10** |
| **Tag questions** | **3 / 3** |
| General questions | 5 / 6 |
| Trap question | 1 / 1 |
| Weak (correct doc at rank 4 or 5) | 0 |

Scoring per the brief: right = expected file in top 5; wrong = absent; weak = present but ranked 4th or 5th. Trap: right = nothing above threshold.

| Q | Expected | Rank of expected | Verdict |
|---|---|---:|---|
| G1 | `SOP-003_Boiler_Start-Up_Procedure.docx` | 1 | right |
| G2 | `MAN-002_Air_Compressor_Manual.docx` | 1 | right |
| G3 | `MNT-003_Seal_Leakage_Repair_P-102.docx` | 1 | right |
| G4 | `INS-003_Boiler_Inspection_B-101.docx` | 3 | right |
| G5 | `PPT-002_Plant_Overview.pptx` | — | **wrong** |
| G6 | `MNT-001_Quarterly_PM_Cooling_Tower.docx` | 1 | right |
| T1 | `MNT-002_Bearing_Replacement_P-101.docx` | 1 | right |
| T2 | `INS-001_Pressure_Vessel_Inspection_T-501.docx` | 1 | right |
| T3 | `INC-002_Valve_Failure_V-220.docx` | 1 | right |
| X1 | _nothing_ | — (top score 0.0049) | right |

## Run 1 — full results (chunk_size 512)

### G1

> When we bring the steam boiler up from cold, how quickly are we allowed to increase the burn, and is there a cap on how fast the metal can heat up?

**Expected:** `SOP-003_Boiler_Start-Up_Procedure.docx`

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.0375 | `SOP-003_Boiler_Start-Up_Procedure.docx` **← expected** |
| 2 | 0.0008 | `INS-003_Boiler_Inspection_B-101.docx` |
| 3 | 0.0001 | `Equipment_Register.xlsx` |
| 4 | 0.0001 | `LOG-002_Night_Shift_15-16-Jul-2026.txt` |
| 5 | 0.0000 | `INC-002_Valve_Failure_V-220.docx` |

### G2

> How dry is the instrument air meant to be, and at what pressure does its relief device open?

**Expected:** `MAN-002_Air_Compressor_Manual.docx`

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.0053 | `MAN-002_Air_Compressor_Manual.docx` **← expected** |
| 2 | 0.0000 | `INC-002_Valve_Failure_V-220.docx` |
| 3 | 0.0000 | `SOP-001_Pump_Start-Up_Procedure.docx` |
| 4 | 0.0000 | `INS-002_Vibration_Analysis_C-201.docx` |
| 5 | 0.0000 | `SOP-003_Boiler_Start-Up_Procedure.docx` |

### G3

> What was suggested to stop grit in the flush water chewing up the seal faces again?

**Expected:** `MNT-003_Seal_Leakage_Repair_P-102.docx`

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.0112 | `MNT-003_Seal_Leakage_Repair_P-102.docx` **← expected** |
| 2 | 0.0005 | `LOG-001_Morning_Shift_15-Jul-2026.txt` |
| 3 | 0.0000 | `SOP-001_Pump_Start-Up_Procedure.docx` |
| 4 | 0.0000 | `SOP-002_Pump_Shut-Down_Procedure.docx` |
| 5 | 0.0000 | `MAN-001_Centrifugal_Pump_Manual.docx` |

### G4

> At what pressures did the two relief valves on the steam drum actually pop during the last test?

**Expected:** `INS-003_Boiler_Inspection_B-101.docx`

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.0112 | `SOP-003_Boiler_Start-Up_Procedure.docx` |
| 2 | 0.0083 | `INC-002_Valve_Failure_V-220.docx` |
| 3 | 0.0070 | `INS-003_Boiler_Inspection_B-101.docx` **← expected** |
| 4 | 0.0002 | `LOG-002_Night_Shift_15-16-Jul-2026.txt` |
| 5 | 0.0001 | `Equipment_Register.xlsx` |

### G5

> Which control system vendor runs the site, and what's used for the safety instrumented layer?

**Expected:** `PPT-002_Plant_Overview.pptx`

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.0001 | `MAN-002_Air_Compressor_Manual.docx` |
| 2 | 0.0001 | `SCN-002_P&ID_Cooling_Water.pdf` |
| 3 | 0.0000 | `LOG-002_Night_Shift_15-16-Jul-2026.txt` |
| 4 | 0.0000 | `SCN-001_Safety_Inspection_Checklist.pdf` |
| 5 | 0.0000 | `LOG-001_Morning_Shift_15-Jul-2026.txt` |

### G6

> Is there any seasonal change recommended to the water treatment chemical programme?

**Expected:** `MNT-001_Quarterly_PM_Cooling_Tower.docx`

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.0001 | `MNT-001_Quarterly_PM_Cooling_Tower.docx` **← expected** |
| 2 | 0.0000 | `LOG-001_Morning_Shift_15-Jul-2026.txt` |
| 3 | 0.0000 | `LOG-002_Night_Shift_15-16-Jul-2026.txt` |
| 4 | 0.0000 | `LOG-001_Morning_Shift_15-Jul-2026.txt` |
| 5 | 0.0000 | `SOP-001_Pump_Start-Up_Procedure.docx` |

### T1

> P-101 was stripped down earlier this year — what state were the bearings in when they came out, and what did the readings settle at afterwards?

**Expected:** `MNT-002_Bearing_Replacement_P-101.docx`

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.2117 | `MNT-002_Bearing_Replacement_P-101.docx` **← expected** |
| 2 | 0.1808 | `INC-001_Pump_Oil_Leakage_P-101.docx` |
| 3 | 0.0285 | `MAN-001_Centrifugal_Pump_Manual.docx` |
| 4 | 0.0206 | `Maintenance_Schedule.xlsx` |
| 5 | 0.0040 | `SOP-001_Pump_Start-Up_Procedure.docx` |

### T2

> For T-501, what did the earth continuity measurement come out at, and how does that sit against the allowable?

**Expected:** `INS-001_Pressure_Vessel_Inspection_T-501.docx`

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.0033 | `INS-001_Pressure_Vessel_Inspection_T-501.docx` **← expected** |
| 2 | 0.0000 | `LOG-001_Morning_Shift_15-Jul-2026.txt` |
| 3 | 0.0000 | `LOG-002_Night_Shift_15-16-Jul-2026.txt` |
| 4 | 0.0000 | `Equipment_Register.xlsx` |
| 5 | 0.0000 | `LOG-002_Night_Shift_15-16-Jul-2026.txt` |

### T3

> When V-220 stopped responding, how far was its actual position from what the controller was asking for, and how high did the header pressure climb?

**Expected:** `INC-002_Valve_Failure_V-220.docx`

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.6998 `>= threshold` | `INC-002_Valve_Failure_V-220.docx` **← expected** |
| 2 | 0.0006 | `LOG-002_Night_Shift_15-16-Jul-2026.txt` |
| 3 | 0.0001 | `LOG-002_Night_Shift_15-16-Jul-2026.txt` |
| 4 | 0.0001 | `LOG-001_Morning_Shift_15-Jul-2026.txt` |
| 5 | 0.0001 | `SCN-002_P&ID_Cooling_Water.pdf` |

### X1 — trap

> What was the root cause of the K-402 seal gas failure in March, and which parts were replaced?

**Expected:** _nothing — `K-402` appears in no document_

| Rank | Score | Source |
|---:|---:|---|
| 1 | 0.0049 | `MNT-003_Seal_Leakage_Repair_P-102.docx` |
| 2 | 0.0004 | `INC-002_Valve_Failure_V-220.docx` |
| 3 | 0.0001 | `Spare_Parts_Inventory.xlsx` |
| 4 | 0.0000 | `LOG-001_Morning_Shift_15-Jul-2026.txt` |
| 5 | 0.0000 | `MAN-001_Centrifugal_Pump_Manual.docx` |

Scored right: nothing reached the 0.25 threshold. Note this is a threshold judgement, not a refusal — the retrieval layer has no way to say "I have nothing". It always returns its top-k. Only a caller that applies the threshold, or the LLM layer, can turn that into an abstention.

## Run 1 — the failure

**G5 — "Which control system vendor runs the site, and what's used for the safety instrumented layer?"** Expected `PPT-002_Plant_Overview.pptx`, which contains `DCS: Yokogawa CENTUM VP` and `SIS: Triconex (SIL-2 / SIL-3)`. It did not appear in the top 5 at all. What came back instead: the air compressor manual, the P&ID, two shift-log chunks and the safety checklist.

My read: this is the only question in the set that shares **no surface token** with its target. The document says "DCS" and "SIS"; the question says "control system vendor" and "safety instrumented layer". BM25 contributes nothing, so the dense arm has to carry it alone — and `all-MiniLM-L6-v2` does not connect the expanded phrases to their acronyms. The words it *can* match on ("safety", "system") are spread across the safety checklist, the safety observations in both shift logs and the P&ID legend, which is exactly the wrong neighbourhood. Every other question shares at least one anchor term with its target — "boiler", "instrument air", "seal", "relief valve", "water treatment", or an equipment tag.

The three tag questions all landed at rank 1 despite each tag appearing in six or more documents, which is the more encouraging result: the tag alone was not what found them. T1 is the closest call — `MNT-002` at 0.2117 against `INC-001` at 0.1808, and `INC-001` is a genuinely plausible answer since it discusses the same pump and cross-references the same job.

## Run 1 — the scores are the real problem

Ranking is good. **Absolute scores are not, and they break the product.**

Only one of ten queries produced any chunk at or above the configured `0.25` threshold — T3, at 0.6998. Eight correct rank-1 hits scored between **0.0001 and 0.2117**. G6 found the right document first, at `0.0001`.

This is not cosmetic, because the two retrieval paths treat the threshold differently:

- `retriever_service.py` (serving `/api/rag/retrieve` and `/api/rag/query`) filters on it: `chunks = [c for c in reranked if c.score >= similarity_threshold]`.
- `hybrid_retriever.py` (serving Copilot, `/api/chat`) does **not** filter at all.

Verified live against the running backend with G1 — the question whose correct document the reranker ranked first:

```
POST /api/rag/retrieve  {"query": "When we bring the steam boiler up from cold, ...", "top_k": 5}
-> total returned: None
   (empty — every chunk fell below the threshold)
```

The same query returns the right document through Copilot and nothing at all through the RAG endpoints. Copilot only works because it ignores a threshold that would otherwise silence it.

Two contributing causes:

1. **`ms-marco-MiniLM` is a passage reranker being fed whole documents.** Each chunk here is an entire ~1,100-character file opening with identical boilerplate — `ABC Petrochemicals Pvt. Ltd. | Document: SOP-003 | Rev: 1.0 | Date: 15-Jan-2026`. The model was trained on short, focused passages; a header-heavy blob scores low even when it contains the answer.
2. **Conversational queries score far below keyword queries.** Short keyword probes against this same stack scored 1.000 / 0.997 / 0.993 (`"oil leak pump P-101"`). The long natural-language questions here score three orders of magnitude lower. The threshold looks to have been tuned against the former and never re-checked against the latter.

### A trap this probe itself fell into

The first run produced scores in a flat `0.028–0.033` band — the RRF range. Reranking had silently not happened: the model loads lazily inside a 10-second scoring budget, blew it on first use, and `_disable()` switched reranking off for the entire process, with only a warning in the log. Production avoids this because `main.py` warms the model during startup. The numbers in this file were produced after an explicit `reranker_service.warmup()` returning `True`. Any process that forgets to warm up silently gets unreranked results.

## Caveats — read before trusting any of this

- **The corpus is synthetic and LLM-generated.** All 22 documents are fabricated records for a fictional plant ("ABC Petrochemicals Pvt. Ltd."), written to a uniform template with consistent formatting. No OCR noise, no scan artefacts, no handwriting, no tables split across pages, no redactions, no inconsistent terminology between authors. Real industrial document sets have all of those.
- **Documents are ~1,100 characters.** At 512 tokens they produced one chunk each (24 across 22 documents); at 256 they produce 2.4 each (52 total). Either way the longest document in the corpus is shorter than a single page of a real manual, so intra-document ranking, passage selection within a long document and page-level citation remain **largely untested**. A real 200-page OEM manual produces hundreds of chunks and is a different retrieval problem. **Run 2 does not demonstrate that chunking works — only that a smaller chunk size does not hurt on documents too short to need chunking.**
- **This does not prove behaviour on real multi-page scanned documents.** Nothing here exercises the OCR path, and `page_number` is null on every non-PDF chunk in this corpus, so location-level citation is untested too.
- **Retrieval is choosing between 24 candidates (run 1) or 52 (run 2).** At this scale "in the top 5" is a weak bar — a random ranker scores roughly 21% per question at 24 candidates. Read these scores as "no gross failures at toy scale", not as accuracy figures. Note also that the two runs are not scored against an identical candidate pool, which is one more reason to treat the 9/10 → 10/10 move as directional rather than precise.
- **The questions were LLM-drafted and human-reviewed, not human-authored from scratch.** They were written after reading the corpus, deliberately paraphrased away from source wording, and reviewed and approved before running. But the same model that drafted the questions also wrote this analysis, and questions written by someone who has just read the answers are biased toward being answerable. An engineer writing questions cold, without the corpus in front of them, would produce a harder and more honest set.
- **One run per configuration.** One embedding model, one reranker, no repeats, no confidence intervals. The chunk-size sweep was a single pass over 10 questions — differences of one hit are within the noise that sample size can support.

## Reproducing

The probe calls `VectorRetriever` directly against the live Qdrant collection. It warms the reranker first (mandatory — see the run 1 notes), over-fetches to 13, drops test-junk filenames and keeps the top 5. Raw per-query output including chunk ids was captured for both runs.

Run 2 re-indexed the corpus by clearing each document's chunks and vectors and putting its ingestion job back to `pending` for the background worker to rebuild. Chunks must be deleted explicitly: `ChunkingService.chunk_document` only bulk-inserts and never clears prior chunks, so reprocessing a document duplicates them in Postgres. Qdrant is unaffected — its indexer deletes a document's vectors before upserting. That asymmetry is a live bug on the retry path, not just a re-index inconvenience, and is not fixed here.
