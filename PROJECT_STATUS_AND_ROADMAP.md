# TRACE — Project Status & Roadmap

**Audit date:** 20 August 2026 · **Revised:** 20 August 2026 (post-fix)
**Branch:** `main` · **Migration head:** `017_investigations`
**Backend tests:** 1121 passed, 8 skipped · **Frontend:** typecheck clean, 33 tests, build green

This document records what was verified working, what is still broken, and what
separates the current build from a production-quality system. Everything in
"Verified working" was exercised against the live services, not inferred from code.

> **Correction (revision 2).** The first revision of this document claimed nine
> frontend pages "render hard-coded fixtures". That was wrong — it was inferred
> from the presence of a `mock-data` import rather than its contents. Nearly
> every mock constant is an **empty array**; those pages render empty states, not
> fabricated records. Section 2 has been rewritten accordingly. The mistake
> overstated the gap between claimed and delivered functionality.

---

## 1. Current status

### Verified working

| Layer | Evidence |
| --- | --- |
| **PostgreSQL** | Schema at head; `alembic check` reports no model drift. 23 live documents, 24 chunks, 24 embeddings. |
| **Qdrant** | Collection `document_chunks`, status green, 384-dim Cosine (matches `all-MiniLM-L6-v2`), payload indexes on `content` + `document_id`, **24 vectors = 24 chunks**. |
| **Neo4j** | Connects over `neo4j+s://` with certificate verification on. Aura 5.27, ~57 ms. 91 nodes, 79 relationships, 7 relationship types, 10 indexes. |
| **Retrieval** | Vector, full-text, and hybrid all rank the correct document first. Cross-encoder reranker loads at startup and scores exact matches at 0.99. |
| **Knowledge graph** | Natural-language questions resolve to entities and facts. Hybrid retrieval returns `merged`/`graph` items with facts attached. |
| **RAG** | `/api/rag/query` returns grounded answers with 5 real citations. `/api/rag/graph-query` returns 22 graph facts + 10 citations. |
| **Agents** | Routing is deterministic (3/3 runs). RCA → RCA agent, maintenance → Maintenance agent, document lookup → Document agent, each with correct tools. |
| **Dashboard API** | `/api/dashboard` returns live figures (23 documents, 91 entities, 79 relationships, 2 conversations, recent uploads). |
| **Metrics API** | `/api/metrics` in JSON and Prometheus formats, plus `POST /api/metrics/reset`. |
| **Authentication** | Login issues JWT; refresh token is `HttpOnly`, `SameSite=lax`, `Path=/api/auth`, 7-day expiry. All protected routes 401 unauthenticated. |
| **RBAC** | Registration yields `Viewer`. Viewer gets 403 on `/api/admin/users` and `/api/graph/statistics`, 200 on `/api/documents`. Enforced via `require_permission(...)` dependencies. |
| **Rate limiting** | 10 requests / 60 s on auth. Verified: 9×401 then 429. |
| **Security headers** | CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy` all present. HSTS correctly gated behind a setting. |
| **CORS** | Preflight from `http://localhost:3000` returns correct allow-origin/credentials. |
| **Frontend** | TypeScript clean, production build succeeds (24 routes), 33 tests pass. Dashboard renders behind the auth proxy. |

### Recently repaired

**Infrastructure reconnection**

- Neo4j `neo4j+s://` failed on Windows because Aura's chain embeds the SSL.com
  root, which the Windows store lacks and OpenSSL therefore rejects. Fixed by
  trusting the OS store **and** certifi — verification stays on.
- The backfill script skipped any document that already had chunks, so a fresh
  Qdrant could never be repopulated except via `--force` (which needlessly
  re-chunks and re-embeds). It now re-indexes from stored embeddings.
- Graph entity search matched the whole query string, so every natural-language
  question returned zero entities and the graph arm of hybrid retrieval was
  silently inert.
- `build_knowledge_graph.py` could not run at all (missing `sys.path` bootstrap).
- Applied the pending `017_investigations` migration.

**Three endpoints that returned 500 on every call**

- `/api/dashboard` — the service built `DashboardResponse` without the connection
  flags the schema required, so Pydantic raised before the route could fill them
  in. The flags now default to `False` and the route overwrites them with live
  `app.state` values.
- `/api/metrics` — awaited three synchronous functions (`snapshot`,
  `prometheus_output`, `reset`). Both output formats and the reset endpoint were
  affected; only the JSON default had been noticed.
- `/api/chat/conversations/archived` — declared below
  `/conversations/{conversation_id}`, which matched first and tried to parse
  `"archived"` as a conversation id. Moved above it.

All three are covered by `backend/tests/test_api_smoke.py` (9 tests). Each test
was validated by reintroducing its defect and confirming the failure.

**Frontend**

- The Executive Dashboard swallowed API errors (`.catch(() => {})`) and fell back
  to an empty placeholder, so a 500ing endpoint looked like "no data yet". It now
  shows an explicit error banner. This is what made the page appear mock-backed.

---

## 2. Remaining issues

### Frontend: empty pages, not fake pages

No page renders fabricated records. The picture is:

| Page | State | What it needs |
| --- | --- | --- |
| Executive Dashboard | **Wired and working** | — |
| Copilot, Knowledge Graph, Documents, Search, Upload, Admin Users | **Wired** | — |
| AI Agents (catalogue) | **Hardcoded** — the one real case: a static list of 7 agents with `status: "active"` | An `/api/agents` listing endpoint |
| Audit Logs | Empty state | A read endpoint; `audit_logs` table and service already exist |
| Assets, Asset Hierarchy, Maintenance, Compliance, SOP Library, Roles, Settings | Empty state | An entire backend domain each — no data model exists |

The README marks Executive Dashboard and Audit Logging as complete (✅).
The dashboard now genuinely is; audit logging collects data but exposes no API,
so the page cannot show it.

### Data hygiene

- **`test.pdf`** is a phantom row: live and `queued`, `storage_uri` `/test/test.pdf`,
  100 bytes, checksum of 64 literal `a`s, no file on disk. It is correctly
  skipped by both pipeline scripts but permanently inflates the document count
  (33 total → 23 live → 22 processable). It also surfaces in the dashboard's
  recent-uploads list, which is the most visible symptom.
- 10 soft-deleted test uploads (`notes.txt`, `test_upload.txt`, …) remain in
  `documents`. Harmless, but they are why "33 documents" never matched reality.

### Testing gaps

- The suite now has route-level smoke coverage, but it is narrow: it asserts the
  three previously-broken endpoints plus a global route-shadowing invariant. Most
  endpoints still have no test that simply calls them.
- No RBAC/permission test file exists, despite RBAC being a headline feature.
- `pytest-cov` is not installed; coverage is unmeasured and ungated.
- Frontend has 3 test files / 33 tests for 24 routes — effectively no component
  or integration coverage. Nothing would have caught the swallowed dashboard error.

### Code quality debt

- `npx eslint .` reports **54 problems (30 errors, 24 warnings)**. Next.js 16
  no longer runs lint during `next build`, so these ship silently. Notably
  **11 × `react-hooks/set-state-in-effect`** (a real render-loop hazard) and
  11 × `no-explicit-any`.
- Seven stray scripts at repo root (`inspect_db.py`, `test_api_graph.py`,
  `benchmark.py`, …) that are neither tests nor packaged tooling.
- `/api/demo/admin` ships unconditionally. It is permission-gated so it is not a
  vulnerability, but a demo route does not belong in a production bundle.

### Agent quality

- RCA and Maintenance agents return **confidence 0.95 / 0.8 with zero citations**,
  while the Document agent returns 0.4 confidence *with* 3 citations. Confidence
  is anti-correlated with evidence, which undermines the citation-coverage and
  hallucination metrics the observability layer claims to track.

### Deployment readiness — currently none

There is **no `Dockerfile`, no `docker-compose.yml`, no CI workflow, no
`.dockerignore`, no `Makefile`**. Every run is manual and machine-specific. This
is the single largest gap between the current build and a deployable product.

Also unaddressed: no structured-log shipping, no error tracking (Sentry or
equivalent), no backup/restore procedure for Postgres/Qdrant/Neo4j, and secrets
live in a local `.env` with no vault path exercised.

---

## 3. What production quality requires

| Area | Requirement |
| --- | --- |
| **Containerisation** | `Dockerfile` for backend and frontend, `docker-compose.yml` for the full stack (Postgres, Qdrant, Neo4j), `.dockerignore`. |
| **CI/CD** | GitHub Actions: lint + typecheck + backend tests + frontend tests + build on every PR; block merge on failure. |
| **Route-level tests** | Extend the smoke suite to every endpoint, not just the three that broke. |
| **Coverage gate** | Install `pytest-cov`, set a floor (start at current level, ratchet up). |
| **Secrets** | Move off `.env` to a managed secret store; the Vault client already exists but is unexercised. |
| **Observability** | Ship logs and traces somewhere queryable; wire error tracking. The metrics endpoint now works and can feed Prometheus. |
| **Backups** | Documented, tested restore for all three datastores. |
| **Migrations in deploy** | `alembic upgrade head` as an explicit, gated deploy step. |
| **Load testing** | Establish p95 latency budgets for RAG and agent execution under concurrency; nothing is currently measured. |
| **HTTPS** | Enable HSTS, set `REFRESH_COOKIE_SECURE=true`, verify `SameSite` behaviour behind a real domain. |

---

## 4. Roadmap

### Phase 1 — Stabilise
1. ~~Fix the three 500-ing endpoints.~~ **Done.**
2. ~~Add smoke tests that would have caught them.~~ **Done** (9 tests, each validated against its reintroduced defect).
3. Delete the `test.pdf` phantom row and the soft-deleted test uploads.
4. Clear the 30 lint errors, starting with `set-state-in-effect`.
5. Remove or env-gate `/api/demo/admin`; relocate the seven root-level scripts.

### Phase 2 — Deployability
1. `Dockerfile` × 2 + `docker-compose.yml` for the whole stack.
2. GitHub Actions CI running lint, typecheck, and both test suites.
3. `pytest-cov` with a coverage floor.
4. Documented deploy runbook including the migration step.

### Phase 3 — Complete the product surface
1. Add `/api/agents` so the AI Agents page reflects the real registry instead of
   a hardcoded list — the only genuinely hardcoded data left in the frontend.
2. Build the audit-log read API and wire the Audit Logs page; the table already
   collects the data, so this is the cheapest real feature available.
3. Decide, per remaining empty page (Assets, Maintenance, Compliance, SOP, Roles,
   Settings), whether to build the backend domain or remove the page. Seven
   permanently empty pages cost more credibility than fewer complete ones.
4. Correct the README's ✅ markers to match delivered functionality.

### Phase 4 — Quality & trust
1. Fix agent confidence calibration so it tracks citation coverage.
2. Require citations for RCA and Maintenance answers; suppress or flag
   uncited claims.
3. Frontend component and integration tests for the wired pages, including
   error states — nothing currently catches a swallowed API failure.
4. RBAC permission-matrix test suite.

### Phase 5 — Scale & features
1. Load testing and p95 latency budgets.
2. Incremental re-indexing (currently a full backfill).
3. Multi-tenancy / organisation isolation.
4. Streaming agent responses in the UI end-to-end.
5. OCR quality pass — confidence thresholds and a review queue for
   low-confidence extractions.

---

## 5. Honest summary

The **intelligence core is real and works**: ingestion, chunking, embedding,
vector search, reranking, knowledge-graph construction, hybrid retrieval, RAG
with citations, and multi-agent routing were all verified end-to-end against
live cloud services. Authentication, RBAC, rate limiting, and security headers
are properly implemented, and the three endpoints that returned 500 on every
call are fixed and regression-tested.

The gap is narrower than the first revision of this document suggested. The
frontend is not full of fake data — it is a set of working pages plus seven
honest empty states waiting on backends that were never built. What remains is:

1. **No deployment story at all** — the largest single gap.
2. **Seven pages with no backend domain**, which is a product-scope decision
   (build or remove) more than an engineering defect.
3. **Thin test coverage at the edges** — route level and frontend — which is how
   three fully broken endpoints coexisted with a green suite.

Phases 1 and 2 are roughly a week of focused work and would move this from
"impressive prototype" to "deployable system".
