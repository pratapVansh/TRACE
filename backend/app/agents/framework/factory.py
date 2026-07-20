import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import LLMProvider, NullLLMProvider
from app.agents.framework.base import BaseAgent
from app.agents.framework.registry import AgentRegistry
from app.graph.graph_query import GraphQueryService
from app.repositories.conversation_repository import ConversationRepository
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


class AgentFactory:
    """Creates agent instances with their dependencies injected.

    Integrates with FastAPI's existing DI container — the factory
    itself is a dependency, and agents created by it receive all
    the services they need via their ``__init__``.

    The factory automatically registers every created agent with the
    provided ``AgentRegistry``.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        llm_provider: LLMProvider | None = None,
        vector_store: VectorStore | None = None,
        graph_query_service: GraphQueryService | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        self._registry = registry
        self._llm = llm_provider or NullLLMProvider()
        self._vector_store = vector_store
        self._graph_svc = graph_query_service
        self._session = session

    def create_agent(self, agent_cls: type[BaseAgent], **kwargs: Any) -> BaseAgent:
        """Instantiate an agent and register it.

        Accepts optional keyword arguments that override the default
        dependencies (e.g. a custom LLM provider for a specific agent).

        Usage::

            agent = factory.create_agent(MyAgent)
            agent = factory.create_agent(MyAgent, llm_provider=my_llm)
        """
        deps: dict[str, Any] = dict(kwargs)

        if "llm_provider" not in deps:
            deps["llm_provider"] = self._llm
        if "vector_store" not in deps and self._vector_store is not None:
            deps["vector_store"] = self._vector_store
        if "graph_query_service" not in deps and self._graph_svc is not None:
            deps["graph_query_service"] = self._graph_svc
        if "session" not in deps and self._session is not None:
            deps["session"] = self._session

        if "conversation_repository" not in deps and self._session is not None:
            deps["conversation_repository"] = ConversationRepository(self._session)

        # Lazy imports for modules that pull in sentence_transformers
        if "hybrid_retriever" not in deps and self._vector_store is not None:
            from app.services.hybrid_retriever import (
                ContextMerger,
                GraphRetriever,
                HybridRetriever,
                VectorRetriever,
            )

            vector_retriever = VectorRetriever(vector_store=self._vector_store)
            graph_retriever = (
                GraphRetriever(graph_query_service=self._graph_svc)
                if self._graph_svc is not None
                else None
            )
            deps["hybrid_retriever"] = HybridRetriever(
                vector_retriever=vector_retriever,
                graph_retriever=graph_retriever,
                context_merger=ContextMerger(),
            )

        if "retriever_service" not in deps and self._vector_store is not None:
            from app.services.retriever_service import RetrieverService

            deps["retriever_service"] = RetrieverService(
                vector_store=self._vector_store,
            )

        agent = agent_cls(**deps)
        self._registry.register(agent)
        logger.info(
            "AgentFactory created agent: %s (%s)",
            agent.agent_id,
            agent.name,
        )
        return agent
