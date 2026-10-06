"""CI infrastructure/authentication adapter; runs the existing pytest suite.

No test assertions, retrieval behavior, scores, or floors are changed. The
legacy Qdrant integration fixtures clear their key and make an anonymous
availability probe. Supply authentication only for the approved CI endpoint.
"""

from __future__ import annotations

import functools
import inspect
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
import sys
from urllib.parse import quote, urlsplit
from unittest.mock import patch
from uuid import uuid4


BACKEND = Path(__file__).resolve().parents[2] / "backend"
REQUIRED = (
    "QDRANT_URL", "QDRANT_API_KEY", "TRACE_TEST_QDRANT_URL",
    "NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE",
    "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_STORAGE_BUCKET",
    "GROQ_API_KEY", "DATABASE_URL", "DATABASE_URL_SYNC", "TRACE_CI_RUN_ID",
)
CI_COLLECTION = re.compile(r"^trace_ci_[a-z0-9_]+$")
RUN_ID = re.compile(r"^[0-9]+_[0-9]+$")


class ConfigurationError(RuntimeError):
    pass


@contextmanager
def neo4j_diagnostic(operation: str):
    """Expose the failing Aura operation without leaking configured credentials."""
    from neo4j.exceptions import ClientError

    try:
        yield
    except ClientError as exc:
        code = str(getattr(exc, "code", ""))
        if not re.fullmatch(r"Neo\.[A-Za-z0-9_.]+", code):
            code = "unavailable"
        message = str(getattr(exc, "message", "") or exc)
        sensitive = re.compile(r"PASSWORD|SECRET|TOKEN|KEY|URI|URL|CREDENTIAL", re.I)
        for name, value in sorted(os.environ.items(), key=lambda item: len(item[1]), reverse=True):
            if value and sensitive.search(name):
                message = message.replace(value, "[REDACTED]")
        message = re.sub(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s<>]+", "[REDACTED_URL]", message)
        message = re.sub(
            r"(?i)\b(?:password|api[-_ ]?key|token|secret|authorization)\s*[:=]\s*"
            r"(?:'[^']*'|\"[^\"]*\"|[^\s,;]+)",
            "[REDACTED_CREDENTIAL]", message,
        )
        message = re.sub(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/-]+",
                         "[REDACTED_AUTH]", message)
        message = re.sub(r"[\x00-\x1f\x7f]+", " ", message).strip()[:400]
        raise ConfigurationError(
            f"Neo4j {operation} failed (type={type(exc).__name__}, code={code}): {message}"
        ) from None


def neo4j_result(session, operation: str, query: str, *, consume: bool = False, **parameters):
    with neo4j_diagnostic(operation):
        result = session.run(query, **parameters)
        return result.consume() if consume else result.single()


def require_configuration() -> None:
    missing = [name for name in REQUIRED if not os.environ.get(name, "").strip()]
    if missing:
        raise ConfigurationError("Missing CI configuration: " + ", ".join(missing))
    if os.environ.get("GITHUB_ACTIONS") != "true" or not RUN_ID.fullmatch(os.environ["TRACE_CI_RUN_ID"]):
        raise ConfigurationError("TRACE_CI_RUN_ID must be a GitHub Actions run_id_run_attempt")
    for name, scheme, suffix in (
        ("QDRANT_URL", "https", ".qdrant.io"),
        ("NEO4J_URI", "neo4j+s", ".neo4j.io"),
        ("SUPABASE_URL", "https", ".supabase.co"),
    ):
        url = urlsplit(os.environ[name])
        allowed_paths = ("",) if name == "QDRANT_URL" else ("", "/")
        if (url.scheme != scheme or not (url.hostname or "").endswith(suffix)
                or url.username or url.password or url.query or url.fragment
                or url.path not in allowed_paths):
            raise ConfigurationError(f"{name} must use the expected cloud host and verified TLS")
    if os.environ["TRACE_TEST_QDRANT_URL"] != os.environ["QDRANT_URL"]:
        raise ConfigurationError("Both Qdrant URLs must identify the same CI cluster")
    if os.environ.get("QDRANT_COLLECTION_NAME") != base_collection():
        raise ConfigurationError("QDRANT_COLLECTION_NAME must name this run's CI collection")
    if os.environ.get("SUPABASE_STORAGE_BUCKET") != "trace":
        raise ConfigurationError("CI must use the existing private trace bucket")
    if os.environ.get("STORAGE_BACKEND") != "supabase":
        raise ConfigurationError("CI storage must use Supabase")
    for name, scheme in (("DATABASE_URL", "postgresql+asyncpg"),
                         ("DATABASE_URL_SYNC", "postgresql+psycopg2")):
        url = urlsplit(os.environ[name])
        if (url.scheme != scheme or url.hostname != "127.0.0.1"
                or url.port != 5432 or url.username != "trace_ci"
                or url.path != "/trace_ci" or url.query or url.fragment):
            raise ConfigurationError(f"{name} must target the ephemeral CI PostgreSQL service")


def base_collection() -> str:
    return f"trace_ci_{os.environ['TRACE_CI_RUN_ID']}_base"


def ci_collection(name: str) -> bool:
    return isinstance(name, str) and CI_COLLECTION.fullmatch(name) is not None


def current_run_collection(name: str) -> bool:
    return ci_collection(name) and name.startswith(f"trace_ci_{os.environ['TRACE_CI_RUN_ID']}_")


def storage_prefix() -> str:
    return f"ci/{os.environ['TRACE_CI_RUN_ID']}/"


def preflight() -> None:
    """Read-only namespace checks, then a run-owned Aura write probe."""
    import httpx
    from neo4j import GraphDatabase
    from qdrant_client import QdrantClient

    require_configuration()
    client = QdrantClient(url=os.environ["QDRANT_URL"],
                          api_key=os.environ["QDRANT_API_KEY"], timeout=30)
    try:
        for collection in client.get_collections().collections:
            if ci_collection(collection.name) and client.count(collection.name, exact=True).count:
                raise ConfigurationError("A CI-owned Qdrant collection contains data; refusing tests")
            if current_run_collection(collection.name):
                raise ConfigurationError("This CI run's Qdrant collection already exists; refusing tests")
    finally:
        client.close()
    with GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(
        os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]
    )) as driver:
        with neo4j_diagnostic("connectivity check"):
            driver.verify_connectivity()
        with driver.session(database=os.environ["NEO4J_DATABASE"]) as session:
            if neo4j_result(session, "CI node ownership check",
                "MATCH (n) WHERE n.trace_ci_run_id = $run_id RETURN count(n) AS count",
                run_id=os.environ["TRACE_CI_RUN_ID"],
            )["count"]:
                raise ConfigurationError("This CI run already owns graph nodes; refusing tests")
            if neo4j_result(session, "CI relationship ownership check",
                "MATCH ()-[r]->() WHERE r.trace_ci_run_id = $run_id RETURN count(r) AS count",
                run_id=os.environ["TRACE_CI_RUN_ID"],
            )["count"]:
                raise ConfigurationError("This CI run already owns graph relationships; refusing tests")
    headers = {"apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
               "Authorization": "Bearer " + os.environ["SUPABASE_SERVICE_ROLE_KEY"]}
    bucket = quote(os.environ["SUPABASE_STORAGE_BUCKET"], safe="")
    with httpx.Client(base_url=os.environ["SUPABASE_URL"].rstrip("/"),
                      headers=headers, timeout=30) as client:
        response = client.get(f"/storage/v1/bucket/{bucket}")
        response.raise_for_status()
        if response.json().get("public") is not False:
            raise ConfigurationError("Supabase CI bucket must be private")
        response = client.post(f"/storage/v1/object/list/{bucket}",
                               json={"prefix": storage_prefix(), "limit": 1})
        response.raise_for_status()
        if response.json():
            raise ConfigurationError("This CI run's Supabase prefix contains data; refusing tests")
    # Existing tests mock generation. Verify credentials without generating answers.
    response = httpx.get("https://api.groq.com/openai/v1/models", headers={
        "Authorization": "Bearer " + os.environ["GROQ_API_KEY"]
    }, timeout=30)
    response.raise_for_status()
    graph_probe()
    print("Shared-cloud namespace preflight and Aura probe passed.")


def graph_probe() -> None:
    """Exercise Aura writes with ownership on every node and relationship."""
    from neo4j import GraphDatabase

    run_id = os.environ["TRACE_CI_RUN_ID"]
    probe_id = uuid4().hex
    with GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(
        os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]
    )) as driver:
        with driver.session(database=os.environ["NEO4J_DATABASE"]) as session:
            try:
                record = neo4j_result(session, "probe creation",
                    "CREATE (a:TraceCI {trace_ci_run_id: $run_id, trace_ci_probe_id: $probe_id}) "
                    "CREATE (b:TraceCI {trace_ci_run_id: $run_id, trace_ci_probe_id: $probe_id}) "
                    "CREATE (a)-[r:TRACE_CI_LINK {trace_ci_run_id: $run_id, "
                    "trace_ci_probe_id: $probe_id}]->(b) "
                    "RETURN count(r) AS count",
                    run_id=run_id, probe_id=probe_id,
                )
                if record["count"] != 1:
                    raise ConfigurationError("Aura CI-owned graph probe failed")
            finally:
                neo4j_result(session, "probe relationship cleanup",
                    "MATCH (a:TraceCI)-[r:TRACE_CI_LINK]->(b:TraceCI) "
                    "WHERE a.trace_ci_run_id = $run_id AND b.trace_ci_run_id = $run_id "
                    "AND r.trace_ci_run_id = $run_id "
                    "AND a.trace_ci_probe_id = $probe_id AND b.trace_ci_probe_id = $probe_id "
                    "AND r.trace_ci_probe_id = $probe_id DELETE r",
                    run_id=run_id, probe_id=probe_id, consume=True,
                )
                neo4j_result(session, "probe node cleanup",
                    "MATCH (n:TraceCI {trace_ci_run_id: $run_id, trace_ci_probe_id: $probe_id}) "
                    "WHERE NOT (n)--() DELETE n",
                    run_id=run_id, probe_id=probe_id, consume=True,
                )
                remaining = neo4j_result(session, "probe cleanup verification",
                    "MATCH (n:TraceCI {trace_ci_run_id: $run_id, trace_ci_probe_id: $probe_id}) "
                    "RETURN count(n) AS count",
                    run_id=run_id, probe_id=probe_id,
                )["count"]
                if remaining:
                    raise ConfigurationError("Aura CI probe cleanup could not safely remove its nodes")


def cleanup() -> None:
    """Remove only resources created beneath this run's namespace."""
    sys.path.insert(0, str(BACKEND))
    from qdrant_client import QdrantClient
    from app.core.storage.supabase_storage import SupabaseStorageBackend

    require_configuration()
    client = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"], timeout=30)
    try:
        for collection in client.get_collections().collections:
            if current_run_collection(collection.name):
                client.delete_collection(collection_name=collection.name)
    finally:
        client.close()
    storage = SupabaseStorageBackend(
        url=os.environ["SUPABASE_URL"],
        service_role_key=os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        bucket=os.environ["SUPABASE_STORAGE_BUCKET"],
    )
    for path in _created_objects():
        if not path.startswith(storage_prefix()):
            raise ConfigurationError("Supabase cleanup manifest contains an unowned path")
        storage.delete(path)


class RequiredTests:
    """Existing infrastructure-dependent skips must never turn CI green."""

    def pytest_sessionfinish(self, session, exitstatus):
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        skipped = reporter.stats.get("skipped", []) if reporter else []
        deselected = reporter.stats.get("deselected", []) if reporter else []
        if skipped or deselected:
            if reporter:
                reporter.write_sep("=", "CI requires the complete suite: skips/deselections fail")
            if exitstatus == 0:
                session.exitstatus = 1


def run_tests(args: list[str]) -> int:
    import pytest

    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise ConfigurationError("Cloud test adapter may run only inside GitHub Actions")
    preflight()
    # The suite mocks generation and the health fixture supplies its LLM flag.
    # Avoid a real Groq models.list() request at every TestClient startup.
    os.environ.pop("GROQ_API_KEY", None)
    endpoint = os.environ["QDRANT_URL"].rstrip("/")
    key = os.environ["QDRANT_API_KEY"]
    sys.path.insert(0, str(BACKEND))
    with authenticated_qdrant(endpoint, key), guarded_cloud_writes():
        return int(pytest.main(args, plugins=[RequiredTests()]))


@contextmanager
def guarded_cloud_writes():
    """Fail closed if the suite attempts a write outside this CI run."""
    from contextlib import ExitStack
    from qdrant_client import QdrantClient
    from app.core.storage.supabase_storage import SupabaseStorageBackend, _SupabaseRestProvider
    from app.graph.neo4j_graph_store import Neo4jGraphStore

    mutations = (
        "create_collection", "recreate_collection", "delete_collection",
        "update_collection", "create_payload_index", "delete_payload_index",
        "upsert", "delete", "set_payload", "overwrite_payload",
        "delete_payload", "clear_payload", "upload_points", "upload_records",
        "batch_update_points", "update_vectors", "delete_vectors",
    )
    original_path = SupabaseStorageBackend.build_document_path
    original_save = SupabaseStorageBackend.save
    original_delete = SupabaseStorageBackend.delete
    original_read = SupabaseStorageBackend.read
    original_exists = SupabaseStorageBackend.exists
    original_graph_write = Neo4jGraphStore.execute_write
    original_graph_transaction = Neo4jGraphStore.begin_transaction
    original_indexes = Neo4jGraphStore._ensure_indexes

    def scoped_path(self, *args, **kwargs):
        path = original_path(self, *args, **kwargs)
        return storage_prefix() + path if isinstance(self._provider, _SupabaseRestProvider) else path

    def check_storage(self, path):
        if isinstance(self._provider, _SupabaseRestProvider) and not (
            isinstance(path, str) and path.startswith(storage_prefix())
        ):
            raise ConfigurationError("Supabase access outside this CI run is forbidden")

    def scoped_save(self, path, content):
        check_storage(self, path)
        if isinstance(self._provider, _SupabaseRestProvider):
            # The provider upserts. Refuse a path not first created by this run.
            if path not in _created_objects() and original_exists(self, path):
                raise ConfigurationError("Refusing to overwrite an existing Supabase object")
            _record_object(path)
        return original_save(self, path, content)

    def scoped_delete(self, path):
        check_storage(self, path)
        if isinstance(self._provider, _SupabaseRestProvider) and path not in _created_objects():
            raise ConfigurationError("Refusing to delete a Supabase object not created by this run")
        return original_delete(self, path)

    def scoped_read(self, path):
        check_storage(self, path)
        return original_read(self, path)

    def scoped_exists(self, path):
        check_storage(self, path)
        return original_exists(self, path)

    async def deny_graph_write(self, *args, **kwargs):
        if self._uri == os.environ["NEO4J_URI"]:
            raise ConfigurationError("Application graph writes are disabled on shared Aura in CI")
        return await original_graph_write(self, *args, **kwargs)

    async def deny_graph_transaction(self, *args, **kwargs):
        if self._uri == os.environ["NEO4J_URI"]:
            raise ConfigurationError("Application graph transactions are disabled on shared Aura in CI")
        return await original_graph_transaction(self, *args, **kwargs)

    async def no_shared_indexes(self):
        if self._uri == os.environ["NEO4J_URI"]:
            return None
        return await original_indexes(self)

    with ExitStack() as stack:
        for method in mutations:
            original = getattr(QdrantClient, method, None)
            if original is None:
                continue
            def guard(self, *args, _original=original, **kwargs):
                collection = kwargs.get("collection_name", args[0] if args else None)
                if not current_run_collection(collection):
                    raise ConfigurationError("Qdrant write outside this CI run is forbidden")
                return _original(self, *args, **kwargs)
            stack.enter_context(patch.object(QdrantClient, method, guard))
        for name, method in (
            ("build_document_path", scoped_path), ("save", scoped_save),
            ("delete", scoped_delete), ("read", scoped_read), ("exists", scoped_exists),
        ):
            stack.enter_context(patch.object(SupabaseStorageBackend, name, method))
        stack.enter_context(patch.object(Neo4jGraphStore, "execute_write", deny_graph_write))
        stack.enter_context(patch.object(Neo4jGraphStore, "begin_transaction", deny_graph_transaction))
        stack.enter_context(patch.object(Neo4jGraphStore, "_ensure_indexes", no_shared_indexes))
        yield


def _object_manifest() -> Path:
    return Path(os.environ["RUNNER_TEMP"]) / f"trace-ci-{os.environ['TRACE_CI_RUN_ID']}-objects.json"


def _created_objects() -> set[str]:
    path = _object_manifest()
    return set(json.loads(path.read_text())) if path.exists() else set()


def _record_object(path: str) -> None:
    objects = _created_objects()
    objects.add(path)
    _object_manifest().write_text(json.dumps(sorted(objects)))


@contextmanager
def authenticated_qdrant(endpoint: str, key: str):
    """Add auth only to the legacy probe and clients for the validated URL."""
    import httpx
    from qdrant_client import QdrantClient

    original_get = httpx.get
    original_init = QdrantClient.__init__
    signature = inspect.signature(original_init)

    @functools.wraps(original_get)
    def authenticated_probe(url, *positional, **kwargs):
        # The existing collection-time availability check uses this exact URL.
        # Never send the key to unrelated test URLs or follow redirects.
        if str(url) == endpoint + "/collections":
            kwargs["headers"] = {**(kwargs.get("headers") or {}), "api-key": key}
            kwargs["follow_redirects"] = False
        return original_get(url, *positional, **kwargs)

    @functools.wraps(original_init)
    def authenticated_client(self, *positional, **kwargs):
        bound = signature.bind(self, *positional, **kwargs)
        if str(bound.arguments.get("url", "")).rstrip("/") == endpoint:
            if not bound.arguments.get("api_key"):
                bound.arguments["api_key"] = key
        return original_init(*bound.args, **bound.kwargs)

    with patch.object(httpx, "get", authenticated_probe), \
            patch.object(QdrantClient, "__init__", authenticated_client):
        yield


def main() -> int:
    try:
        if len(sys.argv) < 2 or sys.argv[1] not in ("configuration", "tests", "cleanup"):
            raise ConfigurationError("Usage: backend_ci.py configuration | tests | cleanup")
        require_configuration()
        if sys.argv[1] == "configuration":
            print("Required shared-cloud CI configuration is present.")
            return 0
        if sys.argv[1] == "cleanup":
            cleanup()
            return 0
        args = sys.argv[2:]
        if args[:1] == ["--"]:
            args = args[1:]
        return run_tests(args)
    except ConfigurationError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # Cloud client exception text can contain URLs/auth details. Do not echo it.
        print(f"::error::CI cloud preflight/runner failed ({type(exc).__name__}); "
              "check shared resource credentials and availability.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
