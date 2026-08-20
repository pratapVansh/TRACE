import functools
import ssl
import threading
import time
from typing import Any

import certifi

from neo4j import (
    AsyncDriver,
    AsyncGraphDatabase,
    basic_auth,
)
from neo4j.exceptions import (
    ServiceUnavailable,
    SessionError,
    TransactionError,
)

from app.graph.base import (
    GraphStore,
    GraphStoreConnectionError,
    GraphStoreConfigurationError,
    GraphStoreOperationError,
)
from app.core.config import settings
from app.core.logging import logger

_VALID_URI_PREFIXES = ("bolt://", "bolt+s://", "bolt+ssc://", "neo4j://", "neo4j+s://", "neo4j+ssc://")

# Schemes that ask for a verified TLS connection. The driver builds its own
# SSL context for these, which trusts only the OS certificate store.
_VERIFIED_TLS_SCHEMES = {"neo4j+s://": "neo4j://", "bolt+s://": "bolt://"}


@functools.lru_cache(maxsize=1)
def _verified_ssl_context() -> ssl.SSLContext:
    """An SSL context trusting the OS store *and* the certifi bundle.

    Neo4j Aura serves a chain rooted at "SSL.com Root Certification Authority
    RSA" and includes that root in the chain it sends. OpenSSL rejects such a
    chain as "self-signed certificate in certificate chain" unless the root is
    in its trust store, and the Windows store does not carry it by default
    (Windows installs roots on demand through CryptoAPI, which OpenSSL never
    calls). The result is that ``neo4j+s://`` fails on a stock Windows Python
    while the identical URL works from curl.

    Loading both sources is a superset of the driver's own context, so a
    private CA that only lives in the OS store keeps working.
    """
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context

_INDEX_QUERIES = [
    "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.name)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.document_id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Compressor) ON (n.name)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Failure) ON (n.name)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Cause) ON (n.name)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Operator) ON (n.name)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.user_id)",
]


class ManagedTransaction:
    """Wraps a Neo4j AsyncTransaction and its session, ensuring the session
    is closed when the transaction finishes (commit or rollback).

    Supports async context manager protocol (``async with``).
    """

    def __init__(self, session: Any, transaction: Any) -> None:
        self._session = session
        self._transaction = transaction

    async def commit(self) -> None:
        try:
            await self._transaction.commit()
            from app.core.cache import cache_manager
            await cache_manager.delete_pattern("neo4j_read:*")
        finally:
            await self._close_session()

    async def rollback(self) -> None:
        try:
            await self._transaction.rollback()
        finally:
            await self._close_session()

    @property
    def closed(self) -> bool:
        return self._transaction.closed

    def __getattr__(self, name: str) -> Any:
        return getattr(self._transaction, name)

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()

    async def _close_session(self) -> None:
        try:
            await self._session.close()
        except Exception:
            logger.exception("Error closing Neo4j session after transaction")


class Neo4jGraphStore(GraphStore):
    """Graph store backed by Neo4j."""

    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._uri = (uri or settings.neo4j_uri).strip()
        self._username = (username or settings.neo4j_username).strip()
        self._password = (password or settings.neo4j_password).strip()
        self._driver: AsyncDriver | None = None
        self._connected = False
        import asyncio
        self._lock = asyncio.Lock()
        self._db_name: str | None = settings.neo4j_database or None

        errors: list[str] = []

        if not self._uri:
            errors.append(
                "NEO4J_URI is not set. Provide a uri or set the environment variable."
            )
        elif not self._is_valid_uri(self._uri):
            errors.append(
                f"NEO4J_URI has an invalid scheme: {self._uri!r}. "
                f"Expected one of: {', '.join(_VALID_URI_PREFIXES)}."
            )

        if not self._username:
            errors.append(
                "NEO4J_USERNAME is not set. Provide a username or set the environment variable."
            )

        if not self._password:
            errors.append(
                "NEO4J_PASSWORD is not set. Provide a password or set the environment variable."
            )

        if errors:
            msg = "; ".join(errors)
            logger.error("Neo4j configuration error(s): %s", msg)
            raise GraphStoreConfigurationError(msg)

        logger.info(
            "Neo4jGraphStore configured — uri=%s username=%s database=%s "
            "connection_timeout=%ds max_connection_lifetime=%ds",
            self._uri,
            self._username,
            self._db_name,
            settings.neo4j_connection_timeout_seconds,
            settings.neo4j_max_connection_lifetime_seconds,
        )

    @staticmethod
    def _is_valid_uri(uri: str) -> bool:
        return any(uri.lower().startswith(prefix) for prefix in _VALID_URI_PREFIXES)

    async def _ensure_indexes(self) -> None:
        try:
            driver = await self._get_driver()
            async with driver.session(database=self._db_name) as session:
                for query in _INDEX_QUERIES:
                    await session.run(query)
            logger.info("Neo4j indexes created or confirmed")
        except Exception as exc:
            logger.warning("Failed to create Neo4j indexes — continuing: %s", exc)

    @property
    def provider_name(self) -> str:
        return "neo4j"

    async def _get_driver(self) -> AsyncDriver:
        if self._driver is None:
            async with self._lock:
                if self._driver is None:
                    uri, extra = self._tls_driver_args()
                    self._driver = AsyncGraphDatabase.driver(
                        uri,
                        auth=basic_auth(self._username, self._password),
                        connection_timeout=settings.neo4j_connection_timeout_seconds,
                        max_connection_lifetime=settings.neo4j_max_connection_lifetime_seconds,
                        **extra,
                    )
        return self._driver

    def _tls_driver_args(self) -> tuple[str, dict[str, Any]]:
        """Resolve the driver URI and any TLS keyword arguments.

        ``ssl_context`` cannot be combined with a ``+s``/``+ssc`` URI — the
        driver raises ConfigurationError — so a verified-TLS scheme is
        downgraded to its base scheme and the encryption is reapplied through
        the context instead. ``+ssc`` (verification deliberately off) and the
        plain schemes are passed through untouched.
        """
        lowered = self._uri.lower()
        for scheme, base_scheme in _VERIFIED_TLS_SCHEMES.items():
            if lowered.startswith(scheme):
                return (
                    base_scheme + self._uri[len(scheme):],
                    {"ssl_context": _verified_ssl_context()},
                )
        return self._uri, {}

    async def connect(self) -> None:
        try:
            driver = await self._get_driver()
            await driver.verify_connectivity()
            await self._ensure_indexes()
            self._connected = True
            logger.info(
                "Neo4j connected — uri=%s",
                self._uri,
            )
        except ServiceUnavailable as exc:
            self._connected = False
            logger.error("Neo4j connection failed — %s", exc)
            raise GraphStoreConnectionError(
                f"Cannot reach Neo4j at {self._uri}: {exc}"
            ) from exc
        except Exception as exc:
            self._connected = False
            logger.exception("Unexpected error during Neo4j connect")
            raise GraphStoreConnectionError(
                f"Neo4j connection failed: {exc}"
            ) from exc

    async def close(self) -> None:
        driver = self._driver
        if driver is not None:
            async with self._lock:
                if self._driver is not None:
                    await self._driver.close()
                    self._driver = None
                    self._connected = False
                    logger.info("Neo4j driver closed")

    async def health_check(self) -> dict:
        start = time.monotonic()
        driver = self._driver
        if driver is None:
            elapsed = (time.monotonic() - start) * 1000
            logger.warning("Health check skipped — Neo4jGraphStore not initialized")
            return {
                "provider": self.provider_name,
                "connection_status": "disconnected",
                "database_version": "",
                "database_name": "",
                "latency_ms": round(elapsed, 2),
            }

        if not self._connected:
            logger.info("Attempting reconnection during health check")
            try:
                await self.connect()
            except GraphStoreConnectionError:
                elapsed = (time.monotonic() - start) * 1000
                return {
                    "provider": self.provider_name,
                    "connection_status": "disconnected",
                    "database_version": "",
                    "database_name": "",
                    "latency_ms": round(elapsed, 2),
                }

        try:
            info = await driver.get_server_info()
            elapsed = (time.monotonic() - start) * 1000
            logger.info(
                "Health check passed — provider=%s version=%s address=%s latency=%.0fms",
                self.provider_name,
                info.agent,
                info.address,
                elapsed,
            )
            db_name = str(info.address) if hasattr(info, "address") and info.address else (info.agent.split("/")[0] if info.agent else "")
            return {
                "provider": self.provider_name,
                "connection_status": "connected",
                "database_version": info.agent,
                "database_name": db_name,
                "latency_ms": round(elapsed, 2),
            }
        except ServiceUnavailable as exc:
            self._connected = False
            elapsed = (time.monotonic() - start) * 1000
            logger.error(
                "Health check failed — connection error after %.0fms: %s",
                elapsed,
                exc,
            )
            return {
                "provider": self.provider_name,
                "connection_status": "disconnected",
                "database_version": "",
                "database_name": "",
                "latency_ms": round(elapsed, 2),
            }
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.error(
                "Health check failed — %s: %s after %.0fms",
                type(exc).__name__,
                exc,
                elapsed,
            )
            return {
                "provider": self.provider_name,
                "connection_status": "error",
                "database_version": "",
                "database_name": "",
                "latency_ms": round(elapsed, 2),
            }

    async def _ensure_connected(self) -> AsyncDriver:
        driver = await self._get_driver()
        if not self._connected:
            logger.info("Reconnecting to Neo4j")
            await self.connect()
            logger.info("Neo4j reconnection successful")
        return driver

    async def execute_read(
        self,
        query: str,
        parameters: dict | None = None,
    ) -> list[dict]:
        import time
        from app.core.observability import metrics
        start_time = time.perf_counter()
        try:
            driver = await self._ensure_connected()
        except GraphStoreConnectionError as exc:
            raise GraphStoreConnectionError(
                f"Cannot execute read query — not connected: {exc}"
            ) from exc

        from app.core.cache import cache_manager
        import hashlib
        import json

        # Build cache key from query and parameters
        cache_key = f"neo4j_read:{hashlib.md5((query + json.dumps(parameters or {}, sort_keys=True)).encode()).hexdigest()}"
        cached_result = await cache_manager.get(cache_key)
        if cached_result is not None:
            metrics.record_histogram("graph.query.time", time.perf_counter() - start_time)
            return cached_result

        try:
            async with driver.session(database=self._db_name) as session:
                result = await session.run(query, parameters or {})
                records = await result.data()
                data = records if records is not None else []
                # Cache for 1 hour
                await cache_manager.set(cache_key, data, ttl=3600)
                metrics.record_histogram("graph.query.time", time.perf_counter() - start_time)
                return data
        except ServiceUnavailable as exc:
            self._connected = False
            raise GraphStoreConnectionError(
                f"Neo4j connection lost during read: {exc}"
            ) from exc
        except (SessionError, TransactionError) as exc:
            raise GraphStoreOperationError(
                f"Neo4j read query failed: {exc}"
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error during Neo4j read query")
            raise GraphStoreOperationError(
                f"Neo4j read query failed: {exc}"
            ) from exc

    async def execute_write(
        self,
        query: str,
        parameters: dict | None = None,
    ) -> list[dict]:
        import time
        from app.core.observability import metrics
        start_time = time.perf_counter()
        try:
            driver = await self._ensure_connected()
        except GraphStoreConnectionError as exc:
            raise GraphStoreConnectionError(
                f"Cannot execute write query — not connected: {exc}"
            ) from exc

        try:
            async with driver.session(database=self._db_name) as session:
                result = await session.run(query, parameters or {})
                records = await result.data()
                await result.consume()
                from app.core.cache import cache_manager
                await cache_manager.delete_pattern("neo4j_read:*")
                metrics.record_histogram("graph.query.time", time.perf_counter() - start_time)
                return records if records is not None else []
        except ServiceUnavailable as exc:
            self._connected = False
            raise GraphStoreConnectionError(
                f"Neo4j connection lost during write: {exc}"
            ) from exc
        except (SessionError, TransactionError) as exc:
            raise GraphStoreOperationError(
                f"Neo4j write query failed: {exc}"
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error during Neo4j write query")
            raise GraphStoreOperationError(
                f"Neo4j write query failed: {exc}"
            ) from exc

    async def begin_transaction(self) -> object:
        try:
            driver = await self._ensure_connected()
        except GraphStoreConnectionError as exc:
            raise GraphStoreConnectionError(
                f"Cannot begin transaction — not connected: {exc}"
            ) from exc

        session = driver.session(database=self._db_name)
        try:
            tx = await session.begin_transaction()
        except ServiceUnavailable as exc:
            await session.close()
            self._connected = False
            raise GraphStoreConnectionError(
                f"Neo4j connection lost during transaction begin: {exc}"
            ) from exc
        except Exception as exc:
            await session.close()
            logger.exception("Unexpected error beginning Neo4j transaction")
            raise GraphStoreOperationError(
                f"Neo4j transaction begin failed: {exc}"
            ) from exc

        return ManagedTransaction(session, tx)
