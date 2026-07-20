"""Dynamic LLM-based planner for multi-agent execution (Milestone 10 Prompt 11).

Replaces hardcoded keyword/if-else routing with an LLM that analyses
the user's question, available agents, and their capabilities, then
produces an ``ExecutionPlan`` — a DAG of steps with dependency ordering,
parallelisation, retry, and fallback.

Components:
- ``ExecutionPlan`` / ``ExecutionStep`` — schema for a plan
- ``PlannerAgent`` — LLM-powered planner that produces plans
- ``PlanExecutor`` — executes a plan against the agent framework
"""

from app.agents.framework.planner.schemas import ExecutionPlan, ExecutionStep
from app.agents.framework.planner.planner_agent import PlannerAgent
from app.agents.framework.planner.plan_executor import PlanExecutor

__all__ = [
    "ExecutionPlan",
    "ExecutionStep",
    "PlannerAgent",
    "PlanExecutor",
]
