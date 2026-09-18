# TRACE — Roadmap

**Branch:** `main` · **Last verified:** 18 September 2026 (late) — **the graph question is
settled at the answer level, and every open measurement is now closed.**
Stage 5 remains complete and its frozen configs are untouched. Earlier the same day
`passage2` — the configuration production runs — was validated at the answer level:
+13.6 pts fact coverage, +20.0 fully correct, negatives 5/5, after a fourth
refusal-classifier gap was found and fixed.

**Four things closed in the final pass:**

1. **`passage2_graphv2` is complete at 40/40** (8 cached + **32 new Groq calls**), so the
   last blocked measurement is done. **`graph_prefer_domain_entities` stays off** — on top
   of `passage2` it is **identical to it on fact coverage, item for item** (87.6% / 80.0%
   fully correct, both). See *Graph promotion status*.
2. **A fifth scoring gap was found and fixed** — `golden_set.yaml` F05 accepted "running
   hours" but not "operating hours", so **three correct answers scored 0.0**. Correcting it
   moved chunk512 (+2.9 coverage) and rerank_off (+2.8), and it was the *only* fact-coverage
   difference between `passage2` and `passage2_graphv2` — i.e. the metric, not the graph,
   produced the apparent regression.
3. **The full backend suite is green with the datastores up: 1108 passed, 0 failed,
   0 skipped.** The 5 failures seen with Docker stopped are environmental, not real.
4. **The documented chunk configuration was wrong.** Production runs **256/40**, not the
   "256/64" this file and `stage5_report.md` claimed in five places. Corrected; the corpus
   was built at 256/40 (`probe_results.md` had it right all along).

**No graph flag is promoted — none meets the answer-level bar, and this is now measured
rather than pending.** See *Graph promotion status*, *Post-Stage-5 changes*, and
*Known debt → 17 September audit*.

---

## What TRACE is

TRACE (Technical Records & Asset Compliance Engine) ingests messy industrial
documents — P&IDs, SOPs, OEM manuals, maintenance logs, inspection reports,
scanned drawings — and turns them into a queryable knowledge layer. An engineer
asks *"why did P-101 fail?"* in plain English and gets a grounded answer with
citations, produced by hybrid retrieval (Qdrant vector search + Neo4j knowledge
graph), cross-encoder reranking, and an LLM.

**Product identity: document intelligence.** Not an industrial asset management
platform. This is settled — see *Decisions already made*.

### Stack

| Layer | Choice |
| --- | --- |
| Backend | FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL |
| Frontend | Next.js 16.2.9, React 19.2, Tailwind v4 |
| Vector store | Qdrant — `all-MiniLM-L6-v2`, 384-dim, cosine. **Local dev now runs Qdrant v1.18.3 in Docker**; the Qdrant Cloud URL is parked (commented out) in `.env` |
| Knowledge graph | Neo4j 5.26 community — **local dev runs it in Docker** (`docker-compose.local.yml`); the Aura instance is gone |
| LLM | Groq — `openai/gpt-oss-120b` (`.env`; the `llama-3.3-70b-versatile` default in `config.py` is overridden) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| OCR | Tesseract + OpenCV preprocessing |

### Verified current state

Code figures were re-checked against the tree on 10 September 2026, after the
containerization commit (`e647562`); tests, Docker and live services on
13 September 2026. Nothing here is taken from the README —
the README is stale in four places, listed under *Known debt*.

| Fact | Value | How checked |
| --- | --- | --- |
| Agent framework | **deleted** | `backend/app/agents/` holds only stale `__pycache__`; no `.py` source |
| Registered tools / agents | 0 / 0 | no registry; `main.py` has no `register()` calls |
| `backend/app` | 197 files, **24,805** lines (17 Sep) | `find backend/app -name "*.py"` |
| `main.py` | 261 lines | `wc -l` |
| Files over 500 lines | 6 | `find … -exec wc -l` (was 7) |
| `except: … pass` blocks | **9** (re-counted 17 Sep; the 10 here was wrong — *Known debt* said 9 and was right) | `grep -A1` over `backend/app` |
| Migrations | 19 files, single head `017_investigations` | `alembic heads` |
| Backend tests | **1108 passed, 0 failed, 0 skipped, 5m06s** (18 Sep, final pass — after the F05 alias fix and its 3 tests, with both datastore containers up). An intermediate run the same evening, before those 3 tests existed, was **1105 passed in 2m42s**; the spread is warm-cache variance, not flakiness. ⚠️ With Docker **stopped** the same suite is unusable — 5 failures in `test_health_degradation.py` and roughly 18 tests in 15 minutes. Earlier: 1080 on 16 Sep, 1061 on 14 Sep, 1011 on 13 Sep | `pytest -q -rs` |
| Frontend tests | 61 passed, 6 files — **re-verified 17 Sep** | `npx vitest run` |
| Frontend typecheck | clean — **re-verified 17 Sep** | `npx tsc --noEmit` |
| Frontend routes | 12 | `find frontend/app -name page.tsx` |
| eslint | 42 problems (23 errors, 19 warnings) | `npx eslint .` |
| Pinned direct deps | 34 (all `==`) | `grep -c "==" backend/requirements.txt` |
| Lockfile | `backend/requirements.lock.txt`, 138 lines | present |
| API routers mounted | 17 under `/api` | `main.py` `include_router` calls |
| Docker | **backend image built 10 Sep and full stack run once**; Neo4j + Qdrant containers in daily use since 13 Sep | `docker image inspect trace-backend:dev`, `docker ps -a` |
| Frontend container | **none** | no `frontend/Dockerfile`; not a compose service |
| CI | **none** | no `.github/` |
| `pytest-timeout` | **not installed** | `pytest --timeout=120` → unrecognized argument |

**The health-test failures were the dead graph, and are gone — but there are five of
them, not two.** Measured 18 September 2026 with the Docker daemon stopped:
`test_health_degradation.py` reports **5 failed, 2 passed in 2m36s**, and the failures are
`::test_runtime_disabled_reranker_is_reported`, `::test_failed_model_load_is_reported`,
`::test_unwarmed_model_is_reported`, `::test_reranking_switched_off_is_not_degraded` and
`::test_optional_store_down_is_degraded_not_unavailable`. All five assert a baseline of
`status == "ok"`, which holds only when every optional service is reachable. With the
containers up all seven pass. The same run skips the 7 `test_rag_integration.py` tests and
drags the whole suite to a crawl — ~18 tests in 15 minutes against 1108 in 2m42s — because
every Qdrant call burns `QDRANT_TIMEOUT_SECONDS=30` × `QDRANT_MAX_RETRIES=3`. **Start
`trace-qdrant-1` and `trace-neo4j-1` before running the suite.** See *Known debt*.

### Live services, re-checked 18 September 2026

**18 September re-check (Docker restarted for the final pass):** Qdrant
`document_chunks` **138 points, status green**; Neo4j **171 nodes / 87 relationships** —
both identical to the 16 September figures below, so nothing drifted while the containers
were stopped. Postgres holds **29 active documents / 138 chunks** (16 soft-deleted), and
`ingestion_jobs` **33 completed / 8 queued / 3 failed**. One of the 29 active documents is
`FAILTEST-143234.txt`, status `failed` — a deliberate failure-path artefact from
5 September, so the real corpus is **28 indexed documents + 1 test row**.

### Live services, as recorded 16 September 2026

| Service | State |
| --- | --- |
| Neo4j (Docker `trace-neo4j-1`, 5.26) | **healthy** — **171 nodes / 87 relationships**, unchanged since the 13 Sep rebuild from Postgres; nodes from all 29 active documents, 0 stale nodes |
| Qdrant (Docker `trace-qdrant-1`, v1.18.3) | **healthy** — `document_chunks`, **138 points** (status green), exactly the 138 chunks of the 29 active Postgres documents |
| Qdrant — `eval_chunks_512` | **healthy, 86 points** (status green) — the Stage 5 512/64 ablation collection built by `python -m eval.chunk512`; separate from production, never queried by the app |
| Qdrant Cloud | parked — still configured in `.env` as comments, not used |
| Neo4j Aura | **gone** — hostname does not resolve |
| Groq | **healthy** — `openai/gpt-oss-120b`. Free tier: **200,000 tokens/day and 8,000 TPM**; the daily cap was reached on 14 and 15 September. On 16 September the 41 calls that closed Stage 5 fit inside the day's quota |
| PostgreSQL | native local (`localhost:5432`) — 29 active documents / 138 chunks, 16 soft-deleted (incl. the 3 `STAGE45-E2E-*` verification uploads). Not re-counted on 16 Sep |

Both datastores run as Docker containers that must be started before any evaluation
(`docker start trace-qdrant-1 trace-neo4j-1`); the eval runner connects to them on
`127.0.0.1` from the host, not from inside the compose network.

The `017_investigations` migration is retained as applied history; the
`investigations` table it created is now unused and its model, schemas and
service are gone. `alembic revision --autogenerate` will therefore propose
dropping the table — take that as a separate, deliberate migration.

---

## Two ordering principles

Everything below follows from these two. Read them before reordering anything.

### 1. Make it work, then deploy

Stages 1–7 make the product correct, complete and reproducible. Stage 8 puts it
online. Deployment is last because **a deployed system that returns wrong
answers is worse than an undeployed one** — it is the same product with a public
URL attached to the failure.

This means **containerization (stage 4) is a development tool, not deployment.**
Its purpose is reproducible environments and CI service containers. Stage 8 is
deployment, and it reuses the images stage 4 produces. Do not treat finishing
stage 4 as being deployed.

### 2. Test before build

Stage 1 needs nothing built and takes one hour. It runs against the cloud
services that are already connected. If retrieval is broken, every stage after
it would have been built on sand — a golden set measuring a broken retriever, a
CI pipeline gating on a broken retriever, a deployment serving a broken
retriever. Measure first, then decide what to build.

---

## Phase 0 — stabilization (done)

Completed history. No checkboxes; nothing here is to be re-planned.

**Committed in-flight work** (`d162a58`). Two half-finished changes were
finished and committed:

- *Conversational query understanding.* Retrieval previously ran on the literal
  text of a follow-up, so "what caused it?" searched the corpus for the word
  "it". `app/services/query_understanding.py` now resolves follow-ups against
  conversation history before retrieval runs.
- *RCA evidence contract.* `root_cause` could return a 0.7 confidence with zero
  citations. Confidence is now tied to the evidence actually present.

**Unregistered six agent tools.** Registry 49 → 43. Three were live attack
surface reachable by any Engineer-role user:

| Tool | Why withdrawn |
| --- | --- |
| `python_execute` | Ran `exec()` on LLM-generated code on the API host |
| `rest_client` | Unrestricted outbound HTTP — SSRF against anything the host can reach |
| `sql_execute` | Raw DB connection guarded only by a substring blocklist |

Three more returned fabricated success without performing the action, so an
agent would report an email sent or a work order raised that never happened:
`send_email`, `pi_historian`, `sap_execute`. The source files remain in place
with module docstrings explaining what each would need before it can return.

**Fixed the fresh-machine install.** `opencv-python-headless` sits on the
startup import chain (`app/processing/ocr/preprocessing.py` imports `cv2` at
module scope) but was missing from `requirements.txt`, so a clean clone could
not boot at all. Added it along with `numpy` and `tenacity`, pinned all 34
direct dependencies to `==`, added `requirements.lock.txt` generated from a
verified clean install, and reordered the README so dependency install precedes
migrations.

**Deleted seven unbacked frontend pages** — Assets, Asset Hierarchy,
Maintenance, Compliance, SOP Library, Roles & Permissions, System Settings —
along with their mock-data files, orphaned types and nav entries. Routes
21 → 14. No page now renders fabricated data.

**Corrected the README.** Audit Logging demoted to 🚧, agent count made
accurate, and a "Not yet built" section added recording what was removed and
what each removed page would need.

> **Note on state:** resolved. All of phase 0 is committed and the working tree
> is clean on `main` — `20130f5` carries the deletions and README corrections,
> with `a86cefe` and `e647562` after it. The `phase-0-stabilize` branch no
> longer matters.

---

## Stage 1 — Retrieval probe ✅ done

**Completed 6 September 2026.** Recorded in `backend/eval/probe_results.md`
(842 lines), committed in `a86cefe`.

**What was run.** `VectorRetriever.retrieve()` called in-process against the
live Qdrant collection — hybrid search then cross-encoder rerank, with the LLM
entirely out of the loop. Five runs; questions never revised once written. Ten
questions over 22 short documents for runs 1–3, plus three long documents and
three more questions for runs 4–5.

**Result: 13 / 13 expected documents in the top 5, 3 / 3 tag questions, trap
correctly refused (top score 0.0015).** Against the interpretation table that is
"healthy" — but read the file's own caveat before quoting the number:

> 13/13 counts a question right when the expected *document* reaches the top 5.
> Two of the three long-document questions return a passage that cannot answer
> them. The headline overstates real performance.

**What the probe proved beyond the score.** Four real defects, all since fixed:

| Found | Fixed in |
| --- | --- |
| `fulltext_search` passed a raw string as a named vector; every call 400'd and hybrid search silently fell back to vector-only — hybrid was never hybrid | `vector_store.py` |
| `RETRIEVAL_SIMILARITY_THRESHOLD=0.25` silenced `/api/rag/*` entirely while Copilot worked, because only one of the two paths filtered on it | default now `0.0`; the filter applies only when `> 0.0` |
| The reranker disabled itself for the whole process on a lazy first-load timeout, with only a warning | `main.py` warms it during startup and records `app.state.reranker_ready` |
| `--psm 3` OCR analysed ruled tables as layout and discarded them; a three-page scanned permit ingested clean having lost every data row | `--psm 11`; 9/18 → 17/18 markers recovered |

**Not done, and it matters:** the probe was run ad hoc and **the script was never
committed**. `backend/eval/` contains `probe_results.md` and nothing else, so
none of the five runs can be reproduced by a command. Stage 5 has to rebuild
that runner from prose.

---

## Stage 2 — Fix what the probe exposes ✅ done (two deliberate deferrals)

**Completed 6 September 2026**, in `a86cefe`. The four defects in the stage 1
table were the failure modes, and all four are fixed. Supporting work landed
with them: `retrieval_dedup.py` (document-level dedup in the Copilot path, plus
139 lines of tests), per-component degradation reporting on `/api/health`, and
the chunk-duplication fix on the reprocess path — `ChunkingService` now deletes
a document's prior chunks before re-inserting, which it never did before.

**Two exposed problems were deliberately not fixed here.** Both are recorded in
full under *Known debt*:

- **Retrieval scores whole questions against whole passages.** A compound
  question drops the answering passage from rank 4 to rank 22 (a 1,200× score
  difference); a naturally-phrased question loses a table to prose about that
  table (2,470×). The fix is query decomposition, which puts an LLM call on the
  hot path — it needs stage 5's harness to justify.
- **The lexical arm is still a filter, not a ranker.** `fulltext_search` works
  now, but it is a Qdrant `MatchText` filter re-scored locally by
  `_term_coverage`. There are still **no sparse vectors and no BM25 scoring**,
  despite `probe_results.md` describing the path as "dense + BM25". Real sparse
  vectors remain the open option if tag-style retrieval degrades at corpus
  scale.

---

## Stage 3 — Complete the half-built features ✅ done

**Completed 6 September 2026**, in `20130f5`.

- [x] **Audit-log read endpoint.** `GET /api/audit-logs`
      (`backend/app/api/routes/audit_logs.py`) with pagination and filtering,
      mounted in `main.py`, covered by `tests/test_audit_logs_api.py`.
- [x] **Audit Logs page wired to it.** `audit-logs-page-content.tsx` calls
      `useAuditLogs` (`frontend/hooks/use-audit-logs.ts` →
      `frontend/lib/api/audit-logs.ts`); the hardcoded empty array is gone and
      `audit-log-filters.tsx` was added.
- [x] **The swallowed promises are gone.** The one remaining `.catch()` in
      `copilot-page-content.tsx` sets a visible `snapshotWarning`; the sibling
      `listConversations()` catch sets `sidebarError`. No `.catch(() => {})`
      remains anywhere in the Copilot.
- [ ] **README status markers still not updated** — Audit Logging is marked 🚧
      with text that is now false. Rolled into the README fix below.

---

## Stage 4 — Containerize for development 🟡 built and run once, exit criterion not verified

**Written 7 September 2026** in `e647562`. Every artefact the stage asked for
exists, and the Dockerfile is unusually careful about the failure modes that
matter.

**Correction (13 September 2026):** the earlier "never built" note is wrong.
`trace-backend:dev` exists locally (created 10 September 2026 11:29 UTC,
~805 MB) and the full stack ran: `trace-backend-1`, `trace-migrate-1`,
`trace-postgres-1`, `trace-qdrant-1` and `trace-neo4j-1` containers are present
(exited), and `docker logs trace-backend-1` shows `graph_svc=connected` and a
completed graph extraction for a test upload. What has **not** been verified is
the exit criterion below — restart persistence and the in-container test run.

- [x] **`backend/Dockerfile`** — 233 lines, three stages (`builder`, `models`,
      `runtime`), `--platform=linux/amd64` pinned on every `FROM`.
  - [x] CPU-only torch from `download.pytorch.org/whl/cpu`, the pin read out of
        the lockfile so the two cannot drift, and a `+cpu` assertion that fails
        the build if the index stops being honoured.
  - [x] Both models baked in via `scripts/bake_models.py`, then re-loaded with
        `HF_HUB_OFFLINE=1` so a build that still reaches the Hub fails at build
        time instead of stalling the first user request.
  - [x] Tesseract plus eleven language packs via `apt`; `libglib2.0-0` for the
        cv2 import on the startup path, `libgomp1`, `libpq5`.
  - [x] Non-root `trace` (uid/gid 1000); `HEALTHCHECK` on `/api/health` through
        the interpreter, since the slim base has no curl.
  - [x] Installs `requirements.lock.txt`; `pywin32` carries a `sys_platform`
        marker so the Windows-frozen lockfile installs cleanly on Linux.
  - [x] Build-time `import app.main` smoke check.
- [x] **`docker-compose.yml`** — Postgres 16 with a `pg_isready` healthcheck, a
      one-shot `migrate` service running `alembic upgrade head`, and `backend`
      gated on `service_completed_successfully`. Migrations never run on boot.
- [x] **`docker-compose.local.yml`** — Qdrant v1.18.3 and Neo4j 5.26 with real
      readiness probes (`/dev/tcp`, `cypher-shell 'RETURN 1'`), plus
      `TRACE_TEST_QDRANT_URL` so the 7 skipped integration tests can run.
- [x] **Named volumes** for `postgres_data` and `backend_storage`, with
      `/app/storage` and `/app/workspace` created as `trace` before the mount so
      the volume inherits writable ownership.
- [x] **`.env.docker.example`** — 173 lines, both flavours (compose service
      names and cloud URLs) in one file.

**Remaining before this stage is done:**

- [x] **Build and run it once.** Done 10 September 2026 — image built, stack
      started, a test document ingested through the containerized worker (see
      correction above).
- [x] **Set `GROQ_API_KEY` in `.env.docker`** — now set (checked 13 September
      2026, value not inspected).
- [x] **Compose no longer keys dev Neo4j on the cloud secret.**
      `docker-compose.local.yml` uses a literal `tracedevpassword` instead of
      `${NEO4J_PASSWORD:-…}`, which interpolated the root `.env` password.
      *Committed in `6d57238`* — the earlier "uncommitted" note here was wrong
      (verified 18 September against `git show HEAD:docker-compose.local.yml`).
- [ ] **Bootstrap a user.** Nothing in compose creates the SuperAdmin.
      `backend/scripts/create_super_admin.py` reads `SUPER_ADMIN_EMAIL` /
      `_PASSWORD` / `_FULL_NAME`, none of which are in `.env.docker` — a fresh
      stack comes up with no account to log in with. Add the three variables
      plus a one-shot `seed` service, or document the `docker compose exec`
      call in the README.
- [ ] **Verify the exit criterion end to end:** `/api/health` returns `ok` with
      all five components green; a document uploaded before
      `docker compose restart` is still downloadable after it; `pytest -q -rs`
      inside the container reports the 8 previously-skipped integration tests as
      run rather than skipped.
- [ ] **Decide about the frontend.** There is no `frontend/Dockerfile` and the
      frontend is not a compose service, so `docker compose up` yields a backend
      with no UI. Defensible if Vercel stays the stage 8 target — but say so in
      the README instead of leaving it to be discovered.

---

## Stage 4.5 — Restore the knowledge graph ✅ done

**Verified 13 September 2026, cleanup finished the same day.** The graph is
back, both stores are clean and match Postgres exactly, ingestion and
retrieval work end to end, and the Knowledge Graph page has been checked in a
logged-in browser.

**Topology used.** Neo4j 5.26 and Qdrant v1.18.3 in Docker, started alone with
`docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --no-deps qdrant neo4j`.
PostgreSQL stays on the native local instance (`localhost:5432`); the compose
`postgres` service is **not** started (it would collide on 5432). The backend
runs natively (`uvicorn app.main:app`) against all three.

**The blocker bug — fixed, uncommitted.** `services/processors/graph_processor.py`
built `Relationship(...)` without importing it. Every chunk that yielded a
relationship raised `NameError`, wrapped as `GraphExtractionError`; because
`GraphProcessor` runs before embedding and indexing, the whole ingestion job
failed and the document never reached Qdrant. Latent while Neo4j was down,
because the processor is only added when a graph store connects. Proven both
ways: `tests/test_graph_processor.py` is **10/10 with the import, 3 failed with
`NameError: name 'Relationship' is not defined` on the committed file**, and a
live upload whose text yields relationships now completes (below).

- [x] **Neo4j provisioned — containerized.** `NEO4J_URI=bolt://127.0.0.1:7687`
      in `.env`, password matches the container's `tracedevpassword`.
      `.env.docker` already uses `bolt://neo4j:7687`.
- [x] **Qdrant moved to the same container stack.** `.env` now points at
      `http://127.0.0.1:6333` with an empty API key; the cloud URL/key are
      commented out, not deleted. Re-populated from Postgres with
      `scripts/backfill_chunks_embeddings_index.py` — all 29 active documents,
      138 stored embeddings re-indexed in 4 s, no re-embedding.
- [x] **Graph rebuilt** with `scripts/build_knowledge_graph.py`: 29/29
      documents, 0 failures. The script still imports and runs against the
      current extraction code. (First pass: 181 nodes / 91 relationships,
      including stale data; final state after cleanup is below.)
- [x] **`/api/health` → `ok`**, all five components green (`database`,
      `vector_store`, `graph_store`, `llm`, `reranker`), nothing degraded.
- [x] **`/api/graph/statistics`** → non-zero (final: 171 entities, 87
      relationships, 29 documents). `/api/graph/search?q=P-101` and
      `/api/graph/neighbors/{id}` → 200 with data.
- [x] **Graph ingestion, end to end.** Uploaded a text document through
      `POST /api/documents`; the background worker ran it to
      `completed` / `indexed` in 2.1 s. Neo4j got 8 nodes and all **4
      relationships** (`CONNECTED_TO`, `INPUT_TO`, `HAS_FAILURE`, `CAUSED_BY`),
      Qdrant got its vector. This is the exact path that used to fail.
- [x] **Graph retrieval, end to end.** `POST /api/rag/graph-query` →
      `retrieval_source=hybrid`, 10 graph facts including the new document's
      `P-4545 INPUT_TO TK-4546` and `bearing failure CAUSED_BY misalignment`,
      and a correct LLM answer citing the uploaded document.
- [x] **Stale container-test data removed** (approved 13 September 2026). The
      10 September containerized run had left 5 Qdrant points and 14 Neo4j
      nodes / 4 relationships from `e2e_pump_report.txt`,
      `ocr_verification.png` and `scanned_verification.pdf` — documents absent
      from the local Postgres — and *"Why did pump P-101 fail?"* was answered
      from `e2e_pump_report.txt`. Deleted the 5 points by `document_id`,
      cleared Neo4j (`MATCH (n) DETACH DELETE n` → 0 nodes) and re-ran
      `build_knowledge_graph.py`: 29/29 documents, 0 failures, **171 nodes /
      87 relationships, 0 nodes carrying stale provenance**.
- [x] **The three `STAGE45-E2E-*.txt` verification uploads soft-deleted** via
      `DELETE /api/documents/{id}` (`012d7f24…`, `0c909188…`, `5d8a6bd8…`):
      204 each, `GET` → 404 afterwards, their Qdrant vectors gone (0 points
      each). The rebuild skips soft-deleted documents, so they left no graph
      nodes. Side note: the delete path logs `Deleted 0 vectors` even when it
      removed vectors — the log count is wrong, the delete is not.
- [x] **Stores match Postgres exactly.** Qdrant 138 points across 29 document
      ids = 29 active Postgres documents / 138 chunks; per-document counts
      identical; no point belongs to an inactive document.
- [x] **Answers no longer cite absent documents.** Re-asked *"Why did pump
      P-101 fail?"* through `/api/rag/graph-query`: `retrieval_source=hybrid`,
      7 graph facts, 3 citations (`INC-001…`, `MNT-003…`, `MNT-002…`) — all
      active in Postgres — and the answer now comes from the real INC-001
      report (loose bearing-housing drain plug). Graph facts still show the
      wrong `source_document` label; that is the provenance debt below, not
      stale data.
- [x] **Knowledge Graph page — data path verified.** With the Next.js dev
      server (`localhost:3000`) and backend running: `/knowledge-graph`
      compiles and serves 200 (307 → `/login` without a session, as
      designed); CORS preflight from `http://localhost:3000` → 200 with
      credentials allowed; replaying the page's own initial load
      (`GET /api/graph/entities?skip=0&limit=50` →
      `POST /api/graph/neighbors/batch` → `/statistics` + `/schema`) returns
      data the page turns into **63 nodes and 24 edges, 0 edges with a missing
      endpoint**, stats 171 / 87 / 29, `has_next=true`.
- [x] **Knowledge Graph page — visual render.** Manually verified by the user
      on 13 September 2026 in a logged-in browser: nodes and edges render
      correctly, and the stats read 171 entities, 87 relationships, 29
      documents.
- [x] **Re-run `pytest`** — 1011 passed, 0 failed, 0 skipped. Both
      `test_health_degradation.py` failures cleared, and the 7
      `test_rag_integration.py` tests ran against the Qdrant container instead
      of skipping.

**Carried forward, not blocking this stage:** decide the standing datastore
policy (Docker vs managed Aura + Qdrant Cloud) and record it under *Decisions
already made*, where the row is marked reopened. It must be settled before
stage 8, which still assumes managed services. A free instance that silently
disappears is not a third option.

**Exit criterion.** `/api/health` reports `graph_store: ok` ✅, `/api/graph/statistics`
returns non-zero counts ✅, answers no longer cite documents absent from
Postgres ✅, the Knowledge Graph page renders nodes ✅ (data path and visual
render both verified).

---

## Stage 5 — Evaluation harness ✅ COMPLETE (16 September 2026)

**Stage 5 is closed.** Every configuration — baseline, rerank_off, graph_off, chunk512 and
`graph_v2` — is measured at **40/40 on answers and 40/40 on retrieval**. The last two gaps
were closed on 16 September for **41 Groq calls**: chunk512's outstanding negative N05 (1 call,
39 reused from cache) and the full `graph_v2` answer run (40 calls, none reusable by design).

**Two further configurations were measured after the stage closed** — `passage2` and
`passage2_graphv2`, both 40/40 on 18 September — so the answer-level picture now covers
**seven** configurations and **280 answers**. Neither reopens Stage 5; both are recorded
under *Post-Stage-5 changes* and *`passage2_graphv2`* below.

**Final decision (as of stage close): keep the baseline pipeline exactly as it is** —
hybrid search + cross-encoder reranker + graph, 256/40 chunks,
`graph_prefer_domain_entities` **off**. ⚠️ **One half of this has since changed:**
`retrieval_chunks_per_document` moved 1 → **2** on 17 September and was validated at the
answer level on 18 September, so production now runs `passage2`, not the Stage 5 baseline.
The graph flag stayed off and is now settled on answer-level evidence. See *Final decision*
below and *Post-Stage-5 changes*.

**Effort: 4 days.** Carried out 13–16 September 2026.

**Commit state, corrected 18 September 2026.** The earlier "nothing is committed" note is
**stale**. The harness, the golden set and the results were committed across `6d57238`,
`bbf5806`, `fbf3439` and `f545e67`; so were the 17 September OCR bounding, dedup, dashboard
and graph-count fixes (`f545e67`). What is *still* uncommitted is only the 18 September
work: `eval/metrics.py` (the `report` verb), `eval/golden_set.yaml` (the F05 aliases),
`eval/report.py`, `eval/stage5_report.md`, the rescored `results/*/answers.*`,
`results/passage2_graphv2/answers.*`, `tests/test_eval_metrics.py` and this file.

**Full results and interpretation: [`backend/eval/stage5_report.md`](backend/eval/stage5_report.md).**
Generated tables: `backend/eval/results/comparison.md`.

### Status summary (18 September 2026 — final)

| Area | State |
| --- | --- |
| Evaluation harness (validator, metrics, retrieval + answer runners, LLM cache) | ✅ complete |
| Golden set — 40 questions | ✅ reviewed and validated (`python -m eval.validate`: 0 errors, 7 warnings, against both collections) |
| **Retrieval evaluation** — baseline + 4 ablations | ✅ **complete** (baseline rerun reproduced identical numbers) |
| Backend tests | ✅ **full suite green** — **1108 passed, 0 failed, 0 skipped** (18 Sep, final pass after the F05 alias fix; 51 eval-metrics tests) |
| **Answer evaluation — baseline** | ✅ **40 / 40** |
| **Answer ablation — graph_off** | ✅ **40 / 40** (14 Sep) |
| **Answer ablation — rerank_off** | ✅ **40 / 40** (15 Sep) |
| **Answer ablation — chunk512** | ✅ **40 / 40** (16 Sep) — N05 generated; negatives now **5 / 5** |
| **Answer run — `graph_v2`** | ✅ **40 / 40** (16 Sep) — 40 new calls. **Result: no answer-level effect** |
| **Answer run — `passage2`** | ✅ **40 / 40** (18 Sep) — **validated**, +13.6 coverage, +20.0 fully correct |
| **Answer run — `passage2_graphv2`** | ✅ **40 / 40** (18 Sep) — 8 cached + **32 new calls**. **Result: identical to `passage2` on fact coverage, item for item** |
| LLM-as-judge | ⏳ **not implemented** (optional step 7; never gated) |
| Scoring fixes (16 Sep) | ✅ third refusal-classifier wording gap + one S17 fact phrasing; move **exactly 3 records**, leave baseline / rerank_off / graph_off byte-identical; 6 new tests |
| Scoring fixes (18 Sep) | ✅ fourth refusal-classifier gap (`report`, moves 1 record) and the **F05 "operating hours" alias gap** (moves **3 records**: chunk512, rerank_off, passage2_graphv2); 3 further tests |
| Empty-generation artefact | ✅ **found, quantified, corrected in the report** — 3 of 200 answers are empty (`max_tokens=1024`); it had corrupted two Stage 5 conclusions. Fixed by the retry; every config now reports `empty_answers: []` |
| Blocker | **None.** All 280 answers cached; every table rebuilds with `rescore` + `report`, no Groq |
| Cached answers | **283** in `backend/eval/cache/llm/` (gitignored) |
| Git | **The 18 September work is uncommitted**; everything earlier is committed — see *Commit state, corrected 18 September* above |

### Final decision

**Chosen configuration: the baseline pipeline, unchanged.** Hybrid search + cross-encoder
reranker + knowledge graph, 256/40 chunks, `graph_prefer_domain_entities` **off**.

| Component | Decision | Why |
| --- | --- | --- |
| Cross-encoder reranker | **Keep** — and its CPU latency is a deployment blocker | Removing it costs 11.4 pts fully-correct, 40 pts on follow-up, and one negative to a genuine missed refusal |
| Knowledge graph | **Keep enabled** | Product feature; reworked it is the best retrieval config measured. Nothing was removed from Neo4j |
| `graph_prefer_domain_entities` (`graph_v2`) | **Stays off by default. Code kept, gated, unchanged** | The criterion was fixed *before* the run: promote it only if the retrieval gain reaches the answers. It does not (see below) |
| Chunk size | **Stays 256/40** | 512 is the biggest answer gain in Stage 5 but is read through a 256-wordpiece embedding window that truncates it. Change the embedding model first |
| `max_tokens=1024` | **Raise it** — the one code change Stage 5 clearly earns, deliberately *not* made here | It produced 3 empty and several truncated answers in 200 generations. Changing it invalidates all 200 cached answers, so it needs a fresh quota day |

**The `graph_v2` verdict, stated plainly.** The reworked graph arm is a genuine *retrieval*
improvement — doc hit@5 88.6% → **97.1%**, MRR 0.860 → **0.920** (above graph-off's 0.906),
and 430 ms/query faster than the baseline. **It produces no answer-level improvement.** Across
all 40 items it differs from the baseline on three answers; two cover zero facts either way,
and the third is a truncated generation. Excluding the items no config answered completely,
`graph_v2` and the baseline are **identical**: 73.2% coverage, 59.4% fully correct, 86.5%
multi-hop each. The reason is visible in the retrieval numbers and matches conclusion 1 —
`graph_v2` changes which *document* ranks first but leaves **evidence-in-context at 61.4%,
identical to the baseline**, so the passages reaching the prompt never change. This is now the
third independent measurement saying the graph does not move answers.

**Correction recorded against the 15 September conclusions.** chunk512's reported −11.7 pts
multi-hop regression was **not** a retrieval effect: its M05 and M10 answers are empty strings
(`max_tokens`), and M05's retrieval is *identical* to the baseline's. Excluding the incomplete
items, chunk512's multi-hop coverage is **96.9% vs the baseline's 86.5%**. The −10 pts
multi-document *recall* cost is real and stands; the claim it had been measured reaching the
answers does not.

### Final Stage 5 metrics

> **The answer table in this section is the 16 September scoring and is kept as the record
> of what Stage 5 concluded. It is not current.** Two later scoring corrections moved it —
> the empty-answer retry (17 Sep) and the F05 alias fix (18 Sep) — and `passage2` /
> `passage2_graphv2` are not in it at all. **Quote `backend/eval/results/comparison.md`**,
> which `python -m eval.run report` regenerates, for anything current. The retrieval table
> below is unaffected by both corrections and still reproduces exactly.

**Retrieval** (35 answerable, deterministic, reruns identically):

| Metric | baseline | rerank_off | graph_off | chunk512 | graph_v2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Doc recall@5 | 91.9% | 88.6% | **98.6%** | 89.0% | **98.6%** |
| Doc hit@5 | 88.6% | 82.9% | **97.1%** | 82.9% | **97.1%** |
| Passage recall@5 | 56.7% | 50.0% | 59.5% | **77.1%** | 59.5% |
| Evidence in LLM context | 61.4% | 54.3% | 61.4% | **86.2%** | 61.4% |
| MRR | 0.860 | 0.783 | 0.906 | 0.853 | **0.920** |
| Retrieval p50 / p95 (ms) | 6485 / 8402 | **132 / 170** | 5511 / 6356 | 7542 / 9443 | 6055 / 6690 |

**Answers** (all 40 items each, one LLM sample per question):

| Metric | baseline | rerank_off | graph_off | chunk512 | graph_v2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fact coverage (35 answerable) | 72.6% | 63.8% | 73.6% | **80.7%** | 70.7% |
| Fully correct | 60.0% | 48.6% | 62.9% | **77.1%** | 57.1% |
| Fact coverage — single_hop | 62.5% | 62.5% | 64.2% | **82.5%** | 62.5% |
| Fact coverage — multi_hop | **89.2%** | 78.2% | **89.2%** | 77.5% | 82.5% |
| Fact coverage — follow_up | 80.0% | 40.0% | 80.0% | 80.0% | 80.0% |
| Correct refusal (5 negatives) | **5 / 5** | 4 / 5 | **5 / 5** | **5 / 5** | **5 / 5** |
| False refusal (answerable) | 11.4% | 14.3% | 11.4% | **8.6%** | 11.4% |
| Citation precision / recall | 77.8% / 81.9% | 75.0% / 81.4% | 84.3% / **91.9%** | **89.8%** / 87.1% | 79.8% / 86.7% |
| Grounded sentence share | 48.8% | 45.8% | **60.8%** | 60.6% | 49.1% |
| Empty answers (of 40) | 1 (S14) | 0 | 0 | 2 (M05, M10) | 0 |

**Sensitivity check** — the same metrics over the 32 answerable items *every* config answered
completely (excluding S14, M05, M10). A post-hoc exclusion, so a check and not the headline,
but it is what shows the two artefacts above:

| Metric (32 items) | baseline | rerank_off | graph_off | chunk512 | graph_v2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fact coverage | 73.2% | 63.8% | 74.2% | **85.2%** | 73.2% |
| Fully correct | 59.4% | 50.0% | 62.5% | **81.2%** | 59.4% |
| Fact coverage — multi_hop (8) | 86.5% | 80.2% | 86.5% | **96.9%** | 86.5% |

**Full results and interpretation: [`backend/eval/stage5_report.md`](backend/eval/stage5_report.md)** —
§3.4 `graph_v2` on answers, §3.5 the empty-generation artefact and sensitivity check,
§3.6 the two scoring fixes, §8 chosen configuration.
Generated tables: `backend/eval/results/comparison.md`.

### `passage2` answer evaluation — ✅ validated (18 September 2026)

**The configuration production already runs is now measured at the answer level, and it
is the largest answer-level gain in the project.** 40/40, one LLM sample per question,
`eval/results/passage2/answers.json`.

| Metric (35 answerable) | baseline | **passage2** |
| --- | ---: | ---: |
| Fact coverage | 74.0% | **87.6% (+13.6)** |
| Fully correct | 60.0% | **80.0% (+20.0)** |
| Fact coverage — single_hop | 65.0% | **87.5% (+22.5)** |
| Fact coverage — multi_hop | 89.2% | 91.7% (+2.5) |
| Fact coverage — follow_up | 80.0% | 80.0% |
| False refusal | 11.4% | **8.6% (−2.9)** |
| Citation precision / recall | 78.4% / 84.8% | **85.5%** (+7.1) / 85.7% (+1.0) |
| Grounded sentence share | 49.0% | **57.2% (+8.2)** |
| Correct refusal (5 negatives) | 5 / 5 | **5 / 5** |
| Empty answers | 0 | 0 |

Against chunk512 it **ties on coverage (87.6% each) and trails by 2.9 pts on
fully-correct (80.0% against 82.9%)** — figures corrected by the F05 alias fix later the
same day, which moved chunk512 up from 84.7% / 80.0%; the pre-fix reading that `passage2`
"beats chunk512 on coverage" was an artefact of that gap. Unlike chunk512, `passage2`
needs no re-embedding and suffers no 256-wordpiece truncation, which is why it ships.
This is conclusion 1 confirmed end to end: `passage2` raised evidence-in-context 61.4% →
86.2%, and the answers followed. **The default shipped on 17 September is correct.**

**A fourth refusal-classifier gap was found and fixed first.** The raw run scored N04
`missed_refusal`, showing correct refusal at 4/5 — which would have been a genuine
trade-off against all the gains above. It was not one. The answer reads *"the available
documents do not report any internal inspection findings … the internal inspection was
deferred to the next shutdown"*: a correct premise correction that invents nothing,
citing INS-003 and LOG-001.

The cause was one missing verb. Pattern 1 (`(do|does) not (contain|include|provide|
mention|specify|record)`) already accepts the negated-active form unrestricted; it
simply lacked `report`. Fixed to the same standard as the three earlier gaps:

- **Minimal** — one verb added, not a new pattern. A restricted subject/object pattern
  was drafted first and discarded as redundant once pattern 1's actual breadth was read.
- **`list` and `show` deliberately excluded.** Both look symmetric, neither is evidenced
  by a stored answer, and `list` is not free: it reclassifies rerank_off's M01, an
  answerable item this fix has no evidence about. A test pins the exclusion.
- **Verified** against every stored answer in all six configs: adding `report` alone
  moves **exactly one record**.
- **Rescored** with `python -m eval.run rescore` (no Groq): only `passage2` changed,
  correct refusal 0.80 → 1.00. Every other config byte-identical on refusal *and*
  coverage.
- 48 tests in `test_eval_metrics.py`, including the N04 regression case. Full backend
  suite re-run after the change: **1105 passed, 0 failed**.

### `passage2_graphv2` — ✅ complete, 40 / 40 (18 September 2026)

**The run the graph decision needed is done**, and it settles the question. The 8 cached
answers were reused and **32 new calls** finished it — no empty generations, nothing
skipped. The run hit Groq's 8,000 **tokens-per-minute** ceiling repeatedly (not the daily
cap) and the client's retry absorbed it, so the run is slow but complete.

| Metric (35 answerable) | `passage2` (shipped) | `passage2_graphv2` |
| --- | ---: | ---: |
| Fact coverage | 87.6% | **87.6%** |
| Fully correct | 80.0% | **80.0%** |
| Fact coverage — single_hop / multi_hop / follow_up | 87.5 / 91.7 / 80.0 | **87.5 / 91.7 / 80.0** |
| Correct refusal (5 negatives) | 5 / 5 | **5 / 5** |
| False refusal | 8.6% | 5.7% |
| Citation precision / recall | 85.5% / 85.7% | 85.5% / **93.3%** |
| Grounded sentence share | 57.2% | 59.0% |
| Retrieval: doc recall@5 / hit@5 / MRR | 89.0% / 85.7% / 0.851 | **98.6% / 97.1% / 0.920** |

**Fact coverage is identical on all 40 items** — not identical in aggregate, identical
item for item. 16 of 40 items differ at all, and 15 of those differ *only* in citation
precision or recall.

**The one substantive difference is S12, and it is not an improvement.** The metric says
`false_refusal → answered`, which reads like a win. Reading the answers says otherwise.
The true values are 12.9 mm (2026) and 13.6 mm (2018) for grid A3; both configs retrieve
the wrong row and report 12.4 mm, and both score **0.0 coverage**. `passage2` then states
that the eight-year-old value is not in the documents. `passage2_graphv2` instead
**extrapolates "≈13.5 mm" from a corrosion rate** and labels it a hypothesis. A wrong
number offered with a derivation is a worse failure than an admission of absence, so the
−2.9 pts false-refusal "gain" is, on inspection, a regression in failure mode.

**The apparent fact-coverage regression was a scoring bug, and is gone.** Before the F05
fix this run scored 84.8% coverage and 60.0% follow-up, which looked like a real 2.9-point
cost. The entire difference was F05: both configs answer "every 4,000 operating hours",
and only `passage2` was credited — because its evidence block happened to quote the source
verbatim as "4000 hours", which the alias list accepted. See *Scoring fixes (18 Sep)*.

### Graph promotion status — settled on answer-level evidence, defaults stay (18 September 2026)

Three graph changes now exist as gated, measured code. **None meets the promotion bar,
so every one of them stays off and the graph itself stays enabled.** Recorded here so
the question is not reopened without new evidence.

| Change | Retrieval | Answers | Decision |
| --- | --- | --- | --- |
| `graph_prefer_domain_entities` (`graph_v2`) | **better** — hit@5 97.1%, MRR 0.920, on both chunk settings | ✅ **measured twice** — neutral on the 256 baseline, and on `passage2` **identical item for item on fact coverage** (87.6% / 80.0% each) | **Off.** The criterion fixed before the run — promote only if the retrieval gain reaches the answers — is not met on either base. Its only substantive answer change (S12) swaps a refusal for an extrapolated number |
| `graph_fact_relationship_provenance` | **neutral** — identical on all 40 items bar one MRR | ❌ **not measured** | **Off.** Retrieval-neutral proves it is *safe*, not that it helps; its benefit is citation correctness, an answer metric |
| Neighbour-pair dedup (keeps 1 edge per pair) | ❌ not measured | ❌ not measured | **Unchanged.** Strongest remaining lead — it *adds* missing facts rather than reordering present ones |

The pattern is consistent and worth stating: **four independent measurements now say
the graph does not move answers** — graph_off on the baseline, `graph_v2` on the baseline,
`graph_provenance` at retrieval level, and now `graph_v2` on top of `passage2`, where its
large retrieval advantage produced **zero** change in fact coverage on any of the 40 items.
The graph is kept because it is a product feature and because `graph_v2` is the best
retrieval configuration measured — not because any version of it has been shown to improve
answer quality. **This question is now closed on evidence; reopen it only with a new
measurement, not a new intuition.**

The honest counter-argument, recorded so it is not lost: on `passage2` the flag does
improve citation recall (85.7% → 93.3%) and grounded share (57.2% → 59.0%) at identical
citation precision, and its retrieval is strictly better. If citation correctness later
becomes the metric that matters — it is what `graph_fact_relationship_provenance` targets
— this flag is the cheapest thing to revisit, and the run above is the evidence to start
from.

### Post-Stage-5 changes to the production pipeline (16–18 September 2026)

Stage 5 concluded "nothing in production changes". That is **no longer true** — two
defaults moved afterwards. The frozen eval configs pin their own values, so every
Stage 5 number above still reproduces; what follows is what the *product* now runs.

| Setting | Stage 5 | Now | Evidence | Answer-level? |
| --- | --- | --- | --- | --- |
| `llm_answer_max_tokens` | 1024 | 1024 **+ 3072 retry** | 3 of 200 generations empty | n/a — strictly removes a failure |
| `retrieval_chunks_per_document` | 1 | **2** | `passage2`: evidence-in-context 61.4% → **86.2%** | ✅ **measured 18 Sep — validated**, coverage +13.6, fully-correct +20.0, negatives 5/5 |
| `graph_prefer_domain_entities` | off | off | neutral on answers on **both** chunk settings | ✅ **measured twice** (18 Sep: `passage2_graphv2`, 40/40) |
| `graph_fact_relationship_provenance` | — | off (new) | retrieval-neutral | ⚠️ not measured |

**The empty-answer retry.** `_generate_answer` retries once at
`llm_answer_retry_max_tokens` when a generation comes back blank; wired into the
buffered path and **both** streaming paths. All three empty answers were regenerated —
every config now reports `empty_answers: []`, and the LLM cache holds 203 entries.
`comparison.md` was regenerated from them: baseline coverage 72.6% → **74.0%**,
chunk512 80.7% → **84.7%** and fully-correct 77.1% → **80.0%**. chunk512's multi-hop
"regression" is now measured away: 77.5% → **91.5%**, above the baseline's 89.2%. The
15 September correction was right, and is now confirmed by measurement rather than by
a post-hoc exclusion.

**`passage2`, and the one thing outstanding.** Two passages per document at the same
`top_k` (which counts documents) recovers evidence-in-context to 86.2% — the figure
the 512-token ablation reached, by the same mechanism, without re-embedding the corpus
and without the 256-wordpiece truncation. It costs doc recall@5 (91.9% → 89.0%) and
MRR (0.860 → 0.851).

Two things are worth stating plainly:

1. ~~**It was promoted on retrieval evidence alone.**~~ ✅ **Closed 18 September** — the
   answer run is complete at 40/40 and the promotion is vindicated: +13.6 pts coverage,
   +20.0 fully correct, negatives 5/5, no metric regressed. See *`passage2` answer
   evaluation* above. The process criticism still stands even though the call was right:
   it shipped before the evidence existed.
2. **`passage2_graphv2` is strictly better at retrieval, and is deliberately not what
   ships.** ✅ **Settled 18 September** — the answer run is complete at 40/40. Retrieval is
   better on every metric (doc recall@5 **98.6%**, hit@5 **97.1%**, passage recall@5
   **75.2%**, MRR **0.920**, with none of `passage2`'s doc-recall cost), and **fact
   coverage is identical to `passage2` on every one of the 40 items**. Production keeps the
   graph flag off: the pre-fixed criterion asks whether the retrieval gain reaches the
   answers, and measured twice now, on two different chunk settings, it does not.

Neither was a reason to revert, and both have now been measured together rather than one
at a time — which is what showed that the only apparent difference between them was a
scoring gap.

**The frozen baseline still reproduces exactly — verified after the 17 September
changes.** `python -m eval.run retrieval --config baseline`, diffed against the
stored run field by field: all five summary metrics identical to six decimal places
(doc recall@5 0.919048, doc hit@5 0.885714, passage recall@5 0.566667,
evidence-in-context 0.614286, MRR 0.860317) and **0 differences across 40 items ×
19 fields**, `top_docs` included.

That is the check that matters for the dedup fix, and it is the predicted result:
`rerank` sorts its output, so selecting a document's best passages by score rather
than by arrival is a no-op on the live path and changes behaviour only in the
degraded case the fix exists for. **Nothing in Stage 5 is invalidated.**

**The 18 September F05 alias fix cannot touch any retrieval number, and no rerun was
spent proving it.** `evaluate_retrieval` reads `question`, `expected_docs`,
`expected_evidence` and `expected_resolution` from each golden item and never reads
`expected_facts`, which is the only field the fix changed (`eval/run.py`, the
`evaluate_retrieval` body). Retrieval results were therefore left untouched on disk rather
than regenerated — a rerun would have rewritten nine `retrieval.json` files with a new
timestamp and identical numbers.

### Next stage

**→ Stage 6 — CI.** Stage 5 exists to give CI something meaningful to gate on, and it now has
it: **gate on the retrieval metrics only** — they are deterministic and reran identically
twice. Suggested floors, set below the measured baseline so ordinary variation does not trip
them: **doc recall@5 ≥ 0.85, MRR ≥ 0.80, passage recall@5 ≥ 0.50**. **Answer metrics stay
reported and must never gate** — they need Groq, they carry one-sample noise, and the
`max_tokens` truncation puts a floor under their reproducibility.

Ranked follow-on work, by measured leverage (tracked separately from Stage 6):

1. ~~**Raise `max_tokens`** and regenerate the 3 empty answers~~ ✅ **done** (16–17 Sep) —
   shipped as a retry rather than a raised ceiling, all three regenerated, and it
   **confirmed** the corrected multi-hop reading: chunk512 multi-hop 77.5% → **91.5%**.
2. ~~**One answer run covering `passage2` and `passage2_graphv2` together**~~ ✅ **done**
   (18 Sep) — both are complete at 40/40. `passage2` is **validated** and the graph flag is
   **settled off** on answer-level evidence. Still unmeasured at the answer level:
   `graph_provenance` (retrieval-neutral; its benefit is citation correctness) and the
   **neighbour-pair dedup**, which remains the strongest untested graph lead because it adds
   missing facts rather than reordering present ones. Both want a free retrieval run first,
   then one batched answer run.
3. **Fit the embedding window to the chunk size**, then re-run the 512 ablation. After the
   18 September rescore chunk512 still holds the highest fully-correct rate measured
   (**82.9%** against `passage2`'s 80.0%) — but the two are now **tied on fact coverage at
   87.6%**, and `passage2` reaches it *without* re-embedding and without the 256-wordpiece
   truncation. The remaining case for 512 is that last 2.9 pts, so measure whether the two
   stack before spending on it.
4. **Move the reranker off CPU** or cut its candidate count before any deployment.
5. LLM-as-judge (step 7) — only worth building with a larger token budget.

### Steps

| Step | What | State |
| --- | --- | --- |
| 0 | Freeze the corpus | ✅ `eval/corpus_manifest.yaml` |
| 1 | Golden set, 40 questions | ✅ `eval/golden_set.yaml` — all 40 reviewed (29 approved, 11 revised; 4 replaced) and validated |
| 2 | Schema + validator | ✅ `eval/schema.py`, `eval/validate.py` — 0 errors, 7 warnings |
| 3 | Metrics + unit tests | ✅ `eval/metrics.py`, `eval/text.py` — 32 eval tests, later 43 in `test_eval_metrics.py` with the refusal-classifier regression tests, inside the full passing suite |
| 4 | Retrieval runner | ✅ `python -m eval.run retrieval` — reruns to identical numbers |
| 5 | Answer runner (refusal, facts, citations, grounding, LLM cache) | ✅ `python -m eval.run answers` — baseline 40/40 |
| 6a | **Retrieval** ablations | ✅ rerank_off, graph_off, chunk512, `graph_v2` — all complete |
| 6b | **Answer** ablations | ✅ **all 40/40** — graph_off, rerank_off, chunk512 (closed 16 Sep, 1 call) and `graph_v2` (16 Sep, 40 calls). 200 answers cached |
| 7 | LLM-as-judge (optional, never gates) | ⏳ not implemented |

### What exists

- **Corpus (step 0).** 25 documents / 134 chunks, identified by sha256 with a
  per-document chunk fingerprint; 4 test fixtures listed as excluded (still
  indexed — the runner drops them from scoring; they took 22 context slots across
  40 baseline queries). `MAN-003`, `INS-004`, `SCN-003` copied into
  `demo_dataset/`, so all 25 source files are in the repo and byte-identical to the
  ingested versions.
- **Golden set (step 1).** 20 single-hop / 10 multi-hop / 5 follow-up / 5 negative,
  each with passage-level `expected_evidence`, `expected_facts` with accepted
  phrasings, fixed follow-up `history` and `expected_resolution`.
  - Review: S01–S10 decided item by item by the project owner (S04, S07, S10
    rejected). S11–S40 reviewed by Claude against the files in `demo_dataset/`
    under the owner's delegation — SCN-003 against its rendered scan image — with
    every decision in `review.notes`, recorded as `reviewed_by: pratapVansh`.
  - Replacements: S04 → SOP-002, S07 → LOG-002 (both previously unused), S10 →
    MAN-003 oil whirl; N05 replaced because the scan shows the "missing" CO
    reading (0 ppm) — only OCR lost it, so it was not a genuine negative.
  - Revised for defensibility: M06 (no reference date for "overdue"), M09 (schedule
    was context, not needed), M05 (training limits were for confined space),
    tightened bare-number phrasings (S17, M04, F03), F01 part-number variant.
- **Validator (step 2).** `python -m eval.validate`: pydantic schema with per-type
  rules, manifest membership and sha256 of every source file, chunk-fingerprint
  drift, evidence present in the indexed chunks of the named document, and every
  expected fact grounded in its documents (5 facts marked `in_source: false` —
  table cells with the unit in the header, OCR-garbled text, one derived yes/no).
  `--collection eval_chunks_512` checks evidence against the ablation collection.
- **Metrics (step 3).** Doc recall@5, doc hit@5, passage recall@5, evidence in LLM
  context, MRR, follow-up resolution, negative top score, fact coverage
  (normalised, number-boundary aware so `44 barg` ≠ `44.5 barg`), refusal outcome
  (correct / missed / false), citation precision/recall, grounding counts via
  TRACE's own classifier, latency percentiles.
- **Runners (steps 4–5).** Build the real `HybridRetriever` / `GraphRagService` as
  `app/main.py` does, never `ChatService` — no conversation, memory or user-graph
  writes. Reranker and embeddings warmed before timing; the run **aborts** if the
  reranker disables itself or the service falls back to vector-only. LLM responses
  cached on the full request hash (`eval/cache/`, gitignored); `rescore` re-applies
  answer metrics without calling the LLM; `--cache-only` scores only cached items.
- **512 ablation (step 6).** `python -m eval.chunk512` builds `eval_chunks_512` with
  TRACE's own chunker from Postgres extracted text (read only; re-chunking at 256
  through the same path reproduces all 25 frozen fingerprints). Production
  `document_chunks` untouched.

### Retrieval evaluation results — ✅ complete (35 answerable questions, deterministic)

*Reproduced in full under Final Stage 5 metrics above; kept here as the working record.*

| Metric | baseline | rerank_off | graph_off | chunk512 | graph_v2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Doc recall@5 | 91.9% | 88.6% | **98.6%** | 89.0% | **98.6%** |
| Doc hit@5 | 88.6% | 82.9% | **97.1%** | 82.9% | **97.1%** |
| Passage recall@5 | 56.7% | 50.0% | 59.5% | **77.1%** | 59.5% |
| Evidence in LLM context | 61.4% | 54.3% | 61.4% | **86.2%** | 61.4% |
| MRR | 0.860 | 0.783 | 0.906 | 0.853 | **0.920** |
| Retrieval p50 / p95 (ms) | 6485 / 8402 | **132 / 170** | 5511 / 6356 | 7542 / 9443 | 6055 / 6690 |

### Answer evaluation results — ✅ complete, all five configs at 40 / 40

**The final cross-config tables are under *Final Stage 5 metrics* above** (measured, plus the
32-item sensitivity check). What follows is the per-ablation reading that the numbers support.

**Baseline** — fact coverage 72.6%, fully correct 60.0%, false refusal 11.4%, correct refusal
5/5, citation precision/recall 77.8% / 81.9%, grounded share 48.8%. One of its 40 answers
(S14) is empty.

**Reranker off — the clearest negative result in Stage 5.** Fact coverage 63.8% (−8.9) and
fully correct 48.6% (−11.4). The damage is concentrated where ranking matters: single-hop is
**unchanged** at 62.5%, multi-hop drops 11.0 pts and **follow-up drops 40.0 pts**. It also
costs a negative — N04 asserts the B-101 internal inspection *was performed* and reports
external UT readings as its findings, the false-premise failure the negatives exist to catch.
That one is genuine and survived both classifier fixes. **Keep the reranker.**

**Graph off — no answer-level effect.** Fact coverage 73.6% vs 72.6%, and **all ten multi-hop
and all five follow-up answers score identically** with and without the graph. Only three
answers differ at all; the single genuine correctness change (S18, 2/3 → 3/3) favours
graph-off. Citation and grounding metrics are better without the graph (84.3% vs 77.8%
precision; 60.8% vs 48.8% grounded), which reflects the pre-rework merge boost pulling
entity-dense documents into the context.

**Chunk 512 — the largest answer-level gain in Stage 5.** Fact coverage 80.7% (+8.1) and
fully correct **77.1% (+17.1)**, single-hop +20.0 pts, citation precision 89.8% (+12.1),
grounded share 60.6% (+11.8), false refusal down to 8.6%, negatives 5/5. This is the direct
consequence of +20.5 pts passage recall and +24.8 pts evidence-in-context, and it is the
strongest confirmation of conclusion 1: feed the pipeline the right passage and the same model
and prompt answer correctly. **Its reported multi-hop regression does not survive inspection**
— see the correction under *Final decision*. The real remaining cost is at the retrieval
level (−10 pts multi-document recall) plus an embedding window that truncates every 512-token
chunk.

**`graph_v2` — retrieval improves, answers do not.** Detailed under *Final decision* above.
Measured: coverage 70.7%, fully correct 57.1%, negatives 5/5, differing from the baseline on
three answers of forty — two covering zero facts either way, one a truncated generation.
Identical to the baseline on the 32 items every config completed.

**What the numbers say** (detail in the report):

1. **Answer quality is gated by passage retrieval.** Facts covered: 98% when all evidence
   reached the context, 26% when none did; all four false refusals had zero evidence in
   context. This is the conclusion everything else in Stage 5 points back to.
2. **The reranker earns its quality and its cost is a deployment problem** — +11.4 pts
   fully-correct, at ~40× latency on CPU, with the slowest query at 9.4 s against the 10 s
   timeout that silently disables it.
3. **The graph does not move answers, in any wiring tested.** Reworked, it is the best
   retrieval config measured (MRR 0.920); it still leaves evidence-in-context at 61.4%,
   identical to the baseline, and the answers with it.
4. **Chunk size is the biggest lever, and the embedding window is what blocks using it.**
5. **Refusal cannot come from scores:** false-premise negatives score 0.94–1.00.
6. **Three of 200 answers were never generated** (`max_tokens=1024`), and they had been read
   as a retrieval result. Raising that limit is the one code change Stage 5 clearly earns.

### 14 September — graph rework and the N04 metric fix (no Groq calls)

Answer generation was paused for the day at the Groq cap, so this was the
deterministic half of the work: find out *why* the graph contributes nothing,
fix it, and fix the metric bug it exposed.

**Why the graph was not helping — measured, not guessed.** Running the graph arm
over all 40 golden questions and counting what it actually emits:

| | before | after (`graph_v2`) |
| --- | ---: | ---: |
| `Document` share of the facts emitted | **59.1%** | **21.2%** |
| bare "this entity exists" facts | 35.3% | 30.0% |
| document-membership edges (`REFERENCES`/`MAINTAINED_BY`/`DESCRIBES`/`INSPECTS`) | 44.8% | 37.9% |
| **domain relationship facts** (`HAS_FAILURE`, `OPERATES`, `FOLLOWS`, …) | **20.0%** | **32.1%** |
| facts emitted over 40 questions | 496 | 377 |

`Document` entities are 18% of the graph but were taking 55% of the five entity
slots, and ~80% of what reached the prompt was either a bare name or "this file
mentions this tag" — both of which the retrieved chunk already shows. **Root
cause:** `search_entities` ranks by how many query terms an entity's *name*
contains. That is a raw count, so a filename like
`MNT-001_Quarterly_PM_Cooling_Tower` beats the tag `P-101` by being longer. The
graph was spending its whole budget restating the vector arm.

**Three focused fixes**, all gated on `graph_prefer_domain_entities` (default
**off**, so the frozen baseline stays reproducible; the `graph_v2` eval config
turns it on). Nothing was deleted from Neo4j:

1. `GraphRetriever` over-fetches, then ranks by term density (coverage ÷ name
   length) instead of raw count, so matching 2 of 2 words beats 2 of 9.
2. Document-shaped entities rank below domain entities — the vector arm has
   already supplied the document and its text.
3. `ContextMerger` counts only *relationship* facts toward the merge boost. Bare
   names and membership edges no longer lift a chunk, which is what pushed
   entity-dense files over the reranker's best passage.

**Retrieval result** (deterministic, no Groq — `eval/results/graph_v2/`):

| Metric | baseline | graph_off | **graph_v2** |
| --- | ---: | ---: | ---: |
| Doc recall@5 | 91.9% | 98.6% | **98.6%** |
| Doc hit@5 | 88.6% | 97.1% | **97.1%** |
| Passage recall@5 | 56.7% | 59.5% | **59.5%** |
| MRR | 0.860 | 0.906 | **0.920** |
| Latency p50 (ms) | 6485 | 5511 | 6055 |

The graph had been *subtracting* from retrieval; it now adds to it. `graph_v2`
recovers every gain that came from switching the graph off **and beats
graph-off on MRR (0.920 vs 0.906)** — the first result in Stage 5 where keeping
the graph is better than not having it. Per item: S06 and M10 recover from
MRR 0.17 and 0.33 to **1.00**, S01 and S03 rise 0.50 → 1.00, S05 improves
slightly. One item, F02, drops 1.00 → 0.50, matching graph_off exactly; its
passage recall is 0.0 in *all three* configs, so the right passage was never
retrieved and the document's rank never mattered — a cosmetic MRR change with
no effect on the answer.

> **Measured on 16 September — and the answer is no.** The `graph_v2` answer run
> (40 calls) found **no answer-level effect**: 3 of 40 answers differ from the
> baseline, two covering zero facts either way and one truncated, and on the 32
> items every config completed the two are identical. Conclusion 1 explains why —
> `graph_v2` improves *document* ranking but leaves **evidence-in-context at
> 61.4%, identical to the baseline**, so the passages reaching the prompt never
> change. The retrieval gain below stands; it simply does not convert.
> `graph_prefer_domain_entities` stays **off** by default.

**N04 refusal-classifier bug — fixed.** `eval/metrics.py` matched
"no findings **were** recorded" but not "no findings **are** recorded", so two
answers with identical content scored `correct_refusal` and `missed_refusal`,
costing graph_off a negative on wording alone. The premise-correction pattern is
now tense-agnostic (`were|was|are|is|have been|has been|had been`). Checked
against every cached answer in all four configs: it changes **exactly one**
label — graph_off N04 → `correct_refusal` — and leaves the baseline untouched.
Stored answers were rescored with `python -m eval.run rescore` (no Groq calls);
graph_off's correct-refusal rate is now **100%**, matching baseline. Covered by
8 new tests including a regression test carrying both real N04 phrasings.

**Tests:** 1061 passed, 0 failed (was 1043 — 18 added). `python -m eval.validate`
still reports 0 errors, 7 warnings. *(Re-run 16 September after the second classifier fix:
**1080 passed, 0 failed** after the third classifier fix; validation still 0 errors /
7 warnings against both `document_chunks` and `eval_chunks_512`.)*

### How stage 5 was closed (16 September 2026)

- [x] **Finish the three baseline answer ablations.** Done 15 September: rerank_off
      completed 40/40 (3 new calls) and chunk512 reached 39/40 (39 new calls) before the
      daily cap returned at 197,749 / 200,000. All 159 cached answers were reused.
- [x] **Close the second refusal-classifier gap** (chunk512 N04). Done 16 September: the
      premise-correction pattern accepts `available|provided|listed` alongside
      `recorded|found|documented|reported|made|given`. Moves exactly one label; baseline,
      graph_off and rerank_off byte-identical. Rescored with no Groq calls.
- [x] **Finish chunk512.** Done 16 September — **1 Groq call** for the outstanding negative
      N05, 39 answers reused from cache. It is a correct refusal, so chunk512 is 40/40 and
      its negatives are **5 / 5**. No answerable metric changed, as expected for a negative.
- [x] **Measure `graph_v2` at the answer level** — the decision Stage 5 was being held open
      for. Done 16 September: **40 Groq calls**, none reusable from cache (correct — the cache
      keys on the complete request and `graph_v2` exists to change the prompt's graph facts),
      ≈20 minutes at the 8,000 TPM ceiling, inside the day's quota.
      - **Result: the retrieval gain does not reach the answers.** `graph_v2` differs from the
        baseline on 3 of 40 answers; two cover zero facts either way and the third is a
        truncated generation. On the 32 items every config completed the two are identical.
      - **Decision, against the criterion fixed before the run:** `graph_prefer_domain_entities`
        **stays off by default**. The `graph_v2` code is kept, gated and unchanged; the graph
        stays enabled. Nothing was removed from Neo4j.
- [x] **Close a third refusal-classifier gap and one fact-phrasing gap** (16 September, no
      Groq). `graph_v2`'s N04 writes the premise correction with the verb before the noun
      ("the documents contain no findings from inside the steam drum"); chunk512 and
      `graph_v2` both write S17's fact as "minimum stock level is 2", which the golden set
      accepted as "minimum stock is 2" and "minimum level of 2" but not with both words
      together. Verified against every stored answer in all five configs: together they move
      **exactly three records** and leave baseline, rerank_off and graph_off byte-identical.
      6 new tests, including two guards ("the inspection report contains no defects") that
      must **not** classify as refusals. A full audit of every missed fact in every config
      found no other scoring artefact.
- [x] **Find and correct the empty-generation artefact.** 3 of 200 answers are empty strings
      (`max_tokens=1024`): baseline S14, chunk512 M05 and M10. They score 0.00 exactly like a
      wrong answer, and two of them had been read on 15 September as a chunk-size retrieval
      regression — M05's retrieval is in fact *identical* to the baseline's.
      `summarize_answers` now reports `empty_answers` so this cannot recur silently.
- [ ] Optional step 7, LLM-as-judge — **not implemented**; only worth building with a
      larger token budget. It never gated, so it does not block closure.

**Exit criterion — met.** `python -m eval.run` prints recall@5, MRR, coverage and refusal rate
over all 40 questions ✅; reruns to the same numbers on unchanged code ✅ (retrieval, verified
twice); **every ablation has recorded figures at both levels — retrieval ✅ and answers ✅,
40/40 for all five configurations** ✅. Validator: 0 errors, 7 warnings against both
collections ✅. Backend suite: **1080 passed, 0 failed** ✅.

**Total Groq spend to close: 41 calls.** 159 of the 200 answers were reused from cache and
none were regenerated. All 200 are now cached, so every table in the report rebuilds with
`python -m eval.run rescore` + `report` and **no Groq calls at all**.

> **Provenance of the golden set.** An LLM drafted it; ground truth came from
> review against the source files, not from TRACE's output. S11–S40 were reviewed
> by Claude under delegation rather than by a cold independent human reviewer —
> the main caveat on every figure above.

---

## Stage 6 — CI ⏳ not started

**Effort: 2 days.**

**What.** `.github/workflows/ci.yml`, running on pull request and on push to
`main`.

**Why now.** CI is only worth having once there is something meaningful to run.
**Stage 5 is complete and supplies exactly that.** Gate on the *retrieval* metrics only —
they are deterministic and reran identically twice. Suggested floors, set below the measured
baseline (doc recall@5 91.9%, MRR 0.860, passage recall@5 56.7%) so ordinary variation does
not trip them: **doc recall@5 ≥ 0.85, MRR ≥ 0.80, passage recall@5 ≥ 0.50**. **Answer metrics
stay reported and must never gate** — they need Groq, they carry one-sample noise, and the
`max_tokens=1024` truncation found in Stage 5 puts a floor under their reproducibility.

> ⚠️ **Re-derive these floors before writing the workflow.** They were chosen against the
> Stage 5 baseline, which is no longer what production runs. `passage2` measures passage
> recall@5 at **73.3%**, so a 0.50 floor would let a 23-point regression through unnoticed
> — and passage recall is the metric Stage 5 identified as gating answer quality. Gate the
> *shipped* configuration, and set the floor a few points under its own measured value.
> The empty-answer retry also removes the `max_tokens` caveat above: 0 of 200 answers are
> empty now. Answer metrics still must not gate, for the other two reasons.

**Steps.**

- [ ] **Backend job:** Python 3.14, install from `requirements.txt`, run
      `pytest`.
- [ ] **Frontend job:** `npm ci`, `tsc --noEmit`, `vitest run`, `eslint`.
- [ ] **`pytest-timeout` with a 60s per-test cap.** Confirmed absent —
      `pytest --timeout=120` is rejected as an unrecognized argument. The suite
      runs in **6m02s** with no upper bound at all, so a hung test hangs the job
      until the runner kills it.
- [ ] **`pytest-cov`, report only. No floor** until one has been measured — a
      floor picked before measurement either blocks everything or means nothing.
- [ ] **eslint starts non-blocking.** Current state (10 September 2026): **42
      problems, 23 errors, 19 warnings** — down from 59/30/29. A separate
      cleanup task takes it to zero. Lint becomes blocking once the count is
      zero. `npx tsc --noEmit` is already clean, so the typecheck job can be
      blocking from day one.
- [ ] **Service containers for Qdrant and Neo4j** so the 8 integration tests that
      currently skip for lack of a live service finally run.
- [ ] **A separate eval workflow** gating on recall@5, triggered on changes to
      `services/retrieval*`, `services/rag*`, `services/reranker*`, `graph/` and
      the prompt builder, plus nightly on `main`.

**Exit criterion.** A pull request runs both jobs to green; a deliberately
introduced retrieval regression fails the eval workflow; the 8 previously
skipped integration tests report as run.

---

## Stage 7 — Embedding model versioning ⏳ not started

**Effort: half a day.**

**Confirmed still open:** `QdrantVectorStore.create_collection` writes only
`VectorParams(size, distance)` — no model name, no dimension metadata, nothing
to compare against `settings.embedding_model_name` at startup.

**What.** Record which embedding model produced the vectors in Qdrant, and
refuse to serve retrieval when the running model disagrees.

**Why now.** Every vector currently in Qdrant was produced by
`all-MiniLM-L6-v2` at 384 dimensions. Change that model and every stored vector
becomes meaningless — new queries embed into a different space and land nowhere
near the old vectors. Retrieval returns garbage with no error, no failed test
and no 500. It is the same silent-failure class as everything else in this
roadmap, except this one you trigger yourself while trying to improve the
system. **Do this whether or not stage 1 says the model needs changing** — the
danger arrives with the improvement attempt, not before it.

**Steps.**

- [ ] Store model name and vector dimension in the Qdrant collection metadata at
      creation time.
- [ ] Compare against `settings.embedding_model_name`
      (`backend/app/core/config.py:93`) on startup. On mismatch, refuse to serve
      retrieval and log loudly — a refusal is recoverable, a silently wrong
      answer is not.
- [ ] Make reindexing an explicit, documented, tested command rather than tribal
      knowledge about which script to run.

**Exit criterion.** Pointing `embedding_model_name` at a different model on a
populated collection makes the app refuse retrieval with a clear log line
instead of returning results; the documented reindex command restores service; a
test covers the mismatch path.

---

## Stage 8 — Deploy on GCP ⏳ not started

**Effort: 1–2 days. Last.**

**What.** One VM, the stage 4 compose stack, HTTPS, and a frontend on Vercel
pointed at it.

**Why now.** Because stages 1–7 have made the system correct, complete and
reproducible. Deploying earlier would have published a system nobody had
measured.

**Plan.** Use GCP's $300 / 90-day new-account credits, run until they expire,
then tear down. No architectural compromises for a free tier — the credits cover
a machine large enough to run the system exactly as built. This is a college
project; the deployment exists to demonstrate the system, not to run
indefinitely.

**Target.** `e2-medium` (2 vCPU, 4 GB RAM), region nearest the user. 4 GB fits
the backend as built — torch, `all-MiniLM-L6-v2` and the ms-marco cross-encoder
all stay in-process. No externalizing inference, no slimming, no model changes.

**Steps.**

- [ ] Provision `e2-medium`, 30 GB disk, static external IP.
- [ ] Firewall: 22, 80, 443 only. The backend port is never exposed to the
      internet.
- [ ] Install Docker and compose, clone the repo, run the stage 4 compose stack.
- [ ] Add Caddy to the compose stack for HTTPS via Let's Encrypt.
- [ ] Postgres containerized on the same VM.
- [ ] Qdrant Cloud, Neo4j Aura and Groq stay exactly as they are — unchanged
      from local.
- [ ] Frontend on Vercel, pointed at the backend.

### Cross-origin auth — this will break if ignored

The refresh-token cookie is `SameSite=lax` (`refresh_cookie_samesite`,
`backend/app/core/config.py:44`). A `*.vercel.app` frontend calling a bare IP is
cross-site, so the browser stops sending the cookie and authentication silently
fails — login appears to work, then every refresh is unauthenticated.
Separately, an HTTPS page cannot call an HTTP backend at all: mixed content is
blocked outright, so the backend needs a certificate, which needs a hostname.

Three options, cheapest first:

1. **Free subdomain** (DuckDNS, nip.io) so Caddy can issue a certificate.
2. **Next.js rewrite** proxying `/api` through Vercel so the browser sees a
   single origin. Simplest — but verify the SSE streaming endpoint
   (`POST /api/chat/stream`) does not get buffered by the proxy.
3. **Real domain**, ~$10/year, if the first two fight back.

- [ ] Pick one and record which, and why, in this file.

### Production settings — flip together or not at all

- [ ] `backend_cors_origins` set to the frontend URL, credentials allowed.
- [ ] `refresh_cookie_secure=true`. Secure cookies over HTTP vanish silently, so
      this and HTTPS must land in the same change.
- [ ] `security_headers_hsts_enabled=true`.
- [ ] `refresh_cookie_domain` set if using subdomains.

### Cost control

- [ ] Set a GCP budget alert at **$1 before launching anything**. An alert
      configured after the spend starts is worthless.
- [ ] On teardown, **delete** resources rather than stopping them. A static IP
      attached to a stopped instance still bills, as do orphaned disks and
      snapshots.

**Teardown checklist** — one pass, in this order:

- [ ] Delete the Compute Engine instance
- [ ] Release the static external IP
- [ ] Delete the boot disk and any additional disks
- [ ] Delete snapshots and custom images
- [ ] Delete the firewall rules
- [ ] Delete the Vercel project or unset its backend URL
- [ ] Revoke the Groq / Qdrant Cloud / Neo4j Aura credentials issued for the
      deployment
- [ ] Confirm the billing page shows zero active resources

**Exit criterion.** A public URL where the Copilot answers a question from the
demo corpus with correct citations. Run a smoke test of a handful of queries
confirming the deployed system matches local behaviour — this is environment
verification, not quality testing. Quality was settled in stages 1 and 5.

---

## Resolved — was known debt

Kept rather than deleted: the diagnosis is the useful part, and the measurement
is what justifies the change.

**The documented chunk configuration was wrong in five places.** *Resolved
18 September 2026.* This file and `stage5_report.md` described the production pipeline as
**256/64** in five places. `config.py:124` is `chunk_overlap = 40`, and it has been since
`a86cefe` (6 September), which lowered it from 64 while tuning against the probe. The
corpus in Qdrant — 138 chunks over 29 documents — was built at **256/40**;
`probe_results.md` recorded that correctly from run 2 onward and was never reconciled with
the prose elsewhere. Every "256/64" is now "256/40". **The "512/64" references are correct
and were left alone:** `eval/chunk512.py` sets `CHUNK_SIZE = 512` and `CHUNK_OVERLAP = 64`
explicitly for the ablation, so that config really does use a 64-token overlap. *No code
changed* — the code was right and the documentation was wrong, which is the safer of the
two ways round but the harder one to notice.

**A fifth scoring gap: F05 accepted "running hours" but not "operating hours".**
*Resolved 18 September 2026.* Three correct answers — chunk512, rerank_off and
`passage2_graphv2` — state the oil-change interval as "every 4,000 operating hours" and
were scored **0.0 coverage**. `passage2` scored 1.0 on the same interval only because its
evidence block quoted the source verbatim as "4000 hours", which the alias list did accept.
The pipelines were never the difference; the alias list was — and it was the **only**
fact-coverage difference between `passage2` and `passage2_graphv2`, i.e. it was deciding
the graph flag.

Fixed to the same standard as the four refusal-classifier gaps: two phrasings added to
`golden_set.yaml` F05, both **evidenced by a stored answer**, no speculative variants;
verified across every stored answer in every config to move **exactly three records**;
3 tests pin it; rescored with `python -m eval.run rescore` (no Groq). The moves are
chunk512 coverage 84.7% → **87.6%** and follow-up 80.0% → **100.0%**, and rerank_off
63.8% → **66.6%**, follow-up 40.0% → **60.0%**. baseline, graph_off, graph_v2 and
`passage2` are unchanged. `python -m eval.validate` stays at 0 errors, 7 warnings.

**The lesson, since this is the fifth of its kind:** every one of these gaps was found by
reading an answer that the metric had marked wrong, and every one was a *phrasing* gap
rather than a pipeline defect. Before accepting any conclusion drawn from a coverage or
refusal delta, read the answers behind the items that moved.

**Scanned tables were silently lost to OCR misconfiguration.** *Resolved
6 September 2026.* A three-page scanned permit ingested clean — `indexed`, six
chunks, no warning — having dropped every data row of the gas test record it
exists to capture. Cause: `--psm 3` in `processing/ocr/engine.py` performs
automatic page segmentation, analyses the ruled table as layout, and discards
the region. Fix: `--psm 11`, sparse text, which performs no layout analysis and
reads the glyphs. **9/18 → 17/18 known markers recovered across the three pages,
for +0.3 s per page.** All five gas-test rows now survive re-ingestion, and the
detector serial corrected itself from `ASX-88214` to the true `A5X-88214`. All
13 probe questions re-ran with every rank and score byte-identical, and the
prose OCR result held at 0.9951 against 0.9975. Measured in
`backend/eval/probe_results.md`, run 5.

`_adaptive_threshold` was the other suspect and was **kept**, on measurement. It
was the stage that destroyed the digits at PSM 3, but at PSM 11 it is not
implicated: it wins or ties on every scan condition tested and is faster on all
of them, and removing it made a heavy-noise page exceed **twelve minutes**
without completing, against 4.9 s with it. Two residual issues are recorded
below rather than hidden by this fix.

**Residual, narrower than the bug it replaced:** PSM 11 recovers a table's values
but not its row structure — it emits roughly one cell per line, so a reading is
no longer bound to its timestamp, and the LEL/H₂S/CO columns did not survive at
all. No thresholded configuration preserves rows. Separately, heavy scanner noise
defeats the pipeline entirely (0/12 markers with thresholding on). Both need real
noisy scans to tune against rather than synthetic ones, and neither is a
regression — they were masked by the larger failure.

**Re-verified 17 September 2026 against the ingested corpus, and left alone.**
Reading the stored extraction for `SCN-003_Hot_Work_Permit_and_Gas_Test_Record.pdf`
(`extraction_method = pymupdf+tesseract`, 3 pages, 2,649 chars): the detector serial
reads **`A5X-88214`** and the earlier misread `ASX-88214` is **absent**; `LEL`, `H2S`
and `CO` are all present. Its three golden-set questions
(`tag: ocr_source`) score **100% doc recall@5** and 72.2% passage recall — at or above
the corpus average. The residual above is visible in the same text: values survive,
row bindings do not (`PLANT / UNIT.`, `EQUIPMENT TAG`, `Cracker Unit …`, `L-401 …`
each land on their own line), plus minor glyph noise (`Lip.` for `Ltd.`, `Al` for
`A1`). The live path also passes `source_dpi=RENDER_DPI` explicitly, so PyMuPDF's
96-DPI PNG metadata cannot trigger the documented over-upscaling. **No change made.**

> **The honest limit on that verification:** exactly **one** of the 29 active documents
> exercises OCR. `SCN-001` and `SCN-002` carry a text layer and extract via plain
> `pymupdf`. "OCR is reliable" rests on one 3-page scan, so it is evidence that the
> pipeline works, not that it generalises. The `--psm 11` change was measured on the
> same document. Real noisy scans remain the gap.

**OCR robustness and cost bounding — ✅ added 17 September 2026.** *Quality* was left
alone (it is correct, and one document is not enough evidence to tune against). What
was missing was everything around it.

**Profiled first**, on `SCN-003` at the configured 300 DPI:

| Stage | Cost | Share |
| --- | ---: | ---: |
| `_denoise` (`fastNlMeansDenoising`) | 1,151 ms | **92.6% of preprocessing** |
| `_adaptive_threshold` | 38 ms | 3.1% |
| `_auto_rotate` | 53 ms | 4.3% |
| `_normalize_dpi` (with `source_dpi=300`) | 0 ms | — |
| **Preprocessing total** | **1,243 ms/page** | |
| **End to end, incl. Tesseract** | **9.36 s/page** | 28.1 s for 3 pages |

The profile also **confirms the `source_dpi` contract empirically**: PyMuPDF's PNG
metadata reports **96.012 DPI** for a page rendered at 300, and without the explicit
`source_dpi` the page is upscaled 2480×3509 → 2827×4000. The live path passes it, so
this does not happen — but the margin is real, not theoretical.

`_denoise` is **not** touched: the roadmap already measured that removing it made a
heavy-noise page exceed twelve minutes. Tuning its parameters needs more than one
scan to measure against, so it stays.

Two defects fixed instead:

1. **One unreadable page destroyed the whole document.** The page loop raised on the
   first `ImageOcrExtractionError`, so a 100-page scan with a single bad page produced
   **no text at all** — and the ingestion job then retried, re-running every expensive
   page twice more before failing permanently. At 9.4 s/page that is ~47 minutes to
   produce nothing. Now the page is skipped and logged, keeps its slot so page
   numbering stays truthful, and the rest of the document is indexed. **Every** page
   failing is still an error: there is nothing to index and the retry is worth taking.
2. **No bound on OCR work per document.** Uploads are capped at 100 MB, which
   comfortably admits a 500-page scan (~78 minutes at the measured rate), and the queue
   drains **serially on one worker** — so one document could stall every other. New
   `ocr_max_pages` (default **100**, ≈16 minutes worst case) caps it. Pages past the
   cap are not read; the document still indexes and is flagged rather than passed off
   as complete.

Partial reads are now visible instead of silent: `ScannedPdfOcrResult` carries
`failed_pages` and `skipped_pages` with an `is_partial` property, the processor writes
`ocr_truncated` / `ocr_failed_pages` into document metadata, and the completion log
records both. **Nothing in the current corpus is affected** — its only OCR'd document
is 3 pages, and the 177-page document is a `.docx`, which never reaches OCR.

**Per-image work was already bounded, and is now verified rather than assumed.**
`_normalize_dpi` downscales anything oversized to `MAX_IMAGE_DIMENSION`: 5000×5000 →
4000×4000 and 8000×2000 → 4000×1000, while a correctly-rendered 2480×3509 page at
300 DPI passes through untouched. PIL's decompression-bomb guard is active at 89.5 M
pixels. So a hostile or merely enormous image cannot blow up the denoiser — the cost
ceiling per page holds regardless of input size. **No change made.**

**Regression-checked against the real file:** `SCN-003` still extracts **2,649
characters** — byte-identical to the stored extraction — at confidence 0.877, with
`is_partial=False`, and `A5X-88214` still correct. 10 tests; all 54 OCR tests pass, and the full backend suite is **1100 passed, 0 failed**.

## Known debt — not scheduled

Real problems, deliberately unscheduled. Each entry says why it can wait.

### Found during the production-readiness audit (17 September 2026)

**Checked and found correct — no change made.** Recorded so the same ground is not
re-audited: OCR on the live path (`services/processors/` → `extract_scanned_pdf_text`
→ `extract_image_text`, which passes `source_dpi=RENDER_DPI` explicitly, so PyMuPDF's
96-DPI PNG metadata cannot cause the documented over-upscaling — see the OCR entry
under *Resolved*); JWT startup validation (`validate_security_configuration` is
fail-fast on an empty, placeholder or short secret, and is called from `main.py`
before traffic); upload error handling (every failure mode maps to its own HTTP
status, and duplicate content is rejected by checksum before any processing);
Qdrant configuration (payload indexes on `content` and `document_id`,
`full_scan_threshold` 10,000 — brute force is correct at 138 points and HNSW takes
over above it); startup degradation (Qdrant, Neo4j and Groq each fail to a warning,
not a crash); secrets hygiene (`.env` and `.env.docker` gitignored, only the
`.example` files tracked); and the frontend — `tsc --noEmit` clean, 61 vitest tests
passing, no TODO/mock/placeholder strings anywhere under `app/`, `components/`,
`lib/` or `hooks/`, loading and error state on every data-fetching hook, and honest
empty states (the dashboard renders `N/A` and surfaces a load failure rather than
falling back to placeholders).

**The `passage2` change shipped without the suite being re-run — and it had
broken a test.** ✅ **Fixed 17 September 2026.** `retrieval_chunks_per_document`
was raised to 2 as a production default, and `dedup_by_document` was rewritten
to support it. The rewrite replaced the original score comparison with "keep
the first *per_document* seen", which is correct only while the caller is
guaranteed to pass a score-sorted list.

`test_retrieval_dedup.py::test_keeps_the_best_even_when_the_weaker_chunk_came_first`
— a test written specifically to pin "insertion order must not decide which
passage represents a document" — **was failing**, and so was the end-to-end
Copilot-path test. Neither was noticed because the suite was not re-run after
the change.

Why it mattered in production: `rerank` sorts, but returns fusion order
untouched whenever reranking is off — **including after a runtime timeout
disables it**, which is the documented deployment blocker. In exactly that
degraded state the *worse* passage was chosen to represent each document.

*Fix:* select each document's best passages by score, independent of arrival
order (`sorted` is stable, so equal scores stay deterministic). The second
failure was a genuinely stale expectation — `top_k` still counts documents, but
each now brings up to two passages — and was rewritten to assert the intended
behaviour, with the one-passage case pinned explicitly so it cannot drift
again. 4 tests added or rewritten.

**The dashboard counted the wrong queue, so its Processing Queue tile could
never appear.** ✅ **Fixed 17 September 2026.** `DashboardService` read
`ProcessingJobRepository.count_pending_jobs()` — the `processing_jobs` table
belonging to the dead `app/processing/` stack. Live ingestion records its work
in `ingestion_jobs`. Verified against the development database:
`processing_jobs` holds **3** stale rows, none `pending`; `ingestion_jobs`
holds **44**.

The count was therefore structurally pinned at 0, and
`executive-dashboard.tsx` renders the tile only `if (api.pending_jobs > 0)` —
so the panel was unreachable no matter how many documents were queued. On a
fresh deployment with a batch upload it would have read "nothing queued" while
the worker was saturated.

*Fix:* `DocumentRepository.count_unfinished_ingestion_jobs()`, counting
`pending` **and** `processing` — a job being worked on is still outstanding,
and counting only `pending` would blink the tile to 0 for the whole of a long
OCR run. The API shape is unchanged, so no frontend change was needed. 5 tests.

**The batch neighbour fetch keeps one relationship per entity pair, and it may
keep the wrong one.** `get_neighbors_for_entities` dedups on
`f"{entity_id}:{neighbour_id}"` — the *pair*, not the relationship — so when two
entities are joined by more than one edge, only the first record survives.
`GraphRetriever`'s own `seen` key does include the relationship type and would
have kept both; it never gets the chance.

Measured against the live graph: **10 of 87 relationships (11.5%) sit on pairs
carrying two distinct edges**, and every one of those pairs is the same shape —
a domain relationship alongside a membership edge:

```
SOP-001_Pump_Start-Up_Procedure ↔ P-101   ["FOLLOWS", "REFERENCES"]
SOP-002_Pump_Shut-Down_Procedure ↔ P-102  ["FOLLOWS", "REFERENCES"]
```

`REFERENCES` is in `graph_membership_relationships` — the "this file mentions
this tag" class that Stage 5 measured as contributing nothing, and that
`graph_prefer_domain_entities` exists to suppress. Which of the two survives is
decided by record order under `ORDER BY neighbor.name`, which says nothing about
relationship type. So the retriever can silently discard `FOLLOWS` and keep
`REFERENCES` — dropping the informative half of the pair before any of the
graph_v2 ranking can see it.

*Not fixed:* the one-line change (add the type to the dedup key) alters what the
graph arm emits, and therefore the prompt and the frozen baseline. It is a
retrieval change and wants the same treatment as the other two — a free
retrieval run, then an answer run before it ships. **This is the strongest
remaining graph lead**, because unlike `graph_v2` and `graph_provenance` it adds
facts that are currently missing rather than reordering ones already present.

**Deployment: the ingestion queue has no claim protocol.**
`list_pending_ingestion_jobs` is a plain `SELECT … WHERE status='pending'
LIMIT n` — no `FOR UPDATE SKIP LOCKED`, no atomic status claim — and `main.py`
starts one worker task per process. Two processes polling the same queue both
select the same jobs and ingest each document twice: duplicate chunks,
duplicate embeddings, duplicate graph writes.

It is latent today only because the container runs `uvicorn app.main:app` with
no `--workers` flag, which defaults to 1. **Nothing enforces that.** Adding
`--workers N` for request throughput at deploy time silently enables double
ingestion. *Documented in `config.py` beside
`processing_queue_worker_enabled`; not fixed*, because a correct claim protocol
is a change to the ingestion state machine and wants its own test pass. Before
scaling out: disable the worker on every replica but one, or build the claim.

**No per-document processing timeout, and no page cap.** 🟡 **Half fixed
17 September 2026.** The expensive half — OCR — is now bounded by `ocr_max_pages`
(see the OCR entry under *Resolved* for the profile that sets the number), and a
failing page no longer destroys the document.

**Still open:** there is still no *general* per-document timeout. Nothing bounds
a pathological non-OCR document — a `.docx` with an enormous table, a PDF whose
text layer explodes on extraction — and the queue still drains **serially on a
single worker**, so any such document blocks the ones behind it. *Deferred
because:* a wall-clock timeout makes a slow-but-legitimate document fail after
3 retries, which is a policy decision, and unlike OCR there is no measured cost
profile to set the budget from. A page cap worked for OCR precisely because
cost there is linear in a quantity known before the work starts.

**`search_entities` is a full label scan on the RAG hot path.** It matches with
`toLower(n.name) CONTAINS toLower(t)`, which no RANGE index can serve. The live
graph has eight RANGE indexes and **no full-text index**, confirmed with
`SHOW INDEXES`. At 171 nodes this is free; it is linear in entity count, it
runs on every graph-enabled query, and `graph_prefer_domain_entities`
over-fetches 6×. *Deferred because:* the fix is a Neo4j full-text index plus
`db.index.fulltext.queryNodes`, which changes match semantics and ranking —
a retrieval change that needs measuring against the golden set, not a drop-in.

**`app/processing/` is two stacks, one of them dead.** Live ingestion runs
through `services/processing_factory.py` → `services/processors/*`. The
parallel `app/processing/{factory,manager,worker,processors}` tree — `PdfProcessor`,
`DocxProcessor`, `PptxProcessor`, `ExcelProcessor`, `ImageProcessor`, ~2,000
lines — is referenced by nothing outside itself; `get_processing_manager()` and
`run_processing_worker()` have no callers. Only `app/processing/{models,
service,repository,queue,ocr}` are live. *Deferred because:* deleting it is
easy but unrelated to shipping, and the OCR engine underneath it **is** live.
It is worth knowing that the careful-looking `PdfProcessor` is not what runs.

**Legacy `ingestion_jobs` rows use a status the code no longer writes.** Eight
rows sit in status `queued`, all belonging to soft-deleted documents from
3–5 July 2026. The worker selects `pending`, so they are inert. Harmless, but
they make `SELECT status, count(*)` misleading to read.

### Found during the stage 4.5 run (13 September 2026)

**Graph build counts relationships it *tried* to write, not ones it wrote.**
✅ **Fixed 17 September 2026.** `GraphBuilderService.process_document` added
`len(rels)` to `relationships_merged` per batch, but `_merge_rels_batch` starts
with `MATCH (src:Entity) … MATCH (tgt:Entity)`, which silently skips any
relationship whose endpoint is not already a node. Measured:
`build_knowledge_graph.py` logged `Equipment_Register.xlsx: 16 nodes, 16 rels`,
and Neo4j holds **0** relationships for that document — its `LOCATED_IN` /
`PART_OF` targets ("Cracker Unit", departments) are never created as entities.
The build total of "155 relationships" was inflated the same way (87 edges
exist after the clean rebuild).

*Fix:* the batch query ends with `RETURN count(rel) AS written` and the builder
counts that instead of the input list, warning per batch when the two differ
and naming how many were dropped. Both callers benefit — live ingestion
(`services/processors/graph_processor.py`) and the `build_knowledge_graph.py`
backfill share `process_document`. The Cypher was verified against the live
container inside a rolled-back transaction; the graph is unchanged at 171
nodes / 87 relationships. 3 tests.

**Still open:** the *data-completeness* half. Relationships whose endpoints were
never extracted as entities are still dropped — the fix reports the loss
honestly rather than preventing it. That needs the extractor work below.

**Graph facts carry the wrong source document.** 🟡 **Fixed behind a flag,
measured, not promoted (17 September 2026).** Entity nodes are shared across
documents (`MERGE` on a type+name hash); `source_document` is kept from the
*first* writer (`COALESCE`) while `document_id` is overwritten by the *last*.
`GraphRetriever` labels a fact with the neighbour node's `source_document`
rather than the relationship's own — which relationships do carry, and which
`get_neighbors_for_entities` already returns.

**Measured against the live graph, 17 September 2026: the neighbour node's
value disagrees with the relationship's own on 63 of 87 relationships
(72.4%).** All 87 relationships have their own `source_document` populated.

It is not cosmetic: `ContextMerger` keys `doc_facts_map` on the fact's
`source_document`, so it decides which chunk a fact attaches to and therefore
the graph boost, and `_graph_only_item` turns the name into a context item that
can be **cited** — a citation naming a document the fact did not come from.
(The label itself never reaches the prompt text; neither prompt builder renders
it. The earlier note that it matters "for citation precision" is right, but by
that indirect route.)

*Implementation:* `graph_fact_relationship_provenance`, default **off**, gated
exactly like `graph_prefer_domain_entities`, with a fallback to the old value
for legacy edges carrying no provenance. New eval config `graph_provenance`.
3 tests.

**Retrieval measurement (`eval/results/graph_provenance/`, no Groq):
retrieval-neutral.** Doc recall@5 91.9%, doc hit@5 88.6%, passage recall@5
56.7% and evidence-in-context 61.4% are **identical to the baseline on all 40
items**. MRR moves 0.860 → 0.858 on one item (M10, rank 3 → 4). Because
evidence-in-context is unchanged item for item, the passages reaching the LLM
are the same — so this cannot change answer quality through retrieval.

*Not promoted.* The measurement shows it is **safe**, not that it helps; its
benefit is citation correctness, which is an answer-level metric. Same bar as
`graph_v2`: it ships when an answer run says so, not before.

**Two different graph extractors.** `scripts/build_knowledge_graph.py` adds
~250 lines of title- and table-based inference (`DESCRIBES`, `INSPECTS`,
`LOCATED_IN`, …) that live ingestion (`GraphProcessor`) does not run, and does
not set `source_type` / `target_type` on relationships. The same document
produces a different subgraph depending on whether it was uploaded or
backfilled. *Deferred because:* choosing one needs the stage 5 graph ablation.

**The regex relationship extractor is narrow and noisy.** "P-4545 feeds
TK-4546" yields a relationship; "Pump P-4545 feeds Tank TK-4546" and
"Valve V-4547 maintains pressure for Pump P-4545" yield none. The same run
created junk entities named "caused by" and "failure caused". *Deferred
because:* improving extraction without a golden set is guesswork.

**The README is stale in four places.** Verified against the tree on
10 September 2026: (1) Audit Logging is marked 🚧 with "No read API exists yet,
so the trail cannot be viewed" — `GET /api/audit-logs` exists and the page is
wired to it; (2) **Investigation Records is marked ✅** — the model, service and
schemas were deleted with the agent framework, and only an orphaned table
remains; (3) Docker is listed as "Containerized deployment (planned)" and under
a future-work heading — a Dockerfile and two compose files are committed;
(4) the LLM is described as Llama 3.3 70B while `.env` runs
`openai/gpt-oss-120b`. *Deferred because:* it is documentation, and stage 4.5
plus stage 4's remaining items will change what the correct text is. Fix it in
one pass afterwards, not four.

**The retrieval probe is not reproducible — superseded.** The five probe runs were
never scripted. *Resolved by stage 5:* `python -m eval.run retrieval` is the
permanent, rerunnable replacement, and 10 of the 13 probe questions survive in
the golden set (verbatim or documented revisions). The probe's own historical
figures remain unreproducible prose.

**`app/agents/` still exists as stale bytecode.** The source is gone but
`backend/app/agents/framework/**/__pycache__/*.pyc` remains on disk — around 60
compiled modules for code that no longer exists, including
`python_tools.cpython-314.pyc` and `rca_agent.cpython-314.pyc`. Harmless
(nothing imports them; Python will not load a `.pyc` without its source in
these layouts) but misleading to anyone reading the tree, and it makes
`backend/app/agents/` look like a live package. *Deferred because:* it is
`git clean -xdf backend/app/agents` and nothing depends on the timing.

**Five tests assume an all-green environment — re-counted 18 September 2026.**
The count here was **two** and was wrong. Measured with the Docker daemon stopped,
`test_health_degradation.py` reports **5 failed, 2 passed**:
`::test_runtime_disabled_reranker_is_reported`, `::test_failed_model_load_is_reported`,
`::test_unwarmed_model_is_reported`, `::test_reranking_switched_off_is_not_degraded` and
`::test_optional_store_down_is_degraded_not_unavailable`. All five start by asserting the
health endpoint reports `"ok"`, which is only true when *every* optional service — Qdrant,
Neo4j, Groq — is reachable. They pass only because the stage 4.5 containers are up; stop
them and all five fail for a reason that has nothing to do with the behaviour they cover.

The same environment also costs *time*: with Qdrant unreachable every call burns
`QDRANT_TIMEOUT_SECONDS=30` × `QDRANT_MAX_RETRIES=3`, and the suite drops from 2m42s to
roughly 18 tests in 15 minutes. That is the more expensive half of this debt, and CI will
hit it the first time a service container fails to come up.

*Deferred because:* the right fix (pin the components under test) belongs with stage 6,
where CI decides which services exist. **Do not size that work from "two tests".**


**Retrieval scores whole questions against whole passages.**
The cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) scores one query
against one passage as wholes, and two question shapes fail because of it. A
compound question buries the passage answering its second half: asking the
bearing heating temperature *and* the locknut torque together drops the torque
table from rank 4 to **rank 22**, score 0.100131 to **0.000083** — a **1,200×**
difference on the same passage, from the same index, caused only by the question
also asking something else. A naturally-phrased question loses a table to prose
about that table: asking for a thickness reading held only in table rows returns
the paragraph discussing a *different* grid position, with the table itself at
**rank 20**, 0.000088, against **rank 1**, 0.217502, when the grid is named
explicitly — a **2,470×** difference. Both cases score as *hits* under a
document-level metric, because the right document does reach the top 5; only
reading the passage shows it cannot support an answer. Document dedup was the
expected cause and is not: with dedup disabled the answer-bearing chunk is still
absent in both. Measured in `backend/eval/probe_results.md` run 4, against a
7,444-word manual and a 15-section inspection report. The fix is query
decomposition — split a multi-part question, retrieve per part, merge — plus
either table-aware sub-queries or serialising table rows into sentence-shaped
text at ingestion. *Deferred because:* decomposition puts an LLM call ahead of
every retrieval, changing latency and cost on the hot path and changing what
every consumer of the RAG path receives; stage 5's harness is what would show
whether it pays for itself. Until then, treat the probe's headline score as an
upper bound: it counts documents, not answers.

**The answer prompt never asks for inline citation markers.**
`services/prompt_builder.py` numbers the retrieved chunks `[1] [2] [3]` when it
builds the context block (line 178), but neither `DEFAULT_SYSTEM_PROMPT` nor
`GRAPH_AWARE_SYSTEM_PROMPT` instructs the model to cite them in its answer — the
rules ask only for an "Evidence" section naming documents. One line added to
both prompts, telling the model to mark each claim with the `[n]` of the passage
supporting it, would give the Copilot UI real claim-level provenance: today it
can only resolve markers the model happens to echo, plus literal document-name
mentions, and it deliberately leaves everything else unlinked rather than guess
at attribution. *Deferred because:* it changes model output for every consumer
of the RAG path, so it needs stage 5's eval harness to confirm the added
instruction does not cost answer quality — a UI improvement is not a reason to
change what the model says unmeasured.

**Answer grounding is lexical overlap, not entailment.**
`services/evidence_classification.py` scores each sentence of an answer by
content-token overlap with the cited chunk. Measured over 18 real answers from
this corpus it separates well — 78.8% on an answer's own citations against
30.1% on unrelated ones, a 48.7pp gap versus 15.5pp for the heuristic it
replaced — but that ~30% floor is the method's ceiling: word overlap cannot
tell support from coincidence. The Copilot therefore reports counts
("12 grounded · 1 hedged · 3 unsupported") and never a per-sentence verdict.
A real fix is entailment: an NLI model or a cross-encoder scoring each
sentence against the chunk it cites. *Deferred because:* it adds a second
model to the serving path, and stage 5's harness is what would tell us whether
the added latency buys enough accuracy to be worth it.

**RBAC has no test file** despite being the security boundary of the whole
application — `backend/tests/` contains no rbac, permission or role test module.
*Deferred because:* it is a contained, well-understood gap that adds no risk of
regression while untouched; stage 6 makes adding it enforceable.

**9 `except: … pass` blocks in `backend/app`** — down from 26; the agent
framework held 17 of them. What remains is in `pdf_processor.py` (3),
`ranking_service.py` (2), and one each in `main.py`, `tracing.py`,
`docx_processor.py` and `vector_store.py`. Each is a place a failure becomes
invisible. *Deferred because:* they need to be read individually, and stage 5's
harness will surface which ones actually hide wrong answers.

**Local disk storage blocks horizontal scaling.** `core/storage/` already has
the seam — `StorageBackend` is a Protocol with `local_storage.py` as the only
implementation. *Deferred because:* one VM is the deployment target and the
abstraction is already in place for the day it is not.

**29 stray scripts** — 7 at the repo root (`benchmark.py`, `inspect_db.py`,
`inspect_qdrant.py`, `investigate_chunks.py`, `test_api_graph.py`,
`test_neo4j_connection.py`, `test_trace_startup.py`), 15 in `backend/scripts/`,
7 in `demo_dataset/`. Several are one-off debugging leftovers; a few are
load-bearing. *Deferred because:* telling the two apart requires reading all of
them, and none of them break anything by existing.

**No backup or restore procedure** for Postgres, Qdrant or Neo4j. *Deferred
because:* the demo corpus is regenerable from `demo_dataset/` and the deployment
is temporary by design.

**No error tracking or log shipping.** *Deferred because:* a single VM with
`docker compose logs` is adequate at this scale; see the production monitoring
note below for what would come first if it were not.

---

## Notes

### Terminology: this is AI engineering / LLMOps, not MLOps

No models are trained here. All three — the embedding model, the reranker and
the LLM — are pretrained and used as-is. There is no retraining pipeline, no
feature store and no experiment tracking, and calling this MLOps invites
questions the project cannot answer.

Stages 5 and 7 are the genuinely LLMOps parts of this roadmap: eval-driven
development against a fixed golden set, and model-artifact versioning against
the data that artifact produced.

### Production monitoring (future, not scheduled)

Log retrieval scores, result counts and citation counts per query; alert on
distribution drift as the corpus grows. Offline eval catches regressions before
deploy; production logging catches them after. Both are needed for a system that
runs indefinitely — this one is not intended to.

---

## Decisions already made

Closed. Reopen only with a reason that did not exist when they were made.

| Decision | Rationale |
| --- | --- |
| **The AI agent framework is deleted, not deferred** | 10 agents, 43 tools, an orchestrator, a planner, multi-agent workflows and agent memory — 40% of the backend — served one page that did a worse job than the Copilot beside it. The evidence, all verified by execution before deleting: report generation **never ran once** (`ReportGenerationAgent` guarded on `context.retrieved_documents`, which nothing ever wrote, so every report request returned a no-evidence stub); the `investigations` table held **0 rows** against 33 ingested documents because no route passed a DB session; RCA ran **degraded and silent** (peer delegation returned empty because `context.orchestrator` was never set); `MultiAgentExecutor` was constructed per request and **never called**; and `ChatService` — the actual product — **never imported a line of it**. The one real capability, per-sentence answer grounding, was ported to `services/evidence_classification.py` first. Report prompts kept as reference in `docs/salvage/report-prompts.md`. |
| **Document intelligence, not an asset platform** | The seven asset-management pages deleted in Phase 0 had no backend, no data model and no owner. Assets exist as Neo4j graph entities extracted from documents; nothing owns them as first-class records, and building that ownership is a different product. |
| **The six withdrawn tools are gone, not parked** | Unregistered in Phase 0 — three unsandboxed sinks for LLM-generated input (`exec()`, arbitrary HTTP, arbitrary SQL), three fabricating success without acting — and deleted with the framework. Superseded by the row above. Any of these capabilities is a fresh build against a real integration, not a re-registration. |
| **Managed datastores, not self-hosted** — ⚠️ *reopened 13 September 2026* | Qdrant Cloud, Neo4j Aura and Groq stay managed. Self-hosting all three on one 4 GB VM trades a working system for an operations problem the project has no reason to own. **Reason to reopen:** the free Aura instance disappeared without warning, and local development now runs Neo4j and Qdrant in Docker (stage 4.5). Settle this before stage 8, which still assumes Aura + Qdrant Cloud. |
| **GCP with new-account credits, not AWS** | $300 / 90 days covers an `e2-medium` running the system exactly as built, with no free-tier compromises. |
| **The deployment is temporary, and teardown is planned** | This is a college project. The deployment demonstrates the system; it is not meant to run indefinitely. The teardown checklist in stage 8 is part of the plan, not a contingency. |
| **Make it work before deploying it** | A deployed system that returns wrong answers is worse than an undeployed one. Stages 1–7 come first; stage 8 is last. |
| **Containerization is development tooling, not deployment** | Stage 4 exists for reproducible environments and CI service containers. Stage 8 reuses the images. Finishing stage 4 is not being deployed. |
