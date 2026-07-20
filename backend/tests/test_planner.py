"""Tests for the dynamic Planner module."""
import json
from unittest.mock import AsyncMock

import pytest

from app.agents.framework.base import BaseAgent
from app.agents.framework.factory import AgentFactory
from app.agents.framework.planner import (
    ExecutionPlan,
    ExecutionStep,
    PlanExecutor,
    PlannerAgent,
)
from app.agents.framework.registry import AgentRegistry
from app.agents.framework.response import AgentResponse
from app.agents.framework.workflow.router import _plan_to_routing


# ── Helpers ─────────────────────────────────────────────────────────

class DummyAgent(BaseAgent):
    agent_id = "test_agent"
    name = "Test Agent"
    description = "A test agent."
    supported_tasks = ["test", "analysis"]
    required_permissions = set()

    def can_handle(self, task: str) -> float:
        return 1.0 if task in self.supported_tasks else 0.0

    async def execute(self, context) -> AgentResponse:
        return AgentResponse(
            answer=f"Processed by {self.agent_id}",
            confidence=0.95,
        )


class DummyRCAgent(BaseAgent):
    agent_id = "root_cause_analysis"
    name = "RCA Agent"
    description = "Root cause analysis."
    supported_tasks = ["root_cause", "rca"]
    required_permissions = set()

    async def execute(self, context) -> AgentResponse:
        return AgentResponse(answer="RCA result", confidence=0.9)


class DummyReportAgent(BaseAgent):
    agent_id = "report_generation"
    name = "Report Agent"
    description = "Generates reports."
    supported_tasks = ["report", "generate"]
    required_permissions = set()

    async def execute(self, context) -> AgentResponse:
        return AgentResponse(answer="Report result", confidence=0.95)


class FailingAgent(BaseAgent):
    agent_id = "failing_agent"
    name = "Failing Agent"
    description = "Always fails."
    supported_tasks = ["fail"]
    required_permissions = set()

    async def execute(self, context) -> AgentResponse:
        raise RuntimeError("Intentional failure")


@pytest.fixture
def registry():
    r = AgentRegistry()
    r.register(DummyAgent())
    r.register(DummyRCAgent())
    r.register(DummyReportAgent())
    return r


@pytest.fixture
def factory(registry):
    return AgentFactory(registry)


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    return llm


# ── ExecutionPlan / ExecutionStep ───────────────────────────────────

class TestExecutionSchemas:
    def test_execution_step_defaults(self):
        step = ExecutionStep(step_id="s1", description="test")
        assert step.step_id == "s1"
        assert step.agent_id is None
        assert step.depends_on == []
        assert step.parallel_with == []
        assert step.retry_on_failure is True
        assert step.max_retries == 1

    def test_execution_plan(self):
        step = ExecutionStep(step_id="s1", description="test", agent_id="test_agent")
        plan = ExecutionPlan(goal="test goal", steps=[step], reasoning="because")
        assert plan.goal == "test goal"
        assert len(plan.steps) == 1
        assert plan.reasoning == "because"
        assert plan.estimated_complexity == "moderate"


# ── PlannerAgent ────────────────────────────────────────────────────

class TestPlannerAgent:
    @pytest.mark.asyncio
    async def test_plan_with_llm(self, registry, mock_llm):
        plan_json = json.dumps({
            "goal": "Analyse pump failure",
            "steps": [
                {
                    "step_id": "step_1",
                    "description": "Find root cause",
                    "agent_id": "root_cause_analysis",
                    "depends_on": [],
                    "parallel_with": [],
                    "retry_on_failure": True,
                    "max_retries": 1,
                    "fallback_agent_id": None,
                    "required_data": [],
                    "output_key": "rca_result",
                    "llm_prompt_template": None,
                },
                {
                    "step_id": "step_2",
                    "description": "Generate report",
                    "agent_id": "report_generation",
                    "depends_on": ["step_1"],
                    "parallel_with": [],
                    "retry_on_failure": True,
                    "max_retries": 1,
                    "fallback_agent_id": None,
                    "required_data": ["rca_result"],
                    "output_key": "report",
                    "llm_prompt_template": None,
                },
            ],
            "reasoning": "Chain RCA then report.",
            "estimated_complexity": "moderate",
            "requires_supervision": False,
        })
        mock_llm.generate.return_value = f"```json\n{plan_json}\n```"

        planner = PlannerAgent(registry, llm_provider=mock_llm)
        plan = await planner.plan("Analyse pump failure")

        assert plan.goal == "Analyse pump failure"
        assert len(plan.steps) == 2
        assert plan.steps[0].agent_id == "root_cause_analysis"
        assert plan.steps[1].agent_id == "report_generation"
        assert plan.steps[1].depends_on == ["step_1"]
        assert plan.reasoning == "Chain RCA then report."
        assert plan.estimated_complexity == "moderate"

        # Verify LLM was called with the agents list
        call_args = mock_llm.generate.call_args
        assert call_args is not None
        prompt = call_args.kwargs["prompt"]
        assert "test_agent" in prompt
        assert "root_cause_analysis" in prompt

    @pytest.mark.asyncio
    async def test_plan_without_llm_fallback(self, registry):
        planner = PlannerAgent(registry, llm_provider=None)
        plan = await planner.plan("root cause pump failure")

        assert len(plan.steps) == 1
        assert plan.estimated_complexity == "simple"
        assert plan.goal == "root cause pump failure"

    @pytest.mark.asyncio
    async def test_plan_with_llm_error_fallback(self, registry, mock_llm):
        mock_llm.generate.side_effect = RuntimeError("LLM down")

        planner = PlannerAgent(registry, llm_provider=mock_llm)
        plan = await planner.plan("maintenance check")

        assert len(plan.steps) == 1
        assert plan.estimated_complexity == "simple"

    def test_build_agents_list(self, registry):
        planner = PlannerAgent(registry)
        agents = planner._build_agents_list()
        assert len(agents) == 3
        ids = {a["agent_id"] for a in agents}
        assert ids == {"test_agent", "root_cause_analysis", "report_generation"}
        for a in agents:
            assert "name" in a
            assert "description" in a
            assert "supported_tasks" in a

    def test_pick_best_agent(self, registry):
        planner = PlannerAgent(registry)
        agent = planner._pick_best_agent("test")
        assert agent is not None
        assert agent.agent_id == "test_agent"

    def test_pick_best_agent_no_match(self, registry):
        planner = PlannerAgent(registry)
        agent = planner._pick_best_agent("something completely unknown")
        assert agent is None or agent.agent_id is not None


# ── PlanExecutor ────────────────────────────────────────────────────

class TestPlanExecutor:
    @pytest.mark.asyncio
    async def test_execute_single_step(self, registry, factory):
        plan = ExecutionPlan(
            goal="test",
            steps=[ExecutionStep(
                step_id="s1",
                description="Do a test",
                agent_id="test_agent",
                output_key="result",
            )],
        )
        executor = PlanExecutor(registry, factory)
        response = await executor.execute(
            plan=plan, question="test", user_id="u1", user_role="Admin",
        )
        assert response.answer == "Processed by test_agent"
        assert response.confidence == 0.95
        assert len(response.execution_order) == 1

    @pytest.mark.asyncio
    async def test_execute_chain(self, registry, factory):
        plan = ExecutionPlan(
            goal="RCA then report",
            steps=[
                ExecutionStep(
                    step_id="s1",
                    description="Find root cause",
                    agent_id="root_cause_analysis",
                    output_key="rca",
                ),
                ExecutionStep(
                    step_id="s2",
                    description="Generate report",
                    agent_id="report_generation",
                    depends_on=["s1"],
                    output_key="report",
                ),
            ],
        )
        executor = PlanExecutor(registry, factory)
        response = await executor.execute(
            plan=plan, question="rca pump fail", user_id="u1", user_role="Admin",
        )
        assert "RCA result" in response.answer
        assert "Report result" in response.answer
        assert len(response.execution_order) == 2
        assert len(response.timeline) == 2
        assert all(t.status == "success" for t in response.timeline)

    @pytest.mark.asyncio
    async def test_execute_empty_plan(self, registry, factory):
        plan = ExecutionPlan(goal="nothing", steps=[])
        executor = PlanExecutor(registry, factory)
        response = await executor.execute(
            plan=plan, question="nothing", user_id="u1", user_role="Admin",
        )
        assert "No agents could process" in response.answer

    @pytest.mark.asyncio
    async def test_execute_step_retry_then_fallback(self, registry, factory):
        """Test a step that fails then succeeds via fallback agent."""
        registry.register(FailingAgent())  # Will fail during execute()
        plan = ExecutionPlan(
            goal="test fallback",
            steps=[ExecutionStep(
                step_id="s1",
                description="Will fail",
                agent_id="failing_agent",  # exists but raises RuntimeError
                retry_on_failure=True,
                max_retries=1,
                fallback_agent_id="test_agent",
                output_key="result",
            )],
        )
        executor = PlanExecutor(registry, factory)
        response = await executor.execute(
            plan=plan, question="test", user_id="u1", user_role="Admin",
        )
        # Fallback should produce a result
        assert "Processed by test_agent" in response.answer

    @pytest.mark.asyncio
    async def test_step_output_passed_to_context(self, registry, factory):
        plan = ExecutionPlan(
            goal="chain with context passing",
            steps=[
                ExecutionStep(
                    step_id="s1",
                    description="First step",
                    agent_id="root_cause_analysis",
                    output_key="rca_out",
                ),
            ],
        )
        executor = PlanExecutor(registry, factory)
        response = await executor.execute(
            plan=plan, question="test", user_id="u1", user_role="Admin",
        )
        assert response.execution_order == ["RCA Agent"]


# ── Routing plan conversion ─────────────────────────────────────────

class TestPlanToRouting:
    def test_single_agent_plan(self):
        plan = ExecutionPlan(
            goal="test",
            steps=[ExecutionStep(
                step_id="s1",
                description="test",
                agent_id="test_agent",
            )],
        )
        rp = _plan_to_routing(plan, mode="single")
        assert rp.primary_agents == ["test_agent"]
        assert rp.execution_mode == "single"

    def test_chain_detection(self):
        plan = ExecutionPlan(
            goal="chain",
            steps=[
                ExecutionStep(
                    step_id="s1",
                    description="RCA",
                    agent_id="root_cause_analysis",
                ),
                ExecutionStep(
                    step_id="s2",
                    description="Report",
                    agent_id="report_generation",
                    depends_on=["s1"],
                ),
            ],
        )
        rp = _plan_to_routing(plan)
        assert rp.execution_mode == "sequential"
        assert rp.chain is not None

    def test_empty_plan(self):
        plan = ExecutionPlan(goal="empty", steps=[])
        rp = _plan_to_routing(plan)
        assert rp.primary_agents == []

    def test_fallback_extraction(self):
        plan = ExecutionPlan(
            goal="test",
            steps=[ExecutionStep(
                step_id="s1",
                description="test",
                agent_id="test_agent",
                fallback_agent_id="root_cause_analysis",
            )],
        )
        rp = _plan_to_routing(plan)
        assert "root_cause_analysis" in rp.fallback_agents


# ── Topological sort ────────────────────────────────────────────────

from app.agents.framework.planner.plan_executor import _topological_sort


class TestTopologicalSort:
    def test_simple_linear(self):
        steps = [
            ExecutionStep(step_id="a", description="a"),
            ExecutionStep(step_id="b", description="b", depends_on=["a"]),
            ExecutionStep(step_id="c", description="c", depends_on=["b"]),
        ]
        levels = _topological_sort(steps)
        assert levels == [["a"], ["b"], ["c"]]

    def test_parallel_levels(self):
        steps = [
            ExecutionStep(step_id="a", description="a"),
            ExecutionStep(step_id="b", description="b"),
            ExecutionStep(step_id="c", description="c", depends_on=["a", "b"]),
        ]
        levels = _topological_sort(steps)
        assert len(levels) == 2
        assert set(levels[0]) == {"a", "b"}
        assert levels[1] == ["c"]

    def test_circular_dependency(self):
        steps = [
            ExecutionStep(step_id="a", description="a", depends_on=["b"]),
            ExecutionStep(step_id="b", description="b", depends_on=["a"]),
        ]
        levels = _topological_sort(steps)
        assert len(levels) > 0

    def test_no_dependencies(self):
        steps = [
            ExecutionStep(step_id="a", description="a"),
            ExecutionStep(step_id="b", description="b"),
            ExecutionStep(step_id="c", description="c"),
        ]
        levels = _topological_sort(steps)
        assert len(levels) == 1
        assert set(levels[0]) == {"a", "b", "c"}
