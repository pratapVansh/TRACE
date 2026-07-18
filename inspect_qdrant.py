#!/usr/bin/env python3
import os, sys, json, random, math
from qdrant_client import QdrantClient
from qdrant_client.http.models import ScoredPoint, VectorParams

CLIENT = QdrantClient(
    url="https://c74086da-a2cd-48c7-b946-678c22507447.eu-central-1-0.aws.cloud.qdrant.io",
    api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6N2ZkYzQ1OTUtNTQwYS00M2JmLWI4ZmQtMzYxMGY1MzNiODMxIn0.mV0Jrsh9KPQvEvGYtB_ErgF2VP82Fmb7cDuH_mNQu4U",
    prefer_grpc=False,
)

COLLECTION = "document_chunks"
print("=" * 70)
print("QDRANT INSPECTION REPORT")
print("=" * 70)

# ---------------------------------------------------------------------------
# 1) List all collections
# ---------------------------------------------------------------------------
print("\n[1] Collections:")
colls = CLIENT.get_collections().collections
for c in colls:
    print(f"    - {c.name}")
print()

# ---------------------------------------------------------------------------
# 2) Collection info
# ---------------------------------------------------------------------------
print("[2] Collection info: document_chunks")
try:
    info = CLIENT.get_collection(COLLECTION)
    print(f"    Status:              {info.status}")
    print(f"    Vector dimension:    {info.config.params.vectors.size}")
    print(f"    Distance metric:     {info.config.params.vectors.distance}")
    print(f"    Points count:        {info.points_count}")
    print(f"    Segments count:      {info.segments_count}")
    cfg = info.config
    if cfg.hnsw_config:
        h = cfg.hnsw_config
        print(f"    HNSW config:")
        print(f"      m:                {h.m}")
        print(f"      ef_construct:     {h.ef_construct}")
        print(f"      full_scan_threshold: {h.full_scan_threshold}")
    if hasattr(cfg, 'optimizer_config') and cfg.optimizer_config:
        o = cfg.optimizer_config
        print(f"    Optimizer config:")
        print(f"      deleted_threshold: {o.deleted_threshold}")
        print(f"      vacuum_min_vector_number: {o.vacuum_min_vector_number}")
        print(f"      default_segment_number: {o.default_segment_number}")
    if hasattr(cfg, 'quantization_config') and cfg.quantization_config:
        print(f"    Quantization config: {cfg.quantization_config}")
    if hasattr(cfg, 'wal_config') and cfg.wal_config:
        w = cfg.wal_config
        print(f"    WAL config:")
        print(f"      wal_capacity_mb:   {w.wal_capacity_mb}")
        print(f"      wal_segments_ahead: {w.wal_segments_ahead}")
    print()
except Exception as e:
    print(f"    ERROR: {e}\n")

# ---------------------------------------------------------------------------
# 3) Scroll through all points
# ---------------------------------------------------------------------------
print("[3] All points (scroll):")
all_points = []
offset = None
limit = 100
page = 0
total_scrolled = 0

while True:
    batch, offset = CLIENT.scroll(
        collection_name=COLLECTION,
        limit=limit,
        offset=offset,
        with_payload=True,
        with_vectors=False,
    )
    if not batch:
        break
    all_points.extend(batch)
    for pt in batch:
        total_scrolled += 1
        pid = pt.id
        pl = pt.payload or {}
        doc_id = pl.get("document_id", "N/A")
        fname = pl.get("filename", "N/A")
        chunk_idx = pl.get("chunk_index", "N/A")
        content = pl.get("content", "")
        content_preview = (content[:120] + "...") if len(content) > 120 else content
        print(f"  Point id={pid}")
        print(f"    document_id={doc_id}  filename={fname}  chunk_index={chunk_idx}")
        print(f"    content={content_preview}")
    print(f"  --- page {page} ({len(batch)} points) ---")
    page += 1
    if offset is None:
        break

print(f"\n  Total points scrolled: {total_scrolled}")

# ---------------------------------------------------------------------------
# 4) Summary statistics
# ---------------------------------------------------------------------------
print("\n[4] Summary:")
print(f"  Total vectors (collection info): {info.points_count}")
print(f"  Total vectors scrolled:          {total_scrolled}")

doc_ids = set()
filenames = set()
null_field_counts = {}
all_payload_keys = set()

for pt in all_points:
    pl = pt.payload or {}
    did = pl.get("document_id")
    if did is not None:
        doc_ids.add(did)
    else:
        null_field_counts["document_id"] = null_field_counts.get("document_id", 0) + 1
    fn = pl.get("filename")
    if fn is not None:
        filenames.add(fn)
    else:
        null_field_counts["filename"] = null_field_counts.get("filename", 0) + 1
    co = pl.get("content")
    if co is None:
        null_field_counts["content"] = null_field_counts.get("content", 0) + 1
    for k in pl:
        all_payload_keys.add(k)
        if pl[k] is None:
            null_field_counts[k] = null_field_counts.get(k, 0) + 1

print(f"  Unique document_ids:   {len(doc_ids)}")
print(f"  Unique filenames:      {len(filenames)}")
print(f"  Filenames list:        {sorted(filenames)}")
print(f"  All payload keys:      {sorted(all_payload_keys)}")
if null_field_counts:
    print(f"  Missing/null field counts: {null_field_counts}")
else:
    print(f"  Missing/null fields:   None")

# ---------------------------------------------------------------------------
# 5) Test search with random 384-dim query vector
# ---------------------------------------------------------------------------
dim = info.config.params.vectors.size
print(f"\n[5] Test search (random {dim}-dim vector):")
query_vec = [random.uniform(-1, 1) for _ in range(dim)]

# New qdrant-client uses query_points instead of search
search_result = CLIENT.query_points(
    collection_name=COLLECTION,
    query=query_vec,
    limit=10,
    with_payload=True,
)

results = search_result.points
print(f"  Results count: {len(results)}")
if results:
    print(f"  Scores:        {[round(r.score, 4) for r in results]}")
    for r in results:
        pl = r.payload or {}
        print(f"    score={r.score:.4f}  doc_id={pl.get('document_id','?')}  "
              f"filename={pl.get('filename','?')}  chunk={pl.get('chunk_index','?')}")
else:
    print("  (no results — collection may be empty)")

print("\nDone.")
