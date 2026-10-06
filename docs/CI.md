# TRACE CI

`.github/workflows/ci.yml` runs on every pull request, push to `main`, and manual
dispatch. It calls the existing `eval.yml` as a reusable workflow; that workflow
also retains its nightly/manual evaluation checks. There is no deployment or
image publishing. Configure branch protection to require **CI quality gate**.
It fails for failed, skipped, or cancelled dependency jobs.

## Configure the `ci` GitHub environment

Create the environment and configure required reviewers before adding secrets.
CI uses the existing Qdrant Cloud cluster, Neo4j Aura database, and private
Supabase `trace` bucket. These cloud resources are shared with TRACE production
and demo data; CI is strictly scoped to its own run namespace. PostgreSQL
remains the workflow's disposable PostgreSQL 16 service.

Environment secrets:

- `CI_QDRANT_URL`, `CI_QDRANT_API_KEY`
- `CI_NEO4J_URI`, `CI_NEO4J_USERNAME`, `CI_NEO4J_PASSWORD`
- `CI_SUPABASE_URL`, `CI_SUPABASE_SERVICE_ROLE_KEY`
- `CI_GROQ_API_KEY`

Environment variables:

- `CI_NEO4J_DATABASE`: Aura database name, default `neo4j`.

Use HTTPS Qdrant Cloud (`*.qdrant.io`), verified Aura TLS (`neo4j+s://*.neo4j.io`),
and HTTPS Supabase (`*.supabase.co`) URLs. The namespace preflight ignores
production data. It fails if any `trace_ci_*` Qdrant collection contains points,
if this run's Qdrant collection already exists, if this run's Aura marker exists,
or if `ci/<run-id>/` in the private `trace` bucket contains objects. The preflight
also creates and deletes a small run-marked Aura graph probe. PostgreSQL URLs
must identify the workflow's disposable service.

The backend suite creates/deletes only `trace_ci_<run-id>_*` collections;
`document_chunks` is never mutated. Application graph writes and schema changes
are blocked in CI; the Aura probe uses `TraceCI` nodes and a `TRACE_CI_LINK`
relationship, each carrying `trace_ci_run_id` and `trace_ci_probe_id`. Its cleanup
matches those exact markers and refuses to detach unrelated relationships.
Real Supabase writes use only `ci/<run-id>/`; cleanup reads a manifest of keys
created by this run and deletes only those keys. The final cleanup removes this
run's Qdrant collections after the integrity audit. Other runs' and production
namespaces are never cleaned by CI. A previous run's populated CI collection
requires manual inspection before retrying. GitHub environment approvals must
be granted only after reviewing the code that will receive secrets.

Missing secrets or inaccessible cloud services fail the backend job and the
quality gate. Fork PRs and Dependabot PRs without secrets cannot receive a green
required backend gate. Do not use `pull_request_target` to run untrusted code
with credentials. Review and run approved changes on a trusted branch with the
isolated environment instead.

## Required checks

- Backend installs `requirements.lock.txt` with CPU-only torch, then installs
  existing direct/test dependencies constrained by that lock. The lock omits
  pytest-timeout/pytest-cov; their pins remain sourced from `requirements.txt`.
  Pip consistency checks also fail the job on incompatible requirements.
- Fresh PostgreSQL: `alembic upgrade head`, `alembic current --check-heads`, and
  a second upgrade to verify repeatability. No existing database is migrated.
- Models: existing `scripts/bake_models.py`, followed by offline verification.
- Entire backend suite with existing coverage/timeout tooling. The CI-only
  adapter supplies authentication to the legacy anonymous Qdrant probe and
  fixtures for the validated Cloud URL only. It changes no assertions or
  retrieval logic. The adapter's credential scope and skip policy have their
  own small safety tests. Any skipped/deselected test fails CI.
- Existing read-only `scripts/audit_rag_integrity.py --fail-on-issues` runs
  against CI's disposable PostgreSQL, run collection, run-marked Aura graph,
  and referenced Supabase objects after tests. Its checks and failure policy
  are unchanged; outside CI it still audits the full graph.
- Existing `eval.validate --offline` checks golden-set schema, review state,
  source files and hashes. `eval.gate` checks committed retrieval results and
  production configuration drift with unchanged floors. The frozen baseline
  must still breach those floors; missing/broken result files are failures.
- Frontend: `npm ci`, `npm test`, `tsc --noEmit`, `npm run build`.
- Docker: full existing `backend/Dockerfile` runtime image, then imports,
  embedding/reranker inference and tokenizer checks with `--network none`.
  Build-time downloads require public PyPI, PyTorch, Debian and Hugging Face
  endpoints. Build failures are blocking; no cloud credentials are build inputs.

Pip/npm, model and Docker layer caches accelerate repeat runs. Only the backend
JUnit report is uploaded, with seven-day retention; environments and cloud
audit output are not uploaded as artifacts. The previous advisory ESLint step
is outside the requested required checks; no application lint rules are changed.

## Evaluation limits

The stored-results gate is not a fresh retrieval evaluation. The full frozen
indexed corpus is not provisioned in CI. The namespace-scoped cross-store audit checks
test-store consistency and is not an audit of production data. A fresh
`eval.validate` (without `--offline`), `eval.run retrieval`, and live-data integrity
audit require access to the matching frozen PostgreSQL corpus and its Qdrant
Cloud/Aura/Supabase resources. Run those existing read-only checks separately in an approved
environment with matching corpus access before approving retrieval changes.
Answer evaluations require Groq and remain reported, not gated, as prescribed
by the existing evaluation harness. No scoring or thresholds are changed.

## Local validation

Frontend checks can be run from `frontend` with the commands above. From
`backend`, run `python -m eval.validate --offline`, `python -m eval.gate`, and
the existing evaluation tests. Full integration tests and online migration
validation require a disposable PostgreSQL database and CI run namespaces on
the shared cloud resources. The CI adapter refuses local cloud test execution. Never validate
migrations or cloud integration tests against existing user/production data.
