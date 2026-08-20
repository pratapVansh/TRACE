"""Regression tests for :class:`AIOrchestrator` single-agent execution.

``AIOrchestrator.execute`` had no committed coverage, which allowed a
missing ``await`` on the ``async`` ``_select_agent`` helper to ship: the
coroutine object was assigned straight to ``agent`` and the very next
statement (``agent.agent_id``) raised ``AttributeError`` on every call.
These tests pin the happy path and the permission/unknown-agent paths so
the regression cannot recur silently.
"""

import pytest

from app.agents.framework.base import BaseAgent
from app.agents.framework.exceptions import OrchestrationError
from app.agents.framework.orchestrator import AIOrchestrator
from app.agents.framework.registry import AgentRegistry
from app.agents.framework.response import AgentResponse
from app.core.authorization import Permission


class _StubAgent(BaseAgent):
    agent_id = "stub"
    name = "Stub Agent"
    description = "Test double that returns a fixed response."
    supported_tasks = ["stub"]
    required_permissions: set[Permission] = set()

    def __init__(self) -> None:
        self.executed_with = None

    async def execute(self, context) -> AgentResponse:
        self.executed_with = context
        return AgentResponse(
            answer="stub answer",
            confidence=0.9,
            agent_name=self.agent_id,
        )


class _RestrictedAgent(_StubAgent):
    agent_id = "restricted"
    name = "Restricted Agent"
    required_permissions = {Permission.USER_MANAGEMENT}


def _make_orchestrator(*agents: BaseAgent) -> AIOrchestrator:
    registry = AgentRegistry()
    for agent in agents:
        registry.register(agent)
    # llm_provider/memory_manager omitted: self-critique and persistence are
    # skipped when they are None, keeping this test to the routing path.
    return AIOrchestrator(registry=registry, factory=None)


@pytest.mark.asyncio
async def test_execute_awaits_agent_selection_and_returns_response():
    """The explicit-``agent_id`` path must resolve a real agent, not a coroutine."""
    agent = _StubAgent()
    orchestrator = _make_orchestrator(agent)

    response = await orchestrator.execute(
        question="why did pump P-101 fail?",
        user_id="user-1",
        user_role="Engineer",
        agent_id="stub",
    )

    assert isinstance(response, AgentResponse)
    # The orchestrator stamps the agent's display name onto the response
    # (orchestrator.py:246), which is only reachable via a resolved agent.
    assert response.agent_name == "Stub Agent"
    # Proves the agent was actually invoked rather than an un-awaited
    # coroutine being passed down the pipeline.
    assert agent.executed_with is not None
    assert agent.executed_with.question == "why did pump P-101 fail?"


@pytest.mark.asyncio
async def test_execute_rejects_unknown_agent_id():
    orchestrator = _make_orchestrator(_StubAgent())

    with pytest.raises(OrchestrationError, match="not registered"):
        await orchestrator.execute(
            question="anything",
            user_id="user-1",
            user_role="Engineer",
            agent_id="does-not-exist",
        )


@pytest.mark.asyncio
async def test_execute_enforces_agent_permissions():
    orchestrator = _make_orchestrator(_RestrictedAgent())

    with pytest.raises(OrchestrationError, match="Access denied"):
        await orchestrator.execute(
            question="anything",
            user_id="user-1",
            user_role="Viewer",
            agent_id="restricted",
        )
