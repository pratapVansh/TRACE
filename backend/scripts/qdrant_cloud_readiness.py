"""Read-only readiness check for TRACE's parked Qdrant Cloud target.

This command never creates, updates, or deletes collections, indexes, points,
or metadata. Run it from ``backend`` with the root ``.env`` configured::

    python scripts/qdrant_cloud_readiness.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
EXPECTED_DIMENSION = 384
EXPECTED_DISTANCE = Distance.COSINE
REQUIRED_PAYLOAD_INDEXES = {
    "content": "text",
    "document_id": "keyword",
    "document_type": "keyword",
    "filename": "keyword",
    "uploaded_by": "keyword",
    "metadata.language": "keyword",
    "upload_date": "float",
}
REQUIRED_METADATA = {
    "trace_embedding_model": "all-MiniLM-L6-v2",
    "trace_vector_dimension": EXPECTED_DIMENSION,
    "trace_embedding_metadata_schema": 1,
}


def _schema_name(value: object) -> str:
    data_type = getattr(value, "data_type", value)
    raw = getattr(data_type, "value", data_type)
    return str(raw).lower()


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    from app.core.config import settings

    url = settings.qdrant_cloud_url.strip()
    api_key = settings.qdrant_cloud_api_key.strip()
    collection = settings.qdrant_collection_name
    if not url or not api_key:
        print("ready=false")
        print("error=QDRANT_CLOUD_URL and QDRANT_CLOUD_API_KEY are required")
        return 2

    client = QdrantClient(
        url=url,
        api_key=api_key,
        timeout=settings.qdrant_timeout_seconds,
        prefer_grpc=False,
    )
    collections = {item.name for item in client.get_collections().collections}
    print("connected=true")
    print(f"collection={collection}")
    if collection not in collections:
        print("collection_exists=false")
        print("ready_for_vector_migration=false")
        print("ready_for_application_switch=false")
        return 1

    info = client.get_collection(collection)
    vectors = info.config.params.vectors
    dimension = getattr(vectors, "size", None)
    distance = getattr(vectors, "distance", None)
    payload_schema = {
        key: _schema_name(value) for key, value in info.payload_schema.items()
    }
    metadata = dict(info.config.metadata or {})
    schema_ok = (
        dimension == EXPECTED_DIMENSION
        and distance == EXPECTED_DISTANCE
        and all(payload_schema.get(key) == value for key, value in REQUIRED_PAYLOAD_INDEXES.items())
    )
    metadata_ok = all(metadata.get(key) == value for key, value in REQUIRED_METADATA.items())

    print("collection_exists=true")
    print(f"status={getattr(info.status, 'value', info.status)}")
    print(f"points_count={info.points_count}")
    print(f"dimension={dimension}")
    print(f"distance={getattr(distance, 'value', distance)}")
    print(
        "required_payload_indexes="
        + ",".join(f"{key}:{payload_schema.get(key, 'missing')}" for key in REQUIRED_PAYLOAD_INDEXES)
    )
    print(f"embedding_metadata_compatible={str(metadata_ok).lower()}")
    print(f"ready_for_vector_migration={str(schema_ok).lower()}")
    print(f"ready_for_application_switch={str(schema_ok and metadata_ok).lower()}")
    return 0 if schema_ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("ready=false")
        print(f"error={type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc
