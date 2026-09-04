# TRACE — Roadmap

**Branch:** `phase-0-stabilize` · **Last verified:** 31 August 2026

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
| Vector store | Qdrant Cloud — `all-MiniLM-L6-v2`, 384-dim, cosine |
| Graph | Neo4j Aura |
| LLM | Groq — Llama 3.3 70B |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| OCR | Tesseract + OpenCV preprocessing |

### Verified current state

Every figure below was checked against the tree after the agent-framework
deletion (4 September 2026), not taken from the README.

| Fact | Value | How checked |
| --- | --- | --- |
| Agent framework | **deleted** | `backend/app/agents/` no longer exists |
| Registered tools / agents | 0 / 0 | no registry; `main.py` has no `register()` calls |
| `backend/app` | 196 files, 24,195 lines | was 275 files / 42,560 before the cut |
| `main.py` | 261 lines, lifespan 119 | was 530 / 375 |
| Files over 500 lines | 7 | was 19 |
| `except: … pass` blocks | 9 | was 26 |
| Migrations | 19 files, head `017_investigations` | `ls backend/alembic/versions`, `alembic heads` |
| Backend tests | 979 passed, 7 skipped, 5m48s | `pytest -q` |
| Frontend tests | 61 passed | `npx vitest run` |
| Frontend routes | 12 | `find frontend/app -name page.tsx` |
| eslint | 42 problems (23 errors) | `npx eslint .` |
| Pinned direct deps | 34 (all `==`) | `grep -c "==" backend/requirements.txt` |
| Lockfile | `backend/requirements.lock.txt`, 129 lines | present |
| Docker / CI | none | no `Dockerfile`, no `docker-compose*.yml`, no `.github/` |

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

> **Note on state:** only the query-understanding and RCA work is committed. The
> tool unregistration, requirements fix, page deletions and README corrections
> are complete in the working tree but uncommitted (38 changed paths on
> `phase-0-stabilize`). Commit before starting stage 1.

---

## Stage 1 — Retrieval probe

**Effort: 1 hour. Do this first.**

**What.** Ask ten questions with known answers directly against retrieval, with
the LLM bypassed, and grade what comes back.

**Why now.** The core claim of this product is that asking a question returns
the right document. Nothing currently verifies that. The 1160 passing backend
tests prove the *mechanics* — chunks get chunked, endpoints return 200, the
reranker loads. None prove the *semantics*: that the chunk returned is the right
chunk. Semantic failures are silent. There is no exception, no failing test, no
500 — the answer comes back fluent, confident, cited and wrong. This stage needs
nothing built: Qdrant, Neo4j and Groq are already connected and the demo corpus
is already indexed.

**Steps.**

- [ ] Pick 10 questions from the demo corpus (`demo_dataset/`) whose correct
      source document you know by hand.
- [ ] Include at least 3 tag-specific questions naming an exact identifier
      (`P-101`, a part number, an error code).
- [ ] Include exactly 1 question about equipment that does not exist in the
      corpus. Correct behaviour is an empty or refusing result, not a confident
      nearest neighbour.
- [ ] Call the retriever directly — `VectorRetriever.retrieve` /
      `HybridRetriever` in `backend/app/services/hybrid_retriever.py`. Do not go
      through `/api/rag/query`; the LLM must be out of the loop.
- [ ] Print the top 5 chunks per question with scores and source document names.
- [ ] Mark each question **right** / **wrong** / **plausible-but-wrong**. The
      third bucket matters most: a chunk from the correct document about the
      wrong pump is the failure this product cannot afford.
- [ ] Write the results into `backend/eval/probe_results.md` — stage 5's golden
      set starts from this file.

**Interpretation.**

| Score | Meaning |
| --- | --- |
| 8–10 right | Healthy. Proceed to stage 3. |
| 5–7 right | Unreliable. Tune before showing this to anyone. Stage 2 has work. |
| Under 5 | Structurally broken in extraction, chunking or embedding. Stop and diagnose which. |

**Known risk.** `all-MiniLM-L6-v2` is a general-purpose sentence embedder. It
may not distinguish `P-101` from `P-205` — same prefix, same shape, tiny
semantic distance, and nothing in its training taught it that the digits carry
all the meaning.

**Correction to a prior assumption.** It has been said that TRACE's "hybrid"
retrieval is vector + graph only, with no lexical matching. That is not what the
code does. `QdrantVectorStore.hybrid_search`
(`backend/app/services/vector_store.py:644`) fuses vector search with a
full-text arm using RRF. But the lexical arm is **a filter, not a ranker**:
Qdrant returns a uniform score for filter-only queries, so results are re-scored
locally by `_term_coverage` — the fraction of query terms appearing in the
chunk. There are no sparse vectors and no BM25 scoring. So exact-match retrieval
exists but is coarse, which is precisely why the tag-specific questions above
are the important ones.

**Exit criterion.** `backend/eval/probe_results.md` exists, contains 10 graded
questions with their top-5 chunks and scores, and ends with a
right/wrong/plausible-but-wrong tally and a one-line verdict against the table
above.

---

## Stage 2 — Fix what the probe exposes

**Effort: varies. May be zero.**

**What.** Whatever stage 1 proves is broken. Nothing else.

**Why now.** Fixing retrieval after building an eval harness on top of it means
rebuilding the harness. Fixing it after deploying means deploying twice.

**Do not pre-plan this stage.** The shape of the work depends entirely on the
probe result. Two likely shapes, for orientation only:

- **Tag questions fail, general questions pass.** The likely fix is real sparse
  vectors in Qdrant — natively supported — for genuine dense + sparse hybrid,
  replacing the filter-and-rescore arm described above. Roughly a day.
- **Retrieval returns the right chunks but answers are still wrong.** Then it is
  a prompt or context-assembly problem in `services/prompt_builder.py` or
  `services/rag_service.py`, not a retrieval problem. Different fix entirely.

- [ ] Read the stage 1 tally and name the failure mode in one sentence before
      writing any code.
- [ ] Fix that failure mode.
- [ ] Re-run the stage 1 probe unchanged and compare tallies.

**Exit criterion.** The stage 1 probe re-run scores 8+ right, or the remaining
failures are documented in `probe_results.md` with a stated reason for accepting
them.

---

## Stage 3 — Complete the half-built features

**Effort: 2 days.**

**What.** Give every advertised feature a backend.

**Why now.** "Working" means the product does what its own UI says it does. This
is cheap, bounded, and removes the last surfaces that show users nothing while
claiming to show them something — the same class of problem Phase 0 deleted
seven pages to fix.

**Steps.**

- [ ] **Audit-log read endpoint.** `audit_logs` and `AuditService` already
      collect data from 19 call sites across five services (`auth_service`,
      `document_service`, `document_processing_service`,
      `document_processing_queue`, `user_management_service`). There is simply
      no reader — `backend/app/api/routes/` has no audit module. Add
      `GET /api/audit-logs` with pagination and role filtering.
- [ ] Wire the Audit Logs page to it. It currently renders
      `const AUDIT_LOGS: AuditLogEntry[] = [];`
      (`frontend/components/operations/audit/audit-logs-page-content.tsx:17`) —
      the same fabricated-surface pattern Phase 0 removed, now living inside a
      component instead of a mock-data file. This is the cheapest real feature
      remaining.
- [ ] **Replace the 3 swallowed promises** in
      `frontend/components/ai-workspace/copilot/copilot-page-content.tsx` —
      `.catch(() => {})` at lines 162, 299 and 304 — with visible error states.
      This is the exact pattern that once hid dashboard 500s for weeks.
- [ ] Update the README status markers as each lands: Audit Logging 🚧 → ✅.

**Exit criterion.** The Audit Logs page shows real rows from a real request, and
no `.catch(() => {})` remains in `copilot-page-content.tsx`.

---

## Stage 4 — Containerize for development

**Effort: 2 days.**

**What.** Reproducible environments and CI service containers.

**Why now.** Stage 5's eval harness needs a reproducible seeded corpus, and
stage 6's CI needs Qdrant and Neo4j as service containers. Both are downstream
of this. **This is not deployment** — nothing goes online here. Stage 8 reuses
these images; that is the only relationship between them.

**Steps.**

- [ ] **`backend/Dockerfile`** — multi-stage, `linux/amd64`.
  - [ ] CPU-only torch: `--index-url https://download.pytorch.org/whl/cpu`.
        Default torch drags in the CUDA runtime libraries, which are dead weight
        on a CPU host and add gigabytes to the image.
  - [ ] Bake both models in at build time. `all-MiniLM-L6-v2` and the ms-marco
        cross-encoder download from HuggingFace on first use; without a
        pre-download the first request after every restart stalls 30–60s.
  - [ ] Tesseract binary via `apt` — `pytesseract` is only a wrapper around a
        binary that must be installed separately.
  - [ ] Install from `requirements.lock.txt`, not `requirements.txt`.
  - [ ] Non-root user; `HEALTHCHECK` against `/api/health`.
- [ ] **`docker-compose.yml`** — backend + Postgres + a one-shot migration
      service running `alembic upgrade head`, which the backend `depends_on`
      with `condition: service_completed_successfully`. Migrations must **not**
      run implicitly on application boot.
- [ ] **`docker-compose.local.yml`** — overlay adding Qdrant and Neo4j for local
      development and CI.
- [ ] **Named volumes for Postgres data *and* `backend/storage`.** Documents are
      written to the API host filesystem (`core/storage/local_storage.py`), so
      without a volume every container restart wipes every uploaded document.
- [ ] **`.env.docker.example` in two flavours** — one using compose service
      names for local services, one using the cloud URLs (Qdrant Cloud, Neo4j
      Aura, Groq).

**Exit criterion.** `docker compose -f docker-compose.yml -f docker-compose.local.yml up`
on a clean machine brings up backend, Postgres, Qdrant and Neo4j; migrations run
once in their own service; `/api/health` returns healthy; a document uploaded
before `docker compose restart` is still there afterwards.

---

## Stage 5 — Evaluation harness

**Effort: 3 days.**

**What.** Automate what stage 1 did by hand, against a fixed, human-authored
golden set.

**Why now.** Compose gives a reproducible seeded corpus, so the same questions
produce comparable numbers run to run. Before stage 4 they would not have.

**Steps.**

- [ ] **`backend/eval/golden_set.yaml`** — 40 questions:
  - 20 single-hop (answer lives in one document)
  - 10 multi-hop (answer requires joining two or more)
  - 5 follow-up (exercises the Phase 0 query-understanding work: a question
    whose meaning depends on the prior turn)
  - 5 negative (equipment not in the corpus; correct behaviour is refusal)
  - Each entry carries: `question`, `expected_docs`, `expected_facts`, `type`.
- [ ] **Deterministic metrics — safe to gate on:** recall@5, MRR, answer
      coverage (does the answer contain `expected_facts`), refusal rate on
      negatives.
- [ ] **Judged metrics — measure, never gate:** faithfulness and citation
      precision via LLM-as-judge on Groq. These move between runs for reasons
      that have nothing to do with the code.
- [ ] **Ablations** — measurements worth having, not gates on anything:
  - [ ] Reranker on/off. It costs 300–700ms per query; it is worth knowing
        whether it earns that.
  - [ ] Graph retrieval on/off. This is the entire justification for running
        Neo4j.
  - [ ] Chunk size variants.

> **The golden set cannot be generated automatically.** Ground truth must be
> human-authored. Using TRACE to produce it is circular — the system would be
> graded against its own output. Using another LLM produces a second opinion
> with its own errors, not a reference. An LLM may **draft** candidate questions
> from the documents, but every question, every `expected_doc` and every
> `expected_fact` must be read and corrected by a human against the source. One
> day of manual work buys a permanent automated check.

**Exit criterion.** `python -m eval.run` prints recall@5, MRR, coverage and
refusal rate over all 40 questions, reruns to the same numbers on unchanged
code, and the three ablations have recorded baseline figures.

---

## Stage 6 — CI

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
- [ ] **`pytest-timeout` with a 60s per-test cap.** The suite runs in 3m45s today
      with no upper bound at all, so a hung test hangs the job until the runner
      kills it.
- [ ] **`pytest-cov`, report only. No floor** until one has been measured — a
      floor picked before measurement either blocks everything or means nothing.
- [ ] **eslint starts non-blocking.** Current state: 59 problems (30 errors, 29
      warnings). A separate cleanup task takes it to zero, starting with the 11
      `react-hooks/set-state-in-effect` errors, which are genuine render-loop
      hazards rather than style. Lint becomes blocking once the count is zero.
- [ ] **Service containers for Qdrant and Neo4j** so the 8 integration tests that
      currently skip for lack of a live service finally run.
- [ ] **A separate eval workflow** gating on recall@5, triggered on changes to
      `services/retrieval*`, `services/rag*`, `services/reranker*`, `graph/` and
      the prompt builder, plus nightly on `main`.

**Exit criterion.** A pull request runs both jobs to green; a deliberately
introduced retrieval regression fails the eval workflow; the 8 previously
skipped integration tests report as run.

---

## Stage 7 — Embedding model versioning

**Effort: half a day.**

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

## Stage 8 — Deploy on GCP

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

## Known debt — not scheduled

Real problems, deliberately unscheduled. Each entry says why it can wait.

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
| **Managed datastores, not self-hosted** | Qdrant Cloud, Neo4j Aura and Groq stay managed. Self-hosting all three on one 4 GB VM trades a working system for an operations problem the project has no reason to own. |
| **GCP with new-account credits, not AWS** | $300 / 90 days covers an `e2-medium` running the system exactly as built, with no free-tier compromises. |
| **The deployment is temporary, and teardown is planned** | This is a college project. The deployment demonstrates the system; it is not meant to run indefinitely. The teardown checklist in stage 8 is part of the plan, not a contingency. |
| **Make it work before deploying it** | A deployed system that returns wrong answers is worse than an undeployed one. Stages 1–7 come first; stage 8 is last. |
| **Containerization is development tooling, not deployment** | Stage 4 exists for reproducible environments and CI service containers. Stage 8 reuses the images. Finishing stage 4 is not being deployed. |
