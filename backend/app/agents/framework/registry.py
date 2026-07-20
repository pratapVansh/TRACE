import logging

from app.agents.framework.base import BaseAgent
from app.agents.framework.exceptions import (
    AgentNotFoundError,
    AgentRegistrationError,
)

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Registry for managing and discovering agents.

    Agents are automatically registered when created through the
    ``AgentFactory``, or they can be registered manually.  Supports
    lookup by id, listing, and unregistration.
    """

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent instance.

        Raises ``AgentRegistrationError`` if an agent with the same
        ``agent_id`` is already registered.
        """
        if agent.agent_id in self._agents:
            raise AgentRegistrationError(
                f"Agent '{agent.agent_id}' is already registered."
            )
        self._agents[agent.agent_id] = agent
        logger.info("Registered agent: %s (%s)", agent.agent_id, agent.name)

    def unregister(self, agent_id: str) -> None:
        """Remove an agent from the registry.

        Silently ignores unknown agent ids.
        """
        removed = self._agents.pop(agent_id, None)
        if removed is not None:
            logger.info("Unregistered agent: %s", agent_id)

    def get_agent(self, agent_id: str) -> BaseAgent:
        """Retrieve an agent by its id.

        Raises ``AgentNotFoundError`` if the agent is not registered.
        """
        agent = self._agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError(f"Agent '{agent_id}' not found in registry.")
        return agent

    def list_agents(self) -> list[BaseAgent]:
        """Return every registered agent instance."""
        return list(self._agents.values())

    def find_agent_for_task(self, task: str) -> BaseAgent | None:
        """Return the agent with the highest confidence for a task.

        Iterates all registered agents and calls ``can_handle(task)``
        on each.  Returns the agent with the highest score, or ``None``
        if no agent scores above zero.
        """
        best: BaseAgent | None = None
        best_score = 0.0
        for agent in self._agents.values():
            score = agent.can_handle(task)
            if score > best_score:
                best_score = score
                best = agent
        return best
