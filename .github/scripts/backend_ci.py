"""CI infrastructure/authentication adapter; runs the existing pytest suite.

No test assertions, retrieval behavior, scores, or floors are changed. The
legacy Qdrant integration fixtures clear their key and make an anonymous
availability probe. Supply authentication only for the approved CI endpoint.
"""

from __future__ import annotations

import functools
import inspect
import os
from contextlib import contextmanager
from pathlib import Path
import sys
from urllib.parse import quote, urlsplit
from unittest.mock import patch


BACKEND = Path(__file__).resolve().parents[2] / "backend"
REQUIRED = (
    "QDRANT_URL", "QDRANT_API_KEY", "TRACE_TEST_QDRANT_URL",
    "NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE",
    "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_STORAGE_BUCKET",
    "GROQ_API_KEY", "DATABASE_URL", "DATABASE_URL_SYNC",
)


class ConfigurationError(RuntimeError):
    pass


def require_configuration() -> None:
    missing = [name for name in REQUIRED if not os.environ.get(name, "").strip()]
    if missing:
        raise ConfigurationError("Missing CI configuration: " + ", ".join(missing))
    if os.environ.get("CI_CLOUD_RESOURCES_ISOLATED") != "true":
        raise ConfigurationError("CI_CLOUD_RESOURCES_ISOLATED must attest dedicated CI resources")
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
    if os.environ.get("QDRANT_COLLECTION_NAME") != "trace_ci_base":
        raise ConfigurationError("QDRANT_COLLECTION_NAME must be trace_ci_base")
    if os.environ.get("STORAGE_BACKEND") != "supabase":
        raise ConfigurationError("CI storage must use Supabase")
    for name, scheme in (("DATABASE_URL", "postgresql+asyncpg"),
                         ("DATABASE_URL_SYNC", "postgresql+psycopg2")):
        url = urlsplit(os.environ[name])
        if (url.scheme != scheme or url.hostname != "127.0.0.1"
                or url.port != 5432 or url.username != "trace_ci"
                or url.path != "/trace_ci" or url.query or url.fragment):
            raise ConfigurationError(f"{name} must target the ephemeral CI PostgreSQL service")


def preflight() -> None:
    """Read-only checks; refuse populated cloud stores before test startup."""
    import httpx
    from neo4j import GraphDatabase
    from qdrant_client import QdrantClient

    require_configuration()
    client = QdrantClient(url=os.environ["QDRANT_URL"],
                          api_key=os.environ["QDRANT_API_KEY"], timeout=30)
    try:
        for collection in client.get_collections().collections:
            if client.count(collection.name, exact=True).count:
                raise ConfigurationError("Qdrant CI cluster contains data; refusing tests")
    finally:
        client.close()
    with GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(
        os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]
    )) as driver:
        driver.verify_connectivity()
        with driver.session(database=os.environ["NEO4J_DATABASE"]) as session:
            if session.run("MATCH (n) RETURN count(n) AS count").single()["count"]:
                raise ConfigurationError("Aura CI database contains data; refusing tests")
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
                               json={"prefix": "", "limit": 1})
        response.raise_for_status()
        if response.json():
            raise ConfigurationError("Supabase CI bucket contains data; refusing tests")
    # Existing tests mock generation. Verify credentials without generating answers.
    response = httpx.get("https://api.groq.com/openai/v1/models", headers={
        "Authorization": "Bearer " + os.environ["GROQ_API_KEY"]
    }, timeout=30)
    response.raise_for_status()
    print("Isolated cloud preflight passed (read-only).")


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
    with authenticated_qdrant(endpoint, key):
        return int(pytest.main(args, plugins=[RequiredTests()]))


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
        if len(sys.argv) < 2 or sys.argv[1] not in ("configuration", "tests"):
            raise ConfigurationError("Usage: backend_ci.py configuration | tests -- [pytest arguments]")
        require_configuration()
        if sys.argv[1] == "configuration":
            print("Required isolated CI configuration is present.")
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
              "check isolated resource credentials and availability.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
