"""Multi-agent workflow orchestration (Milestone 10 Prompt 10).

Sub-package providing automatic agent routing, selection, chaining,
parallel execution, fallback, shared memory, cross-agent context
passing, confidence aggregation, and execution timelines.
"""

from app.agents.framework.workflow.executor import MultiAgentExecutor
from app.agents.framework.workflow.router import AgentRouter, RoutingPlan
from app.agents.framework.workflow.schemas import (
    MultiAgentRequest,
    MultiAgentResponse,
    TimelineEntry,
)

__all__ = [
    "AgentRouter",
    "MultiAgentExecutor",
    "MultiAgentRequest",
    "MultiAgentResponse",
    "RoutingPlan",
    "TimelineEntry",
]
