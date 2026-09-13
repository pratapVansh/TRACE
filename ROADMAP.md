# TRACE — Roadmap

**Branch:** `main` · **Last verified:** 13 September 2026 (stage 4.5 verification run)

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
| `backend/app` | 197 files, 24,603 lines | `find backend/app -name "*.py"` |
| `main.py` | 261 lines | `wc -l` |
| Files over 500 lines | 6 | `find … -exec wc -l` (was 7) |
| `except: … pass` blocks | 10 | `grep -A1` over `backend/app` |
| Migrations | 19 files, single head `017_investigations` | `alembic heads` |
| Backend tests | **1011 passed, 0 failed, 0 skipped, 5m14s** (13 Sep, Neo4j + Qdrant in Docker, working tree incl. uncommitted graph fix). Was 1002 passed / 2 failed / 7 skipped the same morning with no local services | `pytest -q -rs` |
| Frontend tests | 61 passed, 6 files | `npx vitest run` |
| Frontend typecheck | clean | `npx tsc --noEmit` |
| Frontend routes | 12 | `find frontend/app -name page.tsx` |
| eslint | 42 problems (23 errors, 19 warnings) | `npx eslint .` |
| Pinned direct deps | 34 (all `==`) | `grep -c "==" backend/requirements.txt` |
| Lockfile | `backend/requirements.lock.txt`, 138 lines | present |
| API routers mounted | 17 under `/api` | `main.py` `include_router` calls |
| Docker | **backend image built 10 Sep and full stack run once**; Neo4j + Qdrant containers in daily use since 13 Sep | `docker image inspect trace-backend:dev`, `docker ps -a` |
| Frontend container | **none** | no `frontend/Dockerfile`; not a compose service |
| CI | **none** | no `.github/` |
| `pytest-timeout` | **not installed** | `pytest --timeout=120` → unrecognized argument |

**The two health-test failures were the dead graph, and are gone.**
`test_health_degradation.py::test_runtime_disabled_reranker_is_reported` and
`::test_reranking_switched_off_is_not_degraded` assert a baseline of
`status == "ok"`. With the Aura instance deleted (and later with nothing on
`127.0.0.1:7687`) health was `degraded`, so both failed. With the Neo4j
container up they pass. They still assume an all-green environment — see
*Known debt*.

### Live services, checked 13 September 2026

| Service | State |
| --- | --- |
| Neo4j (Docker `trace-neo4j-1`, 5.26) | **healthy** — cleared and rebuilt from Postgres after cleanup: **171 nodes / 87 relationships**, nodes from all 29 active documents, 0 stale nodes |
| Qdrant (Docker `trace-qdrant-1`, v1.18.3) | **healthy** — `document_chunks`, **138 points**, exactly the 138 chunks of the 29 active Postgres documents (per-document counts match, no orphans) |
| Qdrant Cloud | parked — still configured in `.env` as comments, not used |
| Neo4j Aura | **gone** — hostname does not resolve |
| Groq | **healthy** — `openai/gpt-oss-120b` |
| PostgreSQL | native local (`localhost:5432`) — 29 active documents / 138 chunks, 16 soft-deleted (incl. the 3 `STAGE45-E2E-*` verification uploads) |

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
      *Uncommitted.*
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

## Stage 5 — Evaluation harness 🟡 partially complete — retrieval evaluation done, answer-level ablations incomplete

**Stage 5 is NOT fully complete.** The harness, the golden set, the retrieval
evaluation and the baseline answer evaluation are done; the answer-level ablations
are not. **Current blocker: the Groq free-tier daily token limit** — not code.

**Effort: 3 days** (≈3.5 with the corpus freeze). Carried out 13 September 2026.
**Nothing is committed** — all Stage 5 files are uncommitted in the working tree.

**Full results and interpretation: [`backend/eval/stage5_report.md`](backend/eval/stage5_report.md).**
Generated tables: `backend/eval/results/comparison.md`.

### Status summary (13 September 2026)

| Area | State |
| --- | --- |
| Evaluation harness (validator, metrics, retrieval + answer runners, LLM cache) | ✅ complete |
| Golden set — 40 questions | ✅ reviewed and validated (`python -m eval.validate`: 0 errors, 7 warnings) |
| **Retrieval evaluation** — baseline + all 3 ablations (rerank_off, graph_off, chunk512) | ✅ **complete** (baseline rerun reproduced identical numbers) |
| Backend tests | ✅ **1043 passed, 0 failed, 0 skipped** |
| **Answer evaluation — baseline** | ✅ **complete, 40 / 40** |
| **Answer ablation — graph_off** | 🟡 **23 / 40** — stopped when the Groq daily quota refused further calls |
| **Answer ablation — rerank_off** | ❌ **0 / 40** — not started, no quota |
| **Answer ablation — chunk512** | ❌ **0 / 40** — not started, no quota |
| LLM-as-judge | ⏳ **not implemented** |
| Blocker | Groq free-tier daily token limit (200,000 tokens, rolling window) |
| Remaining work | **97 answer calls** (graph_off 17 + rerank_off 40 + chunk512 40) |
| Cached answers | **63 preserved** in `backend/eval/cache/llm/` (gitignored) — must be reused after the quota resets, not regenerated |
| Git | **Nothing committed** |

### Steps

| Step | What | State |
| --- | --- | --- |
| 0 | Freeze the corpus | ✅ `eval/corpus_manifest.yaml` |
| 1 | Golden set, 40 questions | ✅ `eval/golden_set.yaml` — all 40 reviewed (29 approved, 11 revised; 4 replaced) and validated |
| 2 | Schema + validator | ✅ `eval/schema.py`, `eval/validate.py` — 0 errors, 7 warnings |
| 3 | Metrics + unit tests | ✅ `eval/metrics.py`, `eval/text.py` — 32 eval tests, inside the 1043 passing |
| 4 | Retrieval runner | ✅ `python -m eval.run retrieval` — reruns to identical numbers |
| 5 | Answer runner (refusal, facts, citations, grounding, LLM cache) | ✅ `python -m eval.run answers` — baseline 40/40 |
| 6a | **Retrieval** ablations | ✅ rerank_off, graph_off, chunk512 — all complete |
| 6b | **Answer** ablations | 🟡 graph_off 23/40 · rerank_off 0/40 · chunk512 0/40 — blocked by the Groq daily token limit (resume attempted 13 Sep 19:52, stopped at the cap after 5 new calls) |
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

| Metric | baseline | rerank_off | graph_off | chunk512 |
| --- | ---: | ---: | ---: | ---: |
| Doc recall@5 | 91.9% | 88.6% | **98.6%** | 89.0% |
| Doc hit@5 | 88.6% | 82.9% | **97.1%** | 82.9% |
| Passage recall@5 | 56.7% | 50.0% | 59.5% | **77.1%** |
| Evidence in LLM context | 61.4% | 54.3% | 61.4% | **86.2%** |
| MRR | 0.860 | 0.783 | **0.906** | 0.853 |
| Retrieval p50 / p95 (ms) | 6485 / 8402 | **132 / 170** | 5511 / 6356 | 7542 / 9443 |

### Answer evaluation results — 🟡 baseline complete, ablations incomplete

**Baseline answers — ✅ complete (all 40 questions, one LLM sample each):**

| Metric | Baseline |
| --- | ---: |
| Fact coverage (35 answerable) | **72.6%** |
| Fully correct (all expected facts) | 60.0% |
| False refusal (answerable) | 11.4% |
| Correct refusal (5 negatives) | **5 / 5** |
| Citation precision / recall | 77.8% / 81.9% |
| Grounded sentence share | 48.8% |
| LLM latency p50 / p95 (uncached) | 2.7 s / 5.5 s |

**Graph-off answer ablation — 🟡 partial, 23 / 40** (S01–S20, M01–M03). Both configs
scored on the same 23 questions:

| Metric (23 matched questions) | baseline | graph_off |
| --- | ---: | ---: |
| Fact coverage | 67.4% | 68.8% |
| Fully correct | 56.5% | 60.9% |
| False refusal | 13.0% | 13.0% |
| Citation precision | 75.4% | 88.1% |
| Citation recall | 84.8% | 89.1% |
| Grounded sentence share | 49.2% | 58.1% |

Only S18 changed fact coverage. No measurable answer benefit from the graph on these
23 questions; its effect on 7 of 10 multi-hop, all follow-up and all negative
questions is still unmeasured.

**Reranker-off answer ablation — ❌ 0 / 40. Chunk-512 answer ablation — ❌ 0 / 40.**
Their answer-level effect is not measured; only their retrieval effect (table above).

**What the numbers say** (detail in the report):
1. **Answer quality is gated by passage retrieval.** Facts covered: 98% when all
   evidence reached the context, 26% when none did; all four false refusals had
   zero evidence in context.
2. **Reranker:** +6.7 pts passage recall, +0.077 MRR, +16.7 pts on long-document and
   compound questions — at ~40× latency on CPU, with the slowest query at 9.4 s
   against the 10 s timeout that silently disables it.
3. **Graph, as wired, hurts retrieval:** `ContextMerger`'s per-fact score boost lifts
   entity-dense documents over the reranker's best passage (S05, S06, M10).
4. **Chunk 512:** biggest passage-level gain (+20.5 pts) but −10 pts multi-document
   recall, embedding truncation, and answer effect not yet measured.
5. **Refusal cannot come from scores:** false-premise negatives score 0.94–1.00.

### Remaining to close stage 5

- [ ] **Finish the answer-level ablations — blocked by the Groq free-tier daily token
      limit, not by code.** 97 answer calls remain (graph_off 17, rerank_off 40,
      chunk512 40; ≈330,000 tokens at ≈3,400 per call) against a rolling
      200,000-token daily cap — at least two more days on the free tier.
      - Reuse the 63 cached answers; do not regenerate them.
      - Resume: `python -m eval.run answers --config graph_off rerank_off chunk512`,
        then `python -m eval.run report`.
      - Partial progress can be scored without API calls: `--cache-only`.
      - Then update `backend/eval/stage5_report.md` and this section.
- [ ] Optional step 7, LLM-as-judge — **not implemented**; only worth building with a
      larger token budget.

**Exit criterion.** `python -m eval.run` prints recall@5, MRR, coverage and
refusal rate over all 40 questions ✅; reruns to the same numbers on unchanged
code ✅ (retrieval, verified twice); the three ablations have recorded figures —
**retrieval ✅, answers 🟡 (graph_off 23/40, rerank_off 0/40, chunk512 0/40)**.
Stage 5 closes only when the answer-level ablations are complete.

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
Stage 5 supplies that; before it, CI would gate on mechanics alone — the exact
blind spot stage 1 exists to expose.

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

## Known debt — not scheduled

Real problems, deliberately unscheduled. Each entry says why it can wait.

### Found during the stage 4.5 run (13 September 2026)

**Graph build counts relationships it *tried* to write, not ones it wrote.**
`GraphBuilderService.process_document` adds `len(rels)` to
`relationships_merged` per batch, but `_merge_rels_batch` starts with
`MATCH (src:Entity) … MATCH (tgt:Entity)`, which silently skips any relationship
whose endpoint is not already a node. Measured: `build_knowledge_graph.py`
logged `Equipment_Register.xlsx: 16 nodes, 16 rels`, and Neo4j holds **0**
relationships for that document — its `LOCATED_IN` / `PART_OF` targets
("Cracker Unit", departments) are never created as entities. The build total of
"155 relationships" is similarly inflated (87 edges exist after the clean
rebuild; some of the gap is cross-document `MERGE`, the rest silent drops).
*Deferred because:* it is a reporting and data-completeness gap, not a crash.
Stage 5's graph on/off ablation is what shows whether the missing edges matter.

**Graph facts carry the wrong source document.** Entity nodes are shared across
documents (`MERGE` on a type+name hash); `source_document` is kept from the
*first* writer (`COALESCE`) while `document_id` is overwritten by the *last*.
`GraphRetriever` (`services/hybrid_retriever.py:132`) labels a fact with the
neighbour node's `source_document` rather than the relationship's own. Seen
live: `P-4545 INPUT_TO TK-4546` attributed to a document that has no
relationships, `bearing failure CAUSED_BY misalignment` attributed to
`MAN-003…`. *Deferred because:* the answer text was still correct; it matters
for citation precision, which stage 5 measures.

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

**Two tests assume an all-green environment.**
`test_health_degradation.py::test_runtime_disabled_reranker_is_reported` and
`::test_reranking_switched_off_is_not_degraded` both start by asserting the
health endpoint reports `"ok"`, which is only true when *every* optional
service — Qdrant, Neo4j, Groq — is reachable. They failed until 13 September
2026 for a reason that has nothing to do with the reranker they exist to cover,
and pass now only because the stage 4.5 containers are up; stop Neo4j and they
fail again. *Deferred because:* the right fix (pin the components under test)
belongs with stage 6, where CI decides which services exist.


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
