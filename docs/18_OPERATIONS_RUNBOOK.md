# TRACE Operations Runbook

This runbook covers the current Docker Compose deployment: PostgreSQL, Qdrant,
Neo4j, the backend upload volume, migrations, bootstrap, and embedding-index
compatibility. Commands run from the repository root and use both Compose files.

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.local.yml ps
curl http://localhost:8000/api/health
```

Do not use `docker compose down -v` on an installation whose data must survive.
The `-v` option deletes the named data volumes.

## Backup scope

A recoverable TRACE backup is one set containing all four stores from the same
maintenance window:

1. PostgreSQL (`postgres_data`) — users, documents, chunks, jobs, conversations,
   memories, and audit records.
2. Backend storage (`backend_storage`) — uploaded source files.
3. Qdrant (`qdrant_data`) — chunk vectors plus embedding compatibility metadata.
4. Neo4j (`neo4j_data`) — extracted entities and relationships.

Record the application image/version, `EMBEDDING_MODEL_NAME`,
`EMBEDDING_VECTOR_DIMENSION`, and Qdrant collection name beside every backup.
Never put `.env`, API keys, JWT secrets, or database passwords in the archive.

## Create a backup

Create a dated directory outside the repository first. Quiesce uploads and chat
traffic for a consistent multi-store snapshot; the simplest maintenance-window
procedure is to stop only the backend while leaving databases running:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml stop backend
docker compose -f docker-compose.yml -f docker-compose.local.yml exec -T postgres \
  pg_dump -U trace -d trace --clean --if-exists --no-owner --no-privileges \
  > trace-backup/postgres.sql
```

Create a Qdrant collection snapshot and copy the named snapshot returned by the
API from the container:

```bash
curl -X POST http://localhost:6333/collections/document_chunks/snapshots
docker compose -f docker-compose.yml -f docker-compose.local.yml cp \
  qdrant:/qdrant/storage/collections/document_chunks/snapshots/SNAPSHOT_NAME \
  trace-backup/qdrant.snapshot
```

Pause the Neo4j database, dump it, restart it, and copy the dump out:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml exec -T neo4j \
  cypher-shell -u neo4j -p tracedevpassword "STOP DATABASE neo4j WAIT"
docker compose -f docker-compose.yml -f docker-compose.local.yml exec -T neo4j \
  neo4j-admin database dump neo4j --to-path=/data/backups --overwrite-destination=true
docker compose -f docker-compose.yml -f docker-compose.local.yml exec -T neo4j \
  cypher-shell -u neo4j -p tracedevpassword "START DATABASE neo4j WAIT"
docker compose -f docker-compose.yml -f docker-compose.local.yml cp \
  neo4j:/data/backups/neo4j.dump trace-backup/neo4j.dump
```

Archive uploaded files from the named volume without exposing the backend:

```bash
docker run --rm -v trace_backend_storage:/source:ro -v ./trace-backup:/backup \
  alpine tar -C /source -czf /backup/backend-storage.tar.gz .
```

Restart the API and verify health:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml start backend
curl http://localhost:8000/api/health
```

Volume names differ when Compose uses a non-default project name. Confirm them
with `docker volume ls` before any backup or restore command.

## Restore drill

Restore into a new, isolated Compose project first. Never test a restore over
the only production copy.

1. Start clean database containers, but keep the backend stopped.
2. Restore `postgres.sql` with `psql -v ON_ERROR_STOP=1`.
3. Extract `backend-storage.tar.gz` into the new backend storage volume.
4. Upload the Qdrant snapshot through
   `PUT /collections/document_chunks/snapshots/upload?priority=snapshot`.
5. Stop the Neo4j database, copy `neo4j.dump` to `/data/backups`, run
   `neo4j-admin database load neo4j --from-path=/data/backups --overwrite-destination=true`,
   then start the database.
6. Run `alembic upgrade head`, then start bootstrap and backend through Compose.
7. Run the checks below.

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml exec -T backend \
  python scripts/manage_vector_index.py status
python backend/scripts/verify_stage4_e2e.py \
  --file backend/tests/fixtures/e2e/stage4_verification.txt --cleanup
```

Run the E2E command from the project root in the activated backend environment.
It reads the bootstrap credentials from the root `.env`; those credentials are
deliberately supplied to the one-shot bootstrap service, not the long-running
backend container.

The drill is successful only when health, login, upload and processing, search,
graph retrieval, Copilot citations, and audit-log reads all pass. Retain
one previous known-good backup until the restored system passes.

## Embedding model changes and reindexing

Startup compares native Qdrant collection metadata with
`EMBEDDING_MODEL_NAME` and `EMBEDDING_VECTOR_DIMENSION`. A missing or mismatched
marker disables vector retrieval with a clear startup error rather than serving
results from incompatible vector spaces.

For a legacy collection known to have been generated by the configured model,
adopt it without changing vectors:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml exec -T backend \
  python scripts/manage_vector_index.py stamp-existing \
  --confirm-model all-MiniLM-L6-v2
```

For an intentional model or dimension change, update both settings, take a
backup, stop the backend worker, and run the guarded rebuild. This deletes the
Qdrant collection and regenerates stored chunk embeddings; it does not change
chunking or source documents.

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml run --rm backend \
  python scripts/manage_vector_index.py reindex \
  --confirm-collection document_chunks
```

Do not reindex merely because metadata is absent. Use `status` first and the
non-destructive stamp path only when the existing model and physical dimension
are independently known.
