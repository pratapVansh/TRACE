import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.agents.framework.registry import AgentRegistry

if TYPE_CHECKING:
    from app.agents.framework.planner import PlannerAgent

logger = logging.getLogger(__name__)

_ROUTING_RULES: list[tuple[str, str, float]] = [
    ("root cause", "root_cause_analysis", 1.0),
    ("incident", "root_cause_analysis", 0.95),
    ("failure analysis", "root_cause_analysis", 0.95),
    ("corrective action", "root_cause_analysis", 0.85),
    ("evidence", "root_cause_analysis", 0.8),
    ("report", "report_generation", 1.0),
    ("generate report", "report_generation", 1.0),
    ("executive summary", "report_generation", 0.95),
    ("incident report", "report_generation", 0.9),
    ("maintenance report", "report_generation", 0.9),
    ("compliance report", "report_generation", 0.9),
    ("maintenance", "maintenance", 1.0),
    ("preventive", "maintenance", 0.95),
    ("corrective", "maintenance", 0.9),
    ("inspection", "maintenance", 0.85),
    ("spare part", "maintenance", 0.8),
    ("risk assessment", "maintenance", 0.8),
    ("compliance", "compliance", 1.0),
    ("sop", "compliance", 0.95),
    ("regulatory", "compliance", 0.9),
    ("audit", "compliance", 0.85),
    ("non-compliance", "compliance", 0.9),
    ("asset", "asset_intelligence", 1.0),
    ("equipment", "asset_intelligence", 0.95),
    ("pump", "asset_intelligence", 0.95),
    ("valve", "asset_intelligence", 0.95),
    ("motor", "asset_intelligence", 0.9),
    ("compressor", "asset_intelligence", 0.95),
    ("turbine", "asset_intelligence", 0.95),
    ("tank", "asset_intelligence", 0.9),
    ("boiler", "asset_intelligence", 0.9),
    ("generator", "asset_intelligence", 0.9),
    ("heat exchanger", "asset_intelligence", 0.95),
    ("risk profile", "asset_intelligence", 0.85),
    ("document", "document_analysis", 0.9),
    ("explain this", "document_analysis", 0.9),
    ("summarize", "document_analysis", 0.85),
    ("manual", "document_analysis", 0.8),
    ("drawing", "document_analysis", 0.8),
    ("p&id", "document_analysis", 0.85),
    ("graph", "knowledge_graph", 1.0),
    ("relationship", "knowledge_graph", 0.95),
    ("connected", "knowledge_graph", 0.9),
    ("network", "knowledge_graph", 0.85),
    ("find related", "knowledge_graph", 0.95),
    ("related assets", "knowledge_graph", 0.95),
    ("path between", "knowledge_graph", 0.95),
    ("hierarchy", "knowledge_graph", 0.9),
]

_GENERIC_TASK_RULES: list[tuple[str, str, float]] = [
    ("search", "search", 0.9),
    ("find", "search", 0.9),
    ("look up", "search", 0.9),
    ("where", "search", 0.9),
    ("what is", "document_analysis", 0.7),
    ("explain", "document_analysis", 0.8),
    ("summary", "document_analysis", 0.8),
]

_PARALLEL_GROUPS: list[set[str]] = [
    {"maintenance", "compliance"},
    {"document_analysis", "knowledge_graph"},
]

_CHAINS: list[list[str]] = [
    ["root_cause_analysis", "report_generation"],
    ["maintenance", "report_generation"],
    ["compliance", "report_generation"],
]

_EXCLUSIVE_AGENTS: dict[str, list[str]] = {
    "report_generation": ["root_cause_analysis", "maintenance", "compliance"],
}


@dataclass
class RoutingPlan:
    """Result of routing — which agents to invoke and how."""

    primary_agents: list[str] = field(default_factory=list)
    parallel_groups: list[list[str]] = field(default_factory=list)
    chain: list[str] | None = None
    execution_mode: str = "auto"
    routing_confidence: float = 0.0
    fallback_agents: list[str] = field(default_factory=list)


class AgentRouter:
    """Routes questions to the most appropriate agent(s).

    Uses keyword-based intent matching as a fallback, but when a
    ``PlannerAgent`` is provided it delegates to the LLM-powered
    planner for dynamic plan generation.

    The planner produces an ``ExecutionPlan`` which is then converted
    to a ``RoutingPlan`` for backward compatibility with the existing
    ``MultiAgentExecutor``.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        planner: "PlannerAgent | None" = None,
    ) -> None:
        self._registry = registry
        self._planner = planner

    async def route_async(self, question: str, mode: str = "auto") -> RoutingPlan:
        """Analyse a question using the planner (async).

        Uses the ``PlannerAgent`` when available, otherwise falls back
        to the synchronous keyword-based routing.
        """
        if self._planner is not None:
            try:
                plan = await self._planner.plan(question)
                return _plan_to_routing(plan, mode)
            except Exception as exc:
                logger.warning("Planner routing failed, falling back to keywords: %s", exc)

        return self.route(question, mode)

    def route(self, question: str, mode: str = "auto") -> RoutingPlan:
        """Analyse a question and produce a ``RoutingPlan``.

        Args:
            question: The user's question.
            mode:  ``"auto"``, ``"single"``, or ``"multi"``.

        Returns:
            A ``RoutingPlan`` with the agents and execution strategy.
        """
        q = question.lower()
        scores: dict[str, float] = {}

        for keyword, agent_id, score in _ROUTING_RULES:
            if keyword in q:
                scores[agent_id] = max(scores.get(agent_id, 0.0), score)

        if not scores:
            task = self._infer_generic_task(q)
            scores[task] = 0.5

        ordered = sorted(scores.items(), key=lambda x: -x[1])
        primary = [a for a, _ in ordered if self._agent_exists(a)]

        if mode == "single":
            return RoutingPlan(
                primary_agents=primary[:1],
                execution_mode="single",
                routing_confidence=ordered[0][1] if ordered else 0.0,
                fallback_agents=self._find_fallback(primary[:1]),
            )

        if mode == "multi":
            return RoutingPlan(
                primary_agents=primary,
                execution_mode="multi",
                routing_confidence=ordered[0][1] if ordered else 0.0,
                fallback_agents=self._find_fallback(primary),
            )

        chain = self._detect_chain(primary)
        if chain is not None:
            return RoutingPlan(
                primary_agents=chain,
                chain=chain,
                execution_mode="sequential",
                routing_confidence=ordered[0][1] if ordered else 0.0,
                fallback_agents=self._find_fallback(chain),
            )

        pg = self._detect_parallel(primary)
        if pg:
            unique: list[str] = []
            seen: set[str] = set()
            for group in pg:
                for a in group:
                    if a not in seen:
                        unique.append(a)
                        seen.add(a)
            return RoutingPlan(
                primary_agents=unique,
                parallel_groups=pg,
                execution_mode="parallel",
                routing_confidence=ordered[0][1] if ordered else 0.0,
                fallback_agents=self._find_fallback(unique),
            )

        return RoutingPlan(
            primary_agents=primary,
            execution_mode="multi",
            routing_confidence=ordered[0][1] if ordered else 0.0,
            fallback_agents=self._find_fallback(primary),
        )

    def _agent_exists(self, agent_id: str) -> bool:
        try:
            self._registry.get_agent(agent_id)
            return True
        except Exception:
            return False

    def _find_fallback(self, primary: list[str]) -> list[str]:
        primary_set = set(primary)
        fallback: list[str] = []
        for rule_agent, depends_on in _EXCLUSIVE_AGENTS.items():
            if rule_agent not in primary_set:
                for dep in depends_on:
                    if dep in primary_set:
                        fallback.append(rule_agent)
                        break
        return fallback

    @staticmethod
    def _detect_chain(agents: list[str]) -> list[str] | None:
        for chain in _CHAINS:
            if all(a in agents for a in chain):
                return chain
        if "report_generation" in agents and len(agents) > 1:
            non_report = [a for a in agents if a != "report_generation"]
            return non_report + ["report_generation"]
        return None

    @staticmethod
    def _detect_parallel(agents: list[str]) -> list[list[str]]:
        agents_set = set(agents)
        groups: list[list[str]] = []
        for group in _PARALLEL_GROUPS:
            matched = agents_set & group
            if len(matched) >= 2:
                groups.append(list(matched))
        return groups

    def _infer_generic_task(self, q: str) -> str:
        """Map a question that matched no routing rules to the best-fit agent.

        Applies a secondary scored pass over ``_ROUTING_RULES`` so that
        equipment names (pump, valve, motor, …) and intent phrases that
        weren't in the question's *scoring* pass still get routed correctly.
        Falls back to ``document_analysis`` when no rule scores above zero.
        """
        scores: dict[str, float] = {}
        for keyword, agent_id, score in _ROUTING_RULES:
            if keyword in q:
                scores[agent_id] = max(scores.get(agent_id, 0.0), score)

        if scores:
            best = max(scores, key=lambda k: scores[k])
            agent = self._registry.find_agent_for_task(best)
            if agent is not None:
                return agent.agent_id
            # agent_id is already the canonical id — try direct lookup
            try:
                self._registry.get_agent(best)
                return best
            except Exception:
                pass

        # Last resort — document_analysis has widest generic coverage
        return "document_analysis"


def _plan_to_routing(plan: "ExecutionPlan", mode: str = "auto") -> RoutingPlan:
    """Convert an ``ExecutionPlan`` to a ``RoutingPlan``.

    Extracts primary agents from steps, detects chains and parallel
    groups based on dependency structure, and preserves fallback agents.
    """
    # We need to avoid circular import; ExecutionPlan is a pydantic model
    # so we only access string attributes
    from app.agents.framework.planner.schemas import ExecutionPlan as EP

    if not isinstance(plan, EP):
        return RoutingPlan(
            primary_agents=[],
            execution_mode=mode if mode != "auto" else "multi",
        )

    agent_ids: list[str] = []
    for step in plan.steps:
        if step.agent_id and step.agent_id not in agent_ids:
            agent_ids.append(step.agent_id)

    if not agent_ids:
        return RoutingPlan(
            primary_agents=[],
            execution_mode=mode if mode != "auto" else "multi",
        )

    if mode == "single":
        return RoutingPlan(
            primary_agents=agent_ids[:1],
            execution_mode="single",
            fallback_agents=_extract_fallbacks(plan),
        )

    chain = _detect_chain_from_plan(plan, agent_ids)
    if chain is not None:
        return RoutingPlan(
            primary_agents=chain,
            chain=chain,
            execution_mode="sequential",
            fallback_agents=_extract_fallbacks(plan),
        )

    parallel_groups = _detect_parallel_from_plan(plan)
    if parallel_groups:
        unique: list[str] = []
        seen: set[str] = set()
        for group in parallel_groups:
            for a in group:
                if a not in seen:
                    unique.append(a)
                    seen.add(a)
        return RoutingPlan(
            primary_agents=unique,
            parallel_groups=parallel_groups,
            execution_mode="parallel",
            fallback_agents=_extract_fallbacks(plan),
        )

    return RoutingPlan(
        primary_agents=agent_ids,
        execution_mode="multi",
        fallback_agents=_extract_fallbacks(plan),
    )


def _detect_chain_from_plan(plan: "ExecutionPlan", agent_ids: list[str]) -> list[str] | None:
    """Detect a sequential chain from the plan's dependency structure."""
    from app.agents.framework.planner.schemas import ExecutionPlan as EP

    if not isinstance(plan, EP) or len(plan.steps) < 2:
        return None

    has_chain = any(s.depends_on for s in plan.steps)
    if has_chain:
        ordered = _topological_step_order(plan.steps)
        return [s.agent_id for s in ordered if s.agent_id]

    if "report_generation" in agent_ids and len(agent_ids) > 1:
        non_report = [a for a in agent_ids if a != "report_generation"]
        return non_report + ["report_generation"]

    return None


def _detect_parallel_from_plan(plan: "ExecutionPlan") -> list[list[str]]:
    """Detect parallel groups from the plan's parallel_with fields."""
    from app.agents.framework.planner.schemas import ExecutionPlan as EP

    if not isinstance(plan, EP):
        return []

    groups: list[list[str]] = []
    seen_steps: set[str] = set()

    for step in plan.steps:
        if step.step_id in seen_steps or not step.agent_id:
            continue
        if step.parallel_with:
            group = [step.agent_id]
            seen_steps.add(step.step_id)
            for pid in step.parallel_with:
                for s in plan.steps:
                    if s.step_id == pid and s.agent_id and s.step_id not in seen_steps:
                        group.append(s.agent_id)
                        seen_steps.add(s.step_id)
            if len(group) > 1:
                groups.append(group)
        else:
            seen_steps.add(step.step_id)

    return groups


def _topological_step_order(steps: "list[ExecutionStep]") -> "list[ExecutionStep]":
    """Return steps in dependency order."""
    from app.agents.framework.planner.schemas import ExecutionStep

    step_map = {s.step_id: s for s in steps}
    deps: dict[str, set[str]] = {}
    for s in steps:
        deps[s.step_id] = {d for d in s.depends_on if d in step_map and d != s.step_id}

    ordered: list[ExecutionStep] = []
    remaining = set(step_map.keys())

    while remaining:
        current = {sid for sid in remaining if not deps[sid]}
        if not current:
            current = {min(remaining)}
        for sid in sorted(current):
            ordered.append(step_map[sid])
        remaining -= current
        for sid in remaining:
            deps[sid] -= current

    return ordered


def _extract_fallbacks(plan: "ExecutionPlan") -> list[str]:
    """Collect all fallback agent ids from the plan."""
    from app.agents.framework.planner.schemas import ExecutionPlan as EP

    if not isinstance(plan, EP):
        return []
    fallbacks: list[str] = []
    for step in plan.steps:
        if step.fallback_agent_id and step.fallback_agent_id not in fallbacks:
            fallbacks.append(step.fallback_agent_id)
    return fallbacks
