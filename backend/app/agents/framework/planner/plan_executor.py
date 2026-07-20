import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import LLMProvider
from app.agents.framework.base import check_agent_permissions
from app.agents.framework.context import AgentContext
from app.agents.framework.exceptions import OrchestrationError
from app.agents.framework.factory import AgentFactory
from app.agents.framework.memory.manager import MemoryManager
from app.agents.framework.planner.schemas import ExecutionPlan, ExecutionStep
from app.agents.framework.registry import AgentRegistry
from app.agents.framework.evidence_classifier import (
    classify_statements,
    limit_citations,
)
from app.agents.framework.formatter import ResponseFormatter
from app.agents.framework.response import AgentResponse
from app.agents.framework.workflow.schemas import MultiAgentResponse, TimelineEntry

logger = logging.getLogger(__name__)


class PlanExecutor:
    """Executes an ``ExecutionPlan`` DAG against the agent framework.

    Walks the plan in topological order, runs independent steps in
    parallel, dependent steps sequentially, handles retries and
    fallbacks.

    **Collaboration**: before each step, execution history and messages
    from prior agents are injected into ``AgentContext.metadata`` so
    agents can read, challenge, or build on previous work.

    **Synthesis**: after all DAG steps complete, a ``SynthesisAgent``
    (LLM-based) merges all agent outputs into one coherent answer
    instead of concatenating them.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        factory: AgentFactory,
        memory_manager: MemoryManager | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self._registry = registry
        self._factory = factory
        self._memory_manager = memory_manager
        self._llm = llm_provider

    from collections.abc import Callable, Awaitable

    async def execute(
        self,
        plan: ExecutionPlan,
        question: str,
        user_id: str,
        user_role: str,
        conversation_id: str | None = None,
        session: AsyncSession | None = None,
        memory_manager: MemoryManager | None = None,
        event_callback: Callable[[str, Any], Awaitable[None]] | None = None,
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> MultiAgentResponse:
        """Execute an ``ExecutionPlan`` and return the combined response.

        Args:
            plan: The plan to execute.
            question: The original user question.
            user_id: Authenticated user id.
            user_role: Authenticated user role.
            conversation_id: Optional conversation id.
            session: Optional DB session.
            memory_manager: Optional MemoryManager.

        Returns:
            A ``MultiAgentResponse`` with synthesised results.
        """
        start = time.perf_counter()
        mgr = memory_manager or self._memory_manager

        context = AgentContext(
            user_id=user_id,
            user_role=user_role,
            conversation_id=conversation_id,
            question=question,
            session=session,
            metadata={"step_outputs": {}, "plan_goal": plan.goal, "plan_reasoning": plan.reasoning},
        )

        if mgr is not None:
            await mgr.load_conversation(
                conversation_id=conversation_id,
                user_id=user_id,
            )
            await mgr.init_working(task=question)
            await mgr.retrieve_relevant(query=question, user_id=user_id, limit=10)
            mgr.merge_into(context)

        levels = _topological_sort(plan.steps)
        timeline: list[TimelineEntry] = []
        all_results: list[AgentResponse] = []

        for level_idx, level in enumerate(levels):
            step_map = {s.step_id: s for s in plan.steps}
            level_steps = [step_map[sid] for sid in level]

            if len(level_steps) == 1:
                result = await self._execute_step(
                    level_steps[0], context, start, timeline, level_idx, event_callback
                )
                if result is not None:
                    all_results.append(result)
            else:
                results = await asyncio.gather(*[
                    self._execute_step(step, context, start, timeline, level_idx, event_callback)
                    for step in level_steps
                ])
                for r in results:
                    if r is not None:
                        all_results.append(r)

        result = await self._synthesize_and_build_response(
            all_results, timeline, plan, start, question, context, event_callback, stream_callback
        )

        if mgr is not None:
            await mgr.save_conversation_turn("user", question)
            await mgr.save_conversation_turn(
                "assistant", result.answer,
                citations=[c.model_dump() for c in result.citations],
            )
            if mgr.conversation is not None:
                cid = mgr.conversation.conversation_id
                result.conversation_id = str(cid) if cid is not None else None
            try:
                conversation_text = f"User: {question}\nAssistant: {result.answer}"
                await mgr.consolidate(
                    conversation_text=conversation_text,
                    user_id=user_id,
                    conversation_id=conversation_id,
                )
            except Exception:
                logger.warning("Memory consolidation failed (non-fatal)", exc_info=True)

        return result

    async def _execute_step(
        self,
        step: ExecutionStep,
        context: AgentContext,
        start: float,
        timeline: list[TimelineEntry],
        level_index: int = 0,
        event_callback: Callable[[str, Any], Awaitable[None]] | None = None,
    ) -> AgentResponse | None:
        agent_id = step.agent_id
        if agent_id is None:
            return None

        entry_start = time.perf_counter()
        entry = TimelineEntry(
            agent_id=agent_id,
            agent_name=agent_id,
            start_time=entry_start - start,
            end_time=0.0,
        )

        agent = self._get_agent(agent_id, context.user_role)
        entry.agent_name = agent.name

        last_error: Exception | None = None
        max_attempts = step.max_retries + 1 if step.retry_on_failure else 1

        for attempt in range(max_attempts):
            try:
                if event_callback:
                    await event_callback("agent_start", {"agent_id": agent_id, "agent_name": agent.name})
                enriched = await agent.prepare_context(context)
                result = await agent.execute(enriched)
                result.agent_name = agent.name
                result.execution_time = time.perf_counter() - entry_start
                entry.end_time = time.perf_counter() - start
                entry.duration = entry.end_time - entry.start_time
                entry.confidence = result.confidence
                entry.tools_used = result.tools_used
                entry.status = "success"

                _pass_step_output(context, step, result)

                self._capture_execution_snapshot(context, step, agent, result)
                timeline.append(entry)
                if event_callback:
                    await event_callback("agent_end", entry.model_dump())
                return result
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Plan step %s (%s) attempt %d/%d failed: %s",
                    step.step_id, agent_id, attempt + 1, max_attempts, exc,
                )
                if attempt < max_attempts - 1:
                    await asyncio.sleep(0.5)

        if step.fallback_agent_id is not None:
            if event_callback:
                await event_callback("agent_failed", {"agent_id": agent_id, "error": str(last_error)})
            fallback_result = await self._try_fallback(
                step.fallback_agent_id, context, start, timeline, event_callback
            )
            if fallback_result is not None:
                entry.status = "fallback_success"
                entry.end_time = time.perf_counter() - start
                entry.duration = entry.end_time - entry.start_time
                return fallback_result

        entry.end_time = time.perf_counter() - start
        entry.duration = entry.end_time - entry.start_time
        entry.status = "error"
        timeline.append(entry)
        if event_callback:
            await event_callback("agent_failed", entry.model_dump())

        return AgentResponse(
            answer=f"Step '{step.step_id}' ({agent_id}) failed after {max_attempts} attempt(s): {last_error}",
            agent_name=agent.name if agent else agent_id,
            confidence=0.0,
        )

    def _capture_execution_snapshot(
        self,
        context: AgentContext,
        step: ExecutionStep,
        agent: Any,
        result: AgentResponse,
    ) -> None:
        """Record the agent's output in WorkingMemory for downstream agents."""
        wm = context.working_memory
        if wm is None:
            return

        msg_types = [m.message_type for m in wm.get_messages_for_agent(agent.agent_id)]

        snapshot = {
            "agent_id": agent.agent_id,
            "agent_name": agent.name,
            "step_id": step.step_id,
            "answer": result.answer,
            "reasoning": result.reasoning,
            "confidence": result.confidence,
            "tools_used": list(result.tools_used),
            "messages_posted": msg_types,
        }
        wm.add_execution_snapshot(snapshot)

    async def _try_fallback(
        self,
        fallback_agent_id: str,
        context: AgentContext,
        start: float,
        timeline: list[TimelineEntry],
        event_callback: Callable[[str, Any], Awaitable[None]] | None = None,
    ) -> AgentResponse | None:
        try:
            fb_agent = self._get_agent(fallback_agent_id, context.user_role)
            entry_start = time.perf_counter()
            entry = TimelineEntry(
                agent_id=fb_agent.agent_id,
                agent_name=fb_agent.name,
                start_time=entry_start - start,
                end_time=0.0,
                status="fallback",
            )
            if event_callback:
                await event_callback("agent_start", {"agent_id": fb_agent.agent_id, "agent_name": fb_agent.name})
            enriched = await fb_agent.prepare_context(context)
            fb_result = await fb_agent.execute(enriched)
            fb_result.agent_name = fb_agent.name
            fb_result.execution_time = time.perf_counter() - entry_start
            entry.end_time = time.perf_counter() - start
            entry.duration = entry.end_time - entry.start_time
            entry.confidence = fb_result.confidence
            entry.tools_used = fb_result.tools_used
            entry.status = "success"
            timeline.append(entry)
            if event_callback:
                await event_callback("agent_end", entry.model_dump())

            self._capture_execution_snapshot(context, ExecutionStep(
                step_id="fallback", description="", agent_id=fallback_agent_id,
            ), fb_agent, fb_result)
            return fb_result
        except Exception as exc:
            logger.warning("Fallback %s failed: %s", fallback_agent_id, exc)
        return None

    def _get_agent(self, agent_id: str, user_role: str = ""):
        agent = self._registry.get_agent(agent_id)
        err = check_agent_permissions(agent, user_role)
        if err is not None:
            raise OrchestrationError(err)
        return agent

    async def _synthesize_and_build_response(
        self,
        results: list[AgentResponse],
        timeline: list[TimelineEntry],
        plan: ExecutionPlan,
        start: float,
        question: str,
        context: AgentContext | None = None,
        event_callback: Callable[[str, Any], Awaitable[None]] | None = None,
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> MultiAgentResponse:
        """Build the final response, optionally using LLM synthesis."""
        execution_order = _collect_order(results)
        all_tools = _collect_tools(results)
        citations, graph_citations = _dedup_citations(results)
        confidences = [r.confidence for r in results if r.confidence > 0]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        weighted_conf = max(avg_conf, max(confidences) if confidences else 0.0)

        if not results:
            return MultiAgentResponse(
                answer="No agents could process this request.",
                execution_order=[s.agent_id for s in plan.steps if s.agent_id],
                timeline=timeline,
            )

        # ── Build accumulated context from conversation ──────────────
        conversation_summary, previous_findings, accumulated_evidence = \
            _build_accumulated_context(context)

        if self._llm is not None and len(results) > 1:
            try:
                from app.agents.framework.collaboration import SynthesisAgent

                synth = SynthesisAgent(self._llm)
                execution_history = None
                if results and hasattr(results[0], "_execution_history"):
                    pass  # use from working memory

                if event_callback:
                    await event_callback("agent_start", {"agent_id": "synthesis", "agent_name": "Synthesis Agent"})

                synth_result = await synth.synthesize(
                    question=question,
                    agent_results=results,
                    stream_callback=stream_callback,
                    conversation_summary=conversation_summary,
                    previous_findings=previous_findings,
                    accumulated_evidence=accumulated_evidence,
                )

                if event_callback:
                    # We can't dump synth_result directly as a TimelineEntry because it's an AgentResponse,
                    # but we can synthesize a timeline entry for the UI.
                    synth_duration = time.perf_counter() - start # approximation
                    await event_callback("agent_end", {
                        "agent_id": "synthesis", "agent_name": "Synthesis Agent", 
                        "start_time": 0, "end_time": synth_duration, "duration": synth_duration, 
                        "status": "success", "confidence": synth_result.confidence
                    })

                # Evidence-first: limit to top 3 citations
                limited_citations = limit_citations(citations, max_count=3)
                # Classify statements in the synthesised answer
                classified = classify_statements(synth_result.answer, limited_citations)

                # Apply response formatter (concise, structured, no fluff)
                formatter = ResponseFormatter()
                formatted_answer = formatter.format(
                    answer=synth_result.answer,
                    citations=limited_citations,
                    confidence=synth_result.confidence,
                    question=question,
                )

                return MultiAgentResponse(
                    answer=formatted_answer,
                    agent_results=results,
                    citations=limited_citations,
                    graph_citations=graph_citations,
                    confidence=synth_result.confidence,
                    confidence_explanation=synth_result.confidence_explanation,
                    reasoning=synth_result.reasoning,
                    execution_time=time.perf_counter() - start,
                    execution_order=execution_order,
                    timeline=timeline,
                    all_tools_used=sorted(all_tools),
                )
            except Exception as exc:
                logger.warning("LLM synthesis failed, falling back to merge: %s", exc)

        combined_answer = _combine_answers(
            [r.answer for r in results if r.answer and r.confidence > 0],
            confidences,
        )

        # Evidence-first: limit to top 3 citations
        limited_citations = limit_citations(citations, max_count=3)
        return MultiAgentResponse(
            answer=combined_answer,
            agent_results=results,
            citations=limited_citations,
            graph_citations=graph_citations,
            confidence=weighted_conf,
            execution_time=time.perf_counter() - start,
            execution_order=execution_order,
            timeline=timeline,
            all_tools_used=sorted(all_tools),
        )


def _topological_sort(steps: list[ExecutionStep]) -> list[list[str]]:
    """Return levels of step_ids in dependency order.

    Each level is a list of step_ids that can execute in parallel.
    Level 0 has no dependencies, level 1 depends on level 0, etc.
    """
    step_ids = {s.step_id for s in steps}
    deps: dict[str, set[str]] = {}
    for s in steps:
        deps[s.step_id] = {
            d for d in s.depends_on
            if d in step_ids and d != s.step_id
        }

    levels: list[list[str]] = []
    remaining = set(step_ids)

    while remaining:
        current = {sid for sid in remaining if not deps[sid]}
        if not current:
            logger.warning(
                "Circular dependency detected among: %s",
                remaining,
            )
            current = {min(remaining)}
        levels.append(sorted(current))
        remaining -= current
        for sid in remaining:
            deps[sid] -= current

    return levels


def _pass_step_output(
    context: AgentContext,
    step: ExecutionStep,
    result: AgentResponse,
) -> None:
    if not step.output_key:
        return
    outputs = context.metadata.setdefault("step_outputs", {})
    outputs[step.output_key] = {
        "answer": result.answer,
        "confidence": result.confidence,
        "citations": [c.model_dump() for c in result.citations],
        "agent_id": step.agent_id,
    }


def _combine_answers(answers: list[str], confidences: list[float]) -> str:
    if not answers:
        return ""
    if len(answers) == 1:
        return answers[0]

    parts: list[str] = []
    for i, (ans, conf) in enumerate(zip(answers, confidences)):
        prefix = f"--- Agent {i + 1} ---" if len(answers) > 1 else ""
        if prefix:
            parts.append(prefix)
        parts.append(ans)

    return "\n\n".join(parts)


def _collect_order(results: list[AgentResponse]) -> list[str]:
    seen: set[str] = set()
    order: list[str] = []
    for r in results:
        if r.agent_name and r.agent_name not in seen:
            seen.add(r.agent_name)
            order.append(r.agent_name)
    return order


def _collect_tools(results: list[AgentResponse]) -> set[str]:
    tools: set[str] = set()
    for r in results:
        if r.tools_used:
            tools.update(r.tools_used)
    return tools


def _dedup_citations(
    results: list[AgentResponse],
) -> tuple[list[Any], list[Any]]:
    from app.schemas.rag import Citation, GraphCitation

    seen_c: set[str] = set()
    combined_c: list[Citation] = []
    seen_g: set[str] = set()
    combined_g: list[GraphCitation] = []

    for r in results:
        for c in r.citations:
            key = f"{c.document_name}:{c.page_number}:{c.chunk_content}"
            if key not in seen_c:
                seen_c.add(key)
                combined_c.append(c)
        for gc in r.graph_citations:
            key = f"{gc.entity_name}:{gc.relationship_type}:{gc.related_entity}"
            if key not in seen_g:
                seen_g.add(key)
                combined_g.append(gc)

    return combined_c, combined_g


def _trunc(text: str, max_chars: int = 400) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


_MAX_CONTEXT_CHARS = 8000  # total accumulated context budget


def _build_accumulated_context(
    context: AgentContext | None,
) -> tuple[str, str, str]:
    """Extract conversation summary, previous findings and accumulated evidence from the agent context.

    Returns:
        A ``(conversation_summary, previous_findings, accumulated_evidence)``
        tuple. Each is an empty string if nothing is available.
    """
    if context is None:
        return ("", "", "")

    budget = _MAX_CONTEXT_CHARS

    # ── Conversation summary ─────────────────────────────────
    conv_lines: list[str] = []
    if context.chat_history:
        conv_lines.append(f"Total messages in conversation: {len(context.chat_history)}")
        for msg in context.chat_history:
            role = msg.get("role", "unknown")
            content = _trunc(msg.get("content", ""), 300)
            conv_lines.append(f"- **{role}**: {content}")
    conversation_summary = "\n".join(conv_lines)
    if len(conversation_summary) > budget // 3:
        conversation_summary = _trunc(conversation_summary, budget // 3)

    # ── Previous findings (working memory snapshots + step outputs) ──
    findings_lines: list[str] = []

    # From working memory execution history
    if context.working_memory is not None:
        snapshots = context.working_memory.execution_history
        if snapshots:
            findings_lines.append(f"### Execution Snapshots ({len(snapshots)})\n")
            for snap in snapshots[:5]:  # max 5 snapshots
                agent = snap.get("agent_name", snap.get("agent_id", "?"))
                answer = _trunc(snap.get("answer", ""), 300)
                reasoning = _trunc(snap.get("reasoning", ""), 200)
                conf = snap.get("confidence", 0.0)
                findings_lines.append(f"- **{agent}** (confidence={conf:.2f})")
                if reasoning:
                    findings_lines.append(f"  Reasoning: {reasoning}")
                if answer:
                    findings_lines.append(f"  Findings: {answer}")
            findings_lines.append("")

    # From step_outputs in metadata
    step_outputs = context.metadata.get("step_outputs", {})
    if step_outputs:
        findings_lines.append(f"### Prior Step Outputs ({len(step_outputs)})\n")
        for key, output in step_outputs.items():
            agent_id = output.get("agent_id", key)
            answer = _trunc(output.get("answer", ""), 300)
            conf = output.get("confidence", 0.0)
            findings_lines.append(f"- **{agent_id}** (confidence={conf:.2f}): {answer}")
        findings_lines.append("")

    previous_findings = "\n".join(findings_lines)
    if len(previous_findings) > budget // 3:
        previous_findings = _trunc(previous_findings, budget // 3)

    # ── Accumulated evidence ─────────────────────────────────
    evidence_lines: list[str] = []

    if context.retrieved_documents:
        evidence_lines.append(f"### Retrieved Documents ({len(context.retrieved_documents)})\n")
        for i, doc in enumerate(context.retrieved_documents[:5]):  # max 5 docs
            content = _trunc(doc.content if hasattr(doc, "content") else str(doc), 250)
            score = getattr(doc, "score", doc.get("score", 0.0)) if isinstance(doc, dict) else getattr(doc, "score", 0.0)
            source = getattr(doc, "source", doc.get("source", "?")) if isinstance(doc, dict) else getattr(doc, "source", "?")
            evidence_lines.append(f"{i+1}. [{source}] (score={score:.2f}): {content}")
        evidence_lines.append("")

    if context.graph_facts:
        evidence_lines.append(f"### Graph Facts ({len(context.graph_facts)})\n")
        for fact in context.graph_facts[:5]:  # max 5 facts
            evidence_lines.append(
                f"- **{fact.entity_name}** --[{fact.relationship_type}]--> "
                f"**{fact.related_entity}**"
            )
        evidence_lines.append("")

    accumulated_evidence = "\n".join(evidence_lines)
    if len(accumulated_evidence) > budget // 3:
        accumulated_evidence = _trunc(accumulated_evidence, budget // 3)

    return (conversation_summary, previous_findings, accumulated_evidence)
