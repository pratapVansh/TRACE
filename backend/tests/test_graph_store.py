"""Unit tests for GraphStore interface and Neo4jGraphStore implementation."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from neo4j.exceptions import ServiceUnavailable, SessionError

from app.graph.base import (
    GraphStore,
    GraphStoreConfigurationError,
    GraphStoreConnectionError,
    GraphStoreOperationError,
)
from app.graph.neo4j_graph_store import ManagedTransaction, Neo4jGraphStore


@pytest.fixture(autouse=True)
def _patch_settings():
    with (
        patch("app.graph.neo4j_graph_store.settings") as mock_settings,
        patch("app.core.config.settings") as mock_config_settings,
    ):
        mock_settings.neo4j_uri = "bolt://localhost:7687"
        mock_settings.neo4j_username = "neo4j"
        mock_settings.neo4j_password = "password"
        mock_settings.neo4j_database = "neo4j"
        mock_settings.neo4j_connection_timeout_seconds = 30
        mock_settings.neo4j_max_connection_lifetime_seconds = 3600
        mock_config_settings.neo4j_connection_timeout_seconds = 30
        mock_config_settings.neo4j_max_connection_lifetime_seconds = 3600
        yield


class TestGraphStoreInterface:
    """Verify the GraphStore ABC enforces the expected contract."""

    def test_interface_cannot_be_instantiated(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            GraphStore()

    def test_concrete_subclass_must_implement_all_methods(self):
        class Incomplete(GraphStore):
            pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            Incomplete()


class TestNeo4jGraphStoreConfig:
    def test_missing_uri_raises(self):
        with (
            patch("app.graph.neo4j_graph_store.settings") as s,
        ):
            s.neo4j_uri = ""
            s.neo4j_username = "neo4j"
            s.neo4j_password = "password"
            with pytest.raises(GraphStoreConfigurationError, match="NEO4J_URI"):
                Neo4jGraphStore()

    def test_missing_username_raises(self):
        with (
            patch("app.graph.neo4j_graph_store.settings") as s,
        ):
            s.neo4j_uri = "bolt://localhost:7687"
            s.neo4j_username = ""
            s.neo4j_password = "password"
            with pytest.raises(GraphStoreConfigurationError, match="NEO4J_USERNAME"):
                Neo4jGraphStore()

    def test_missing_password_raises(self):
        with (
            patch("app.graph.neo4j_graph_store.settings") as s,
        ):
            s.neo4j_uri = "bolt://localhost:7687"
            s.neo4j_username = "neo4j"
            s.neo4j_password = ""
            with pytest.raises(GraphStoreConfigurationError, match="NEO4J_PASSWORD"):
                Neo4jGraphStore()

    def test_explicit_credentials_override_settings(self):
        store = Neo4jGraphStore(
            uri="bolt://custom:7687",
            username="custom_user",
            password="custom_pass",
        )
        assert store._uri == "bolt://custom:7687"
        assert store._username == "custom_user"
        assert store._password == "custom_pass"

    def test_provider_name(self):
        store = Neo4jGraphStore()
        assert store.provider_name == "neo4j"

    def test_invalid_uri_scheme_raises(self):
        with patch("app.graph.neo4j_graph_store.settings") as s:
            s.neo4j_uri = "http://localhost:7687"
            s.neo4j_username = "neo4j"
            s.neo4j_password = "password"
            with pytest.raises(GraphStoreConfigurationError, match="invalid scheme"):
                Neo4jGraphStore()

    def test_invalid_uri_scheme_listed_prefixes(self):
        with patch("app.graph.neo4j_graph_store.settings") as s:
            s.neo4j_uri = "mysql://localhost:7687"
            s.neo4j_username = "neo4j"
            s.neo4j_password = "password"
            with pytest.raises(
                GraphStoreConfigurationError, match="bolt://|neo4j://"
            ):
                Neo4jGraphStore()

    def test_whitespace_uri_treated_as_missing(self):
        with patch("app.graph.neo4j_graph_store.settings") as s:
            s.neo4j_uri = "   "
            s.neo4j_username = "neo4j"
            s.neo4j_password = "password"
            with pytest.raises(GraphStoreConfigurationError, match="NEO4J_URI is not set"):
                Neo4jGraphStore()

    def test_whitespace_username_treated_as_missing(self):
        with patch("app.graph.neo4j_graph_store.settings") as s:
            s.neo4j_uri = "bolt://localhost:7687"
            s.neo4j_username = "  "
            s.neo4j_password = "password"
            with pytest.raises(GraphStoreConfigurationError, match="NEO4J_USERNAME is not set"):
                Neo4jGraphStore()

    def test_whitespace_password_treated_as_missing(self):
        with patch("app.graph.neo4j_graph_store.settings") as s:
            s.neo4j_uri = "bolt://localhost:7687"
            s.neo4j_username = "neo4j"
            s.neo4j_password = "   "
            with pytest.raises(GraphStoreConfigurationError, match="NEO4J_PASSWORD is not set"):
                Neo4jGraphStore()

    def test_multiple_config_errors_reported_together(self):
        with patch("app.graph.neo4j_graph_store.settings") as s:
            s.neo4j_uri = ""
            s.neo4j_username = ""
            s.neo4j_password = ""
            with pytest.raises(
                GraphStoreConfigurationError,
                match="NEO4J_URI.*NEO4J_USERNAME.*NEO4J_PASSWORD",
            ):
                Neo4jGraphStore()

    def test_invalid_uri_and_missing_username_reported_together(self):
        with patch("app.graph.neo4j_graph_store.settings") as s:
            s.neo4j_uri = "bad-scheme://host"
            s.neo4j_username = ""
            s.neo4j_password = "password"
            with pytest.raises(
                GraphStoreConfigurationError,
                match="invalid scheme.*NEO4J_USERNAME",
            ):
                Neo4jGraphStore()

    def test_uri_scheme_check_is_case_insensitive(self):
        store = Neo4jGraphStore(
            uri="BOLT://localhost:7687",
            username="neo4j",
            password="password",
        )
        # Scheme is validated case-insensitively; stored value is preserved as-is
        assert store._uri == "BOLT://localhost:7687"
        assert store._username == "neo4j"

    def test_uri_is_stripped_of_whitespace(self):
        store = Neo4jGraphStore(
            uri="  bolt://localhost:7687  ",
            username="neo4j",
            password="password",
        )
        assert store._uri == "bolt://localhost:7687"


class TestNeo4jGraphStoreConnect:
    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_connect_success(self, mock_driver_factory):
        mock_driver = AsyncMock()
        mock_driver_factory.return_value = mock_driver

        store = Neo4jGraphStore()
        await store.connect()

        mock_driver_factory.assert_called_once()
        assert store._connected is True
        assert store._driver is mock_driver

    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_connect_service_unavailable(self, mock_driver_factory):
        mock_driver = AsyncMock()
        mock_driver.verify_connectivity.side_effect = ServiceUnavailable("No route")
        mock_driver_factory.return_value = mock_driver

        store = Neo4jGraphStore()
        with pytest.raises(GraphStoreConnectionError, match="Cannot reach Neo4j"):
            await store.connect()
        assert store._connected is False


class TestNeo4jGraphStoreClose:
    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_close_idempotent_when_not_connected(self, mock_driver_factory):
        store = Neo4jGraphStore()
        await store.close()

    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_close_releases_driver(self, mock_driver_factory):
        mock_driver = AsyncMock()
        mock_driver_factory.return_value = mock_driver

        store = Neo4jGraphStore()
        await store.connect()
        await store.close()

        mock_driver.close.assert_awaited_once()
        assert store._driver is None
        assert store._connected is False

    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_close_idempotent_when_called_twice(self, mock_driver_factory):
        mock_driver = AsyncMock()
        mock_driver_factory.return_value = mock_driver

        store = Neo4jGraphStore()
        await store.connect()
        await store.close()
        await store.close()

        mock_driver.close.assert_awaited_once()


class TestNeo4jGraphStoreHealthCheck:
    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_health_check_not_initialized(self, mock_driver_factory):
        store = Neo4jGraphStore()
        result = await store.health_check()

        assert result["provider"] == "neo4j"
        assert result["connection_status"] == "disconnected"
        assert result["database_version"] == ""
        assert result["database_name"] == ""
        assert isinstance(result["latency_ms"], float)

    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_health_check_reconnects_when_disconnected(self, mock_driver_factory):
        mock_driver = AsyncMock()
        mock_server_info = MagicMock()
        mock_server_info.agent = "Neo4j/5.20.0"
        # health_check reports ``ServerInfo.address`` (the driver's real API).
        # Setting ``.server`` instead left ``.address`` as an auto-created
        # MagicMock, which stringifies to a repr rather than an address.
        mock_server_info.address = "neo4j@localhost:7687"
        mock_driver.get_server_info = AsyncMock(return_value=mock_server_info)
        mock_driver_factory.return_value = mock_driver

        store = Neo4jGraphStore()
        store._driver = mock_driver
        store._connected = False

        result = await store.health_check()

        mock_driver.verify_connectivity.assert_awaited_once()
        assert result["connection_status"] == "connected"
        assert result["database_version"] == "Neo4j/5.20.0"
        assert result["database_name"] == "neo4j@localhost:7687"
        assert result["latency_ms"] > 0

    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_health_check_returned_disconnected_on_failure(
        self, mock_driver_factory
    ):
        mock_driver = AsyncMock()
        mock_driver.get_server_info = AsyncMock(
            side_effect=ServiceUnavailable("No route")
        )
        mock_driver_factory.return_value = mock_driver

        store = Neo4jGraphStore()
        store._driver = mock_driver
        store._connected = True

        result = await store.health_check()

        assert result["connection_status"] == "disconnected"
        assert result["database_version"] == ""

    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_health_check_latency_measured(self, mock_driver_factory):
        mock_driver = AsyncMock()
        mock_server_info = MagicMock()
        mock_driver.get_server_info = AsyncMock(return_value=mock_server_info)
        mock_driver_factory.return_value = mock_driver

        store = Neo4jGraphStore()
        store._driver = mock_driver
        store._connected = True

        result = await store.health_check()

        assert result["latency_ms"] > 0


class TestNeo4jGraphStoreExecuteRead:
    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_execute_read_success(self, mock_driver_factory):
        mock_driver = AsyncMock()
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[{"n": 1}, {"n": 2}])

        mock_driver_factory.return_value = mock_driver
        mock_driver.session = MagicMock()
        mock_driver.session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(return_value=mock_result)

        store = Neo4jGraphStore()
        await store.connect()
        records = await store.execute_read("MATCH (n) RETURN n LIMIT 2")

        assert records == [{"n": 1}, {"n": 2}]
        mock_session.run.assert_awaited_with(
            "MATCH (n) RETURN n LIMIT 2", {}
        )

    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_execute_read_with_parameters(self, mock_driver_factory):
        mock_driver = AsyncMock()
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[{"n": {"id": 42}}])

        mock_driver_factory.return_value = mock_driver
        mock_driver.session = MagicMock()
        mock_driver.session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(return_value=mock_result)

        store = Neo4jGraphStore()
        await store.connect()
        records = await store.execute_read(
            "MATCH (n) WHERE n.id = $id RETURN n",
            {"id": 42},
        )

        assert records == [{"n": {"id": 42}}]
        mock_session.run.assert_awaited_with(
            "MATCH (n) WHERE n.id = $id RETURN n",
            {"id": 42},
        )

    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_execute_read_connection_lost(self, mock_driver_factory):
        mock_driver = AsyncMock()

        mock_driver_factory.return_value = mock_driver
        mock_driver.session = MagicMock()
        mock_driver.session.return_value.__aenter__ = AsyncMock(
            side_effect=ServiceUnavailable("Lost connection")
        )
        mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=None)

        store = Neo4jGraphStore()
        await store.connect()
        with pytest.raises(GraphStoreConnectionError, match="connection lost"):
            await store.execute_read("MATCH (n) RETURN n")

    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_execute_read_not_connected(self, mock_driver_factory):
        store = Neo4jGraphStore()
        with pytest.raises(GraphStoreConnectionError, match="not connected"):
            await store.execute_read("MATCH (n) RETURN n")


class TestNeo4jGraphStoreExecuteWrite:
    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_execute_write_success(self, mock_driver_factory):
        mock_driver = AsyncMock()
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[{"n": {"id": 1}}])

        mock_driver_factory.return_value = mock_driver
        mock_driver.session = MagicMock()
        mock_driver.session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(return_value=mock_result)

        store = Neo4jGraphStore()
        await store.connect()
        records = await store.execute_write(
            "CREATE (n:Test {name: $name}) RETURN n",
            {"name": "test"},
        )

        assert records == [{"n": {"id": 1}}]
        mock_result.consume.assert_awaited_once()

    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_execute_write_not_connected(self, mock_driver_factory):
        store = Neo4jGraphStore()
        with pytest.raises(GraphStoreConnectionError, match="not connected"):
            await store.execute_write("CREATE (n) RETURN n")


class TestNeo4jGraphStoreBeginTransaction:
    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_begin_transaction_success(self, mock_driver_factory):
        mock_driver = AsyncMock()
        mock_session = MagicMock()
        mock_tx = AsyncMock()

        mock_driver_factory.return_value = mock_driver
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.begin_transaction = AsyncMock(return_value=mock_tx)

        store = Neo4jGraphStore()
        await store.connect()
        tx = await store.begin_transaction()

        assert isinstance(tx, ManagedTransaction)
        mock_session.begin_transaction.assert_awaited_once()

    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_begin_transaction_not_connected(self, mock_driver_factory):
        store = Neo4jGraphStore()
        with pytest.raises(GraphStoreConnectionError, match="not connected"):
            await store.begin_transaction()

    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_begin_transaction_closes_session_on_service_unavailable(
        self, mock_driver_factory,
    ):
        mock_driver = AsyncMock()
        mock_session = MagicMock()
        mock_session.close = AsyncMock()

        mock_driver_factory.return_value = mock_driver
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.begin_transaction = AsyncMock(
            side_effect=ServiceUnavailable("Down"),
        )

        store = Neo4jGraphStore()
        await store.connect()
        with pytest.raises(GraphStoreConnectionError, match="Down"):
            await store.begin_transaction()

        mock_session.close.assert_awaited_once()

    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_begin_transaction_closes_session_on_generic_error(
        self, mock_driver_factory,
    ):
        mock_driver = AsyncMock()
        mock_session = MagicMock()
        mock_session.close = AsyncMock()

        mock_driver_factory.return_value = mock_driver
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.begin_transaction = AsyncMock(
            side_effect=RuntimeError("Unexpected"),
        )

        store = Neo4jGraphStore()
        await store.connect()
        with pytest.raises(GraphStoreOperationError, match="Unexpected"):
            await store.begin_transaction()

        mock_session.close.assert_awaited_once()


class TestManagedTransaction:
    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        session.close = AsyncMock()
        return session

    @pytest.fixture
    def mock_tx(self):
        return AsyncMock()

    @pytest.fixture
    def managed_tx(self, mock_session, mock_tx):
        return ManagedTransaction(mock_session, mock_tx)

    @pytest.mark.asyncio
    async def test_commit_closes_session(
        self, managed_tx, mock_session, mock_tx,
    ):
        await managed_tx.commit()

        mock_tx.commit.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rollback_closes_session(
        self, managed_tx, mock_session, mock_tx,
    ):
        await managed_tx.rollback()

        mock_tx.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_commit_closes_session_even_on_failure(
        self, managed_tx, mock_session, mock_tx,
    ):
        mock_tx.commit.side_effect = RuntimeError("commit failed")

        with pytest.raises(RuntimeError, match="commit failed"):
            await managed_tx.commit()

        mock_tx.commit.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rollback_closes_session_even_on_failure(
        self, managed_tx, mock_session, mock_tx,
    ):
        mock_tx.rollback.side_effect = RuntimeError("rollback failed")

        with pytest.raises(RuntimeError, match="rollback failed"):
            await managed_tx.rollback()

        mock_tx.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_closed_delegates_to_transaction(
        self, managed_tx, mock_tx,
    ):
        mock_tx.closed = False
        assert managed_tx.closed is False

        mock_tx.closed = True
        assert managed_tx.closed is True

    @pytest.mark.asyncio
    async def test_attribute_delegation(self, managed_tx, mock_tx):
        mock_tx.foo = "bar"
        assert managed_tx.foo == "bar"

    @pytest.mark.asyncio
    async def test_async_context_manager_commits_on_success(
        self, managed_tx, mock_session, mock_tx,
    ):
        async with managed_tx:
            pass

        mock_tx.commit.assert_awaited_once()
        mock_tx.rollback.assert_not_called()
        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_context_manager_rolls_back_on_error(
        self, managed_tx, mock_session, mock_tx,
    ):
        with pytest.raises(ValueError, match="oops"):
            async with managed_tx:
                raise ValueError("oops")

        mock_tx.rollback.assert_awaited_once()
        mock_tx.commit.assert_not_called()
        mock_session.close.assert_awaited_once()


class TestNeo4jGraphStoreReconnect:
    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_execute_read_triggers_reconnect(self, mock_driver_factory):
        mock_driver = AsyncMock()
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[{"n": 1}])

        mock_driver_factory.return_value = mock_driver
        mock_driver.session = MagicMock()
        mock_driver.session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(return_value=mock_result)

        store = Neo4jGraphStore()
        store._driver = mock_driver
        store._connected = False

        records = await store.execute_read("MATCH (n) RETURN n LIMIT 1")

        mock_driver.verify_connectivity.assert_awaited_once()
        assert records == [{"n": 1}]


class TestNeo4jGraphStoreThreadSafety:
    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_concurrent_close_safe(self, mock_driver_factory):
        mock_driver = AsyncMock()
        mock_driver_factory.return_value = mock_driver

        store = Neo4jGraphStore()
        await store.connect()

        async def closer():
            await store.close()

        await asyncio.gather(closer(), closer())

        mock_driver.close.assert_awaited_once()

    @patch("app.graph.neo4j_graph_store.AsyncGraphDatabase.driver")
    async def test_get_driver_thread_safe_double_check(self, mock_driver_factory):
        mock_driver = AsyncMock()
        mock_driver_factory.return_value = mock_driver

        store = Neo4jGraphStore()

        async def get_driver():
            return await store._get_driver()

        drivers = await asyncio.gather(get_driver(), get_driver())

        mock_driver_factory.assert_called_once()
        assert drivers[0] is drivers[1]
