"""Tests for agent routing: capability scoring and plan parsing.

These cover the paths the system falls back to when the planner LLM is
unavailable or returns something imperfect — exactly when routing quality
matters most and is least observed.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.framework.base import BaseAgent
from app.agents.framework.planner.planner_agent import (
    PlannerAgent,
    _balanced_object,
    _extract_json,
)
from app.agents.framework.planner.schemas import ExecutionStep


class _Agent(BaseAgent):
    def __init__(self, agent_id: str, tasks: list[str]) -> None:
        self.agent_id = agent_id
        self.name = agent_id
        self.description = ""
        self.supported_tasks = tasks
        self.required_permissions = set()

    async def execute(self, context):  # pragma: no cover - never invoked
        raise NotImplementedError


class TestCanHandle:
    def test_whole_question_scores_against_keywords(self) -> None:
        """A real question must score above zero.

        ``task in supported_tasks`` required the question to *equal* a label,
        so every agent scored 0.0 and keyword routing never fired.
        """
        agent = _Agent("asset", ["asset", "equipment", "maintenance history"])

        assert agent.can_handle("Show the maintenance history for this asset") > 0.0

    def test_more_matches_score_higher(self) -> None:
        agent = _Agent("asset", ["asset", "equipment", "parts"])

        one = agent.can_handle("Tell me about this asset")
        many = agent.can_handle("List asset equipment parts")

        assert many > one

    def test_unrelated_question_scores_zero(self) -> None:
        agent = _Agent("asset", ["asset", "equipment"])

        assert agent.can_handle("What is the weather today?") == 0.0

    def test_matching_respects_word_boundaries(self) -> None:
        """Substring matching would route "united" to the "unit" agent."""
        agent = _Agent("asset", ["unit", "part"])

        assert agent.can_handle("the united nations partition") == 0.0

    def test_multi_word_label_outranks_single_generic_word(self) -> None:
        specific = _Agent("maint", ["maintenance history"])
        generic = _Agent("asset", ["unit"])

        question = "give me the maintenance history for unit 4"

        assert specific.can_handle(question) > generic.can_handle(question)

    def test_agent_without_tasks_scores_zero(self) -> None:
        assert _Agent("empty", []).can_handle("anything") == 0.0

    def test_blank_question_scores_zero(self) -> None:
        assert _Agent("asset", ["asset"]).can_handle("   ") == 0.0

    def test_matching_is_case_insensitive(self) -> None:
        agent = _Agent("asset", ["Asset"])

        assert agent.can_handle("show the ASSET") > 0.0

    def test_score_never_exceeds_one(self) -> None:
        agent = _Agent("asset", [f"kw{i}" for i in range(50)])
        question = " ".join(f"kw{i}" for i in range(50))

        assert agent.can_handle(question) <= 1.0


class TestExtractJson:
    def test_bare_object(self) -> None:
        assert json.loads(_extract_json('{"goal": "x"}'))["goal"] == "x"

    def test_fenced_object(self) -> None:
        raw = "```json\n" + '{"goal": "x"}' + "\n```"

        assert json.loads(_extract_json(raw))["goal"] == "x"

    def test_fence_with_preamble_and_trailer(self) -> None:
        """The common real-world shape, which used to fail outright."""
        raw = "Here is the plan:\n```json\n" + '{"goal": "x"}' + "\n```\nHope this helps!"

        assert json.loads(_extract_json(raw))["goal"] == "x"

    def test_object_with_prose_around_it(self) -> None:
        raw = 'Sure. {"goal": "x"} Let me know if you need changes.'

        assert json.loads(_extract_json(raw))["goal"] == "x"

    def test_braces_inside_strings_do_not_truncate(self) -> None:
        raw = '{"goal": "use {placeholder} here", "steps": []}'

        assert json.loads(_extract_json(raw))["goal"] == "use {placeholder} here"

    def test_escaped_quote_inside_string(self) -> None:
        raw = r'{"goal": "say \"hi\"", "steps": []}'

        assert json.loads(_extract_json(raw))["goal"] == 'say "hi"'

    def test_nested_objects(self) -> None:
        raw = 'Plan: {"a": {"b": {"c": 1}}}'

        assert json.loads(_extract_json(raw))["a"]["b"]["c"] == 1


class TestBalancedObject:
    def test_returns_none_without_an_object(self) -> None:
        assert _balanced_object("no json here") is None

    def test_returns_none_for_unclosed_object(self) -> None:
        assert _balanced_object('{"goal": "x"') is None


class TestResolveAgentIds:
    @pytest.fixture
    def planner(self) -> PlannerAgent:
        registry = MagicMock()
        registry.list_agents.return_value = [
            _Agent("document_analysis", ["document"]),
            _Agent("asset_intelligence", ["asset"]),
        ]
        return PlannerAgent(registry=registry, llm_provider=None)

    def test_known_agent_id_is_kept(self, planner: PlannerAgent) -> None:
        steps = [
            ExecutionStep(step_id="s1", description="d", agent_id="asset_intelligence")
        ]

        assert planner._resolve_agent_ids(steps)[0].agent_id == "asset_intelligence"

    def test_hallucinated_agent_id_is_cleared(self, planner: PlannerAgent) -> None:
        """A made-up id must fail at routing, not midway through execution."""
        steps = [ExecutionStep(step_id="s1", description="d", agent_id="safety_agent")]

        assert planner._resolve_agent_ids(steps)[0].agent_id is None

    def test_hallucinated_fallback_id_is_cleared(self, planner: PlannerAgent) -> None:
        steps = [
            ExecutionStep(
                step_id="s1",
                description="d",
                agent_id="asset_intelligence",
                fallback_agent_id="imaginary_agent",
            )
        ]

        assert planner._resolve_agent_ids(steps)[0].fallback_agent_id is None

    def test_null_agent_id_is_left_alone(self, planner: PlannerAgent) -> None:
        steps = [ExecutionStep(step_id="s1", description="d", agent_id=None)]

        assert planner._resolve_agent_ids(steps)[0].agent_id is None


class TestFallbackPlan:
    async def test_picks_the_best_keyword_match_without_an_llm(self) -> None:
        """Without an LLM the planner must still route on topic.

        ``_pick_best_agent`` depends on ``can_handle``; while that always
        returned 0.0 it picked nothing, and every question fell through to
        the orchestrator's hardcoded first choice regardless of subject.
        """
        registry = MagicMock()
        registry.list_agents.return_value = [
            _Agent("document_analysis", ["document", "sop", "procedure"]),
            _Agent("asset_intelligence", ["asset", "equipment", "pump"]),
        ]
        planner = PlannerAgent(registry=registry, llm_provider=None)

        plan = await planner.plan("Tell me about the pump equipment")

        assert plan.steps[0].agent_id == "asset_intelligence"

    async def test_falls_back_when_llm_output_is_unparseable(self) -> None:
        registry = MagicMock()
        registry.list_agents.return_value = [_Agent("document_analysis", ["document"])]
        llm = AsyncMock()
        llm.generate.return_value = "I cannot produce a plan."
        planner = PlannerAgent(registry=registry, llm_provider=llm)

        plan = await planner.plan("something")

        assert plan.steps
        assert "Fallback" in plan.reasoning


class TestAgentListFiltering:
    def test_agents_the_role_cannot_use_are_withheld(self) -> None:
        """Planning around an unusable agent yields a plan that dies partway."""
        from app.core.authorization import Permission

        allowed = _Agent("document_analysis", ["document"])
        restricted = _Agent("admin_agent", ["admin"])
        restricted.required_permissions = {Permission.USER_MANAGEMENT}

        registry = MagicMock()
        registry.list_agents.return_value = [allowed, restricted]
        planner = PlannerAgent(registry=registry, llm_provider=None)

        listed = {a["agent_id"] for a in planner._build_agents_list(user_role="Viewer")}

        assert "document_analysis" in listed
        assert "admin_agent" not in listed

    def test_no_role_lists_everything(self) -> None:
        registry = MagicMock()
        registry.list_agents.return_value = [_Agent("a", ["x"]), _Agent("b", ["y"])]
        planner = PlannerAgent(registry=registry, llm_provider=None)

        assert len(planner._build_agents_list(user_role="")) == 2
