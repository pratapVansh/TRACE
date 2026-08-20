import json
import logging
import re
from typing import Any

from app.ai.base import LLMProvider
from app.agents.framework.base import BaseAgent, check_agent_permissions
from app.agents.framework.planner.schemas import ExecutionPlan, ExecutionStep
from app.agents.framework.registry import AgentRegistry

logger = logging.getLogger(__name__)

# Matches a fenced block anywhere in the response, with or without a
# language tag.
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

_SYSTEM_PROMPT = """You are a planning agent for an industrial asset management system.
Your job is to analyse user requests and create an execution plan — a DAG of steps
that breaks the goal into discrete subtasks, assigns the right agent to each step,
and determines dependencies and parallelisation.

Available agents and their capabilities are provided below.

Rules:
1. Break the user's request into logical steps (1–6 steps typically).
2. For each step, assign the most capable agent. Use agent_id exactly as provided.
3. Set depends_on to list step_ids that must complete before this step.
4. Set parallel_with when two steps are independent and can run concurrently.
5. When a report is needed after analysis, chain: analyse → report.
6. Always include a reasoning field explaining why you chose this plan.
7. Estimate complexity: "simple" (1 agent), "moderate" (2-3 agents, some chain),
   or "complex" (4+ agents, parallel groups).
8. Set requires_supervision to true for high-risk actions (e.g. safety decisions).

You MUST respond with ONLY valid JSON matching this schema:
{
  "goal": "string — restate the user's goal",
  "steps": [
    {
      "step_id": "string — unique id like 'step_1'",
      "description": "string — what this step does",
      "agent_id": "string | null — agent to invoke, or null for LLM-only",
      "depends_on": ["step_id", ...],
      "parallel_with": ["step_id", ...],
      "retry_on_failure": true,
      "max_retries": 1,
      "fallback_agent_id": "string | null",
      "required_data": ["what data this step needs from earlier steps"],
      "output_key": "string — key to store result under",
      "llm_prompt_template": "string | null — custom prompt for this step"
    }
  ],
  "reasoning": "string — why this plan was chosen",
  "estimated_complexity": "simple|moderate|complex",
  "requires_supervision": false
}"""


class PlannerAgent:
    """LLM-powered planner that produces ``ExecutionPlan`` DAGs.

    Analyses the user question together with the registry of available
    agents, then uses the LLM to produce a structured plan with
    dependency ordering, parallelisation, retry, and fallback.

    Falls back to a simple single-agent plan when the LLM is
    unavailable.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self._registry = registry
        self._llm = llm_provider

    async def plan(
        self,
        question: str,
        user_role: str = "",
        context_hints: dict[str, Any] | None = None,
    ) -> ExecutionPlan:
        """Analyse *question* and return an ``ExecutionPlan``.

        Args:
            question: The user's question.
            user_role: Role for permission filtering.
            context_hints: Optional metadata (conversation history, etc.).

        Returns:
            An ``ExecutionPlan`` with goal, steps, and reasoning.
        """
        if self._llm is None:
            return self._fallback_plan(question)

        agents_info = self._build_agents_list(user_role)
        prompt = self._build_prompt(question, agents_info, context_hints)

        try:
            raw = await self._llm.generate(
                prompt=prompt,
                system_prompt=_SYSTEM_PROMPT,
                temperature=0.2,
                max_tokens=2048,
            )
            return self._parse_response(raw, question)
        except Exception as exc:
            logger.warning("PlannerAgent LLM call failed: %s", exc)
            return self._fallback_plan(question)

    def _build_agents_list(self, user_role: str = "") -> list[dict[str, Any]]:
        """List the agents the planner may choose from.

        Agents the caller lacks permission for are withheld rather than
        offered and rejected later: planning around an agent the user cannot
        run produces a plan that dies partway through instead of a working
        plan built from what they can actually use.
        """
        agents = []
        for agent in self._registry.list_agents():
            if user_role and check_agent_permissions(agent, user_role) is not None:
                continue
            agents.append({
                "agent_id": agent.agent_id,
                "name": agent.name,
                "description": agent.description,
                "supported_tasks": agent.supported_tasks,
                "required_permissions": [p.value for p in agent.required_permissions],
            })
        return agents

    def _build_prompt(
        self,
        question: str,
        agents_info: list[dict[str, Any]],
        context_hints: dict[str, Any] | None = None,
    ) -> str:
        lines = [f"User request: {question}", ""]
        lines.append("Available agents:")
        lines.append(json.dumps(agents_info, indent=2))
        lines.append("")

        if context_hints:
            lines.append("Context hints:")
            lines.append(json.dumps(context_hints, indent=2))
            lines.append("")

        lines.append("Produce an ExecutionPlan JSON that best satisfies the request.")
        return "\n".join(lines)

    def _parse_response(self, raw: str, question: str) -> ExecutionPlan:
        cleaned = _extract_json(raw)
        data = json.loads(cleaned)
        steps = [ExecutionStep(**s) for s in data.get("steps", [])]
        steps = self._resolve_agent_ids(steps)
        return ExecutionPlan(
            goal=data.get("goal", question),
            steps=steps,
            reasoning=data.get("reasoning", ""),
            estimated_complexity=data.get("estimated_complexity", "moderate"),
            requires_supervision=data.get("requires_supervision", False),
        )

    def _resolve_agent_ids(self, steps: list[ExecutionStep]) -> list[ExecutionStep]:
        """Drop agent ids the LLM invented so they fail routing, not execution.

        Nothing constrained the planner's ``agent_id`` to the registry, so a
        plausible-looking hallucination ("safety_agent") reached the executor
        and only failed once that step ran — after the steps before it had
        already done their work. Clearing the id here lets the step fall back
        to normal selection instead.
        """
        known = {agent.agent_id for agent in self._registry.list_agents()}
        for step in steps:
            if step.agent_id is not None and step.agent_id not in known:
                logger.warning(
                    "Planner proposed unknown agent_id %r for step %s — "
                    "clearing it so the step falls back to agent selection",
                    step.agent_id,
                    step.step_id,
                )
                step.agent_id = None
            if step.fallback_agent_id is not None and step.fallback_agent_id not in known:
                step.fallback_agent_id = None
        return steps

    def _fallback_plan(self, question: str) -> ExecutionPlan:
        """Produce a safe single-agent plan when LLM is unavailable."""
        agent = self._pick_best_agent(question)
        step = ExecutionStep(
            step_id="step_1",
            description=f"Analyse: {question[:120]}",
            agent_id=agent.agent_id if agent else None,
            output_key="final_answer",
        )
        return ExecutionPlan(
            goal=question,
            steps=[step],
            reasoning="Fallback: LLM unavailable, used best keyword match.",
            estimated_complexity="simple",
        )

    def _pick_best_agent(self, question: str) -> BaseAgent | None:
        best: BaseAgent | None = None
        best_score = 0.0
        for agent in self._registry.list_agents():
            score = agent.can_handle(question)
            if score > best_score:
                best_score = score
                best = agent
        return best


def _extract_json(text: str) -> str:
    """Pull a JSON object out of LLM output.

    Models routinely wrap the object in a markdown fence and introduce it
    with a sentence ("Here is the plan:"). The previous implementation only
    unwrapped a fence when it was the very first thing in the response, so
    any preamble made ``json.loads`` fail and quietly collapsed a full
    multi-agent plan into the single-agent fallback.

    A fenced block is preferred when present; otherwise the first balanced
    ``{...}`` span is taken, ignoring braces inside strings.
    """
    text = text.strip()

    fenced = _FENCE_RE.search(text)
    if fenced:
        candidate = fenced.group(1).strip()
        if candidate:
            return candidate

    span = _balanced_object(text)
    return span if span is not None else text


def _balanced_object(text: str) -> str | None:
    """Return the first complete ``{...}`` span, or ``None`` if there is none.

    Brace counting is string-aware: a ``{`` or ``}`` inside a JSON string
    value (a description, a prompt template) must not change the depth, or
    the span closes early and yields invalid JSON.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False

    for i in range(start, len(text)):
        char = text[i]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return None
