from abc import ABC, abstractmethod


class GraphStoreError(Exception):
    """Base class for graph store failures."""


class GraphStoreConnectionError(GraphStoreError):
    """Raised when the graph database cannot be reached."""


class GraphStoreConfigurationError(GraphStoreError):
    """Raised when the graph database is misconfigured."""


class GraphStoreOperationError(GraphStoreError):
    """Raised when a graph database operation fails."""


class GraphStore(ABC):
    """Abstract interface for a graph database backend."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connectivity and verify the service is reachable."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Gracefully close all connections and release resources."""
        ...

    @abstractmethod
    async def health_check(self) -> dict:
        """Return a dictionary with connectivity, version, database info, and latency."""
        ...

    @abstractmethod
    async def execute_read(
        self,
        query: str,
        parameters: dict | None = None,
    ) -> list[dict]:
        """Execute a read-only Cypher query and return results as a list of dicts."""
        ...

    @abstractmethod
    async def execute_write(
        self,
        query: str,
        parameters: dict | None = None,
    ) -> list[dict]:
        """Execute a write Cypher query and return results as a list of dicts."""
        ...

    @abstractmethod
    async def begin_transaction(self) -> object:
        """Begin a new transaction and return the transaction object."""
        ...
