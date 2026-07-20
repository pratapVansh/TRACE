from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import LLMProvider
from app.agents.framework.base import BaseAgent, check_agent_permissions
from app.agents.framework.context import AgentContext
from app.agents.framework.exceptions import (
    AgentNotFoundError,
    InvalidContextError,
    OrchestrationError,
)
from app.agents.framework.factory import AgentFactory
from app.agents.framework.memory.manager import MemoryManager
from app.core.observability import metrics, get_tracer, trace_span
from app.agents.framework.planner import ExecutionPlan, PlannerAgent
from app.agents.framework.registry import AgentRegistry
from app.agents.framework.critique import SelfCritique
from app.agents.framework.evidence_classifier import (
    build_evidence_summary,
    classify_statements,
    contains_forbidden_content,
    limit_citations,
)
from app.agents.framework.formatter import ResponseFormatter
from app.agents.framework.response import AgentResponse
from app.schemas.hybrid import GraphFact, UnifiedContextItem

if TYPE_CHECKING:
    from app.agents.framework.workflow.schemas import MultiAgentResponse

logger = logging.getLogger(__name__)

_CONFIDENCE_REVISION_THRESHOLD = 0.5


class AIOrchestrator:
    """Unified orchestrator for single and multi-agent workflows.

    Responsibilities:
    - single-agent execution (``execute`` / ``stream``)
    - multi-agent planning, chaining, parallel execution, and fallback
      (``execute_multi``)
    - shared memory, context passing, citation deduplication, and
      confidence aggregation
    - **Long-term memory retrieval** before execution
    - **Long-term memory consolidation** after execution

    The orchestrator delegates multi-agent workflows to an internal
    ``MultiAgentExecutor`` which uses ``AgentRouter`` for automatic
    agent selection and routing.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        factory: AgentFactory,
        llm_provider: LLMProvider | None = None,
        memory_manager: MemoryManager | None = None,
        multi_executor: Any | None = None,
        planner: PlannerAgent | None = None,
    ) -> None:
        self._registry = registry
        self._factory = factory
        self._llm = llm_provider
        self._memory_manager = memory_manager
        self._multi_executor = multi_executor
        self._planner = planner or PlannerAgent(registry, llm_provider)

    # ── Public API ─────────────────────────────────────────────

    async def execute(
        self,
        question: str,
        user_id: str,
        user_role: str,
        conversation_id: str | None = None,
        agent_id: str | None = None,
        session: AsyncSession | None = None,
        memory_manager: MemoryManager | None = None,
    ) -> AgentResponse:
        """Route a question to the appropriate agent and return its response.

        Args:
            question: The user's question.
            user_id: Authenticated user id.
            user_role: Authenticated user role name.
            conversation_id: Optional existing conversation id.
            agent_id: Optional explicit agent selection.  When omitted
                the registry's ``find_agent_for_task`` is used.
            session: Optional database session.
            memory_manager: Optional ``MemoryManager``.  Falls back to
                the one passed at construction time.

        Returns:
            An ``AgentResponse`` with answer, citations, and metadata.
        """
        start = time.perf_counter()
        mgr = memory_manager or self._memory_manager
        tracer = get_tracer("orchestrator")

        context = await self._build_context(
            question=question,
            user_id=user_id,
            user_role=user_role,
            conversation_id=conversation_id,
            session=session,
            memory_manager=mgr,
        )

        agent = self._select_agent(question, agent_id, user_role=user_role)
        metrics.increment(f"agent.{agent.agent_id}.invocations")

        # Let the agent enrich the context before execution
        enriched = await agent.prepare_context(context)

        with trace_span(tracer, f"agent.{agent.agent_id}.execute", {
            "agent_id": agent.agent_id,
            "question": question[:120],
        }):
            result = await agent.execute(enriched)

        # ── Record observability metrics ────────────────────────
        elapsed = time.perf_counter() - start
        metrics.record_histogram(f"agent.{agent.agent_id}.time", elapsed)
        metrics.record_histogram("agent.execution.time", elapsed)
        metrics.record_histogram("confidence.score", result.confidence)
        metrics.increment("answer.total")
        metrics.increment(f"citations.total", len(result.citations))
        if result.reasoning:
            metrics.record_histogram("reasoning.length", len(result.reasoning))

        # ── Evidence-first post-processing: classify statements, limit citations ─
        result.citations = limit_citations(result.citations, max_count=3)
        result.classified_statements = classify_statements(
            result.answer, result.citations
        )
        result.evidence_summary = build_evidence_summary(
            result.answer, result.citations
        )
        if contains_forbidden_content(result.answer):
            logger.warning(
                "Forbidden content detected in answer from %s, appending notice",
                agent.agent_id,
            )
            result.answer += (
                "\n\n> [!WARNING]\n> This answer may contain unsupported claims. "
                "Please verify all maintenance history, part numbers, failure causes, "
                "and schedules against original documentation."
            )

        # ── Self-critique: verify evidence, detect hallucinations, revise ─
        if self._llm is not None:
            try:
                critique = SelfCritique(self._llm)
                cr = await critique.critique(
                    question=enriched.question,
                    answer=result.answer,
                    citations=result.citations,
                    graph_citations=result.graph_citations,
                    confidence=result.confidence,
                    confidence_explanation=result.confidence_explanation,
                    tools_used=result.tools_used,
                )
                if cr.reasoning_report:
                    # Store internal reasoning report (not shown to user)
                    result.reasoning = cr.reasoning_report

                # Adjust confidence
                adj = result.confidence + cr.confidence_adjustment
                result.confidence = max(0.0, min(1.0, adj))

                # Auto-revise if confidence below threshold
                needs_revision = (
                    result.confidence < _CONFIDENCE_REVISION_THRESHOLD
                    or bool(cr.hallucinations)
                    or bool(cr.revised_answer)
                )
                if needs_revision:
                    if cr.revised_answer:
                        logger.info(
                            "SelfCritique: revising answer for %r (conf=%.2f, issues=%d)",
                            enriched.question[:60],
                            result.confidence,
                            len(cr.issues),
                        )
                        result.answer = cr.revised_answer
                    elif result.confidence < _CONFIDENCE_REVISION_THRESHOLD:
                        result.answer = (
                            f"{result.answer}\n\n---\n"
                            f"*Note: This answer has low confidence ({result.confidence:.2f}). "
                            f"The critique identified the following issues: "
                            f"{'; '.join(cr.issues[:3]) if cr.issues else 'insufficient evidence'}.*"
                        )

                # ── Record hallucination / critique metrics ────
                if cr.hallucinations:
                    metrics.increment("hallucination.flagged", len(cr.hallucinations))
                if cr.issues:
                    metrics.increment("critique.issues", len(cr.issues))
            except Exception:
                logger.warning("SelfCritique failed (non-fatal)", exc_info=True)

        # ── Apply response formatter (concise, structured, no fluff) ──
        formatter = ResponseFormatter()
        result.answer = formatter.format(
            answer=result.answer,
            citations=result.citations,
            confidence=result.confidence,
            question=question,
        )

        # Persist conversation turns
        mgr_exec = memory_manager or self._memory_manager
        if mgr_exec is not None:
            await mgr_exec.save_conversation_turn("user", question)
            await mgr_exec.save_conversation_turn(
                "assistant", result.answer,
                citations=[c.model_dump() for c in result.citations],
            )
            if mgr_exec.conversation is not None:
                cid = mgr_exec.conversation.conversation_id
                result.conversation_id = str(cid) if cid is not None else None

            # Long-term memory consolidation
            await self._consolidate_memories(
                mgr_exec, question, result.answer, user_id, conversation_id,
            )

        logger.info(
            "Orchestrator: agent=%s question=%r confidence=%.3f "
            "tools=%s elapsed=%.3fs",
            agent.agent_id,
            question,
            result.confidence,
            result.tools_used,
            elapsed,
        )

        result.execution_time = elapsed
        result.agent_name = agent.name
        return result

    async def stream(
        self,
        question: str,
        user_id: str,
        user_role: str,
        conversation_id: str | None = None,
        agent_id: str | None = None,
        session: AsyncSession | None = None,
        memory_manager: MemoryManager | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream an agent's response token-by-token (future).

        Placeholder for SSE-based streaming support.  Will be
        implemented when agents produce streaming responses.
        """
        result = await self.execute(
            question=question,
            user_id=user_id,
            user_role=user_role,
            conversation_id=conversation_id,
            agent_id=agent_id,
            session=session,
            memory_manager=memory_manager,
        )
        yield result.answer

    # ── Multi-agent public API ─────────────────────────────────

    async def execute_multi(
        self,
        question: str,
        user_id: str,
        user_role: str,
        conversation_id: str | None = None,
        agent_ids: list[str] | None = None,
        mode: str = "auto",
        session: AsyncSession | None = None,
        memory_manager: MemoryManager | None = None,
    ) -> "MultiAgentResponse":
        """Execute a multi-agent workflow.

        Uses the ``PlannerAgent`` for dynamic plan generation when no
        explicit ``agent_ids`` are provided, then delegates execution
        to ``PlanExecutor`` (which walks the plan DAG, handles
        dependency ordering, parallelisation, retries, and fallbacks).

        When ``agent_ids`` are provided explicitly, a simple linear plan
        is created and executed.

        Args:
            question: The user's question.
            user_id: Authenticated user id.
            user_role: Authenticated user role name.
            conversation_id: Optional existing conversation id.
            agent_ids: Explicit list of agent ids (skips planning).
            mode: ``"auto"`` (default), ``"single"``, ``"sequential"``,
                  or ``"parallel"``.
            session: Optional database session.
            memory_manager: Optional ``MemoryManager``.

        Returns:
            A ``MultiAgentResponse`` with combined results.
        """
        from app.agents.framework.planner import PlanExecutor

        plan: ExecutionPlan

        if agent_ids:
            from app.agents.framework.planner import ExecutionStep

            steps = [
                ExecutionStep(
                    step_id=f"step_{i}",
                    description=f"Execute {aid}",
                    agent_id=aid,
                    output_key=f"result_{aid}",
                )
                for i, aid in enumerate(agent_ids)
            ]
            plan = ExecutionPlan(goal=question, steps=steps, reasoning="Explicit agent selection.")
        else:
            plan = await self._planner.plan(
                question,
                user_role=user_role,
                context_hints={"mode": mode} if mode != "auto" else None,
            )

        executor = PlanExecutor(
            registry=self._registry,
            factory=self._factory,
            memory_manager=memory_manager or self._memory_manager,
            llm_provider=self._llm,
        )

        return await executor.execute(
            plan=plan,
            question=question,
            user_id=user_id,
            user_role=user_role,
            conversation_id=conversation_id,
            session=session,
            memory_manager=memory_manager or self._memory_manager,
        )

    async def stream_multi(
        self,
        question: str,
        user_id: str,
        user_role: str,
        conversation_id: str | None = None,
        agent_ids: list[str] | None = None,
        mode: str = "auto",
        session: AsyncSession | None = None,
        memory_manager: MemoryManager | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a multi-agent workflow via SSE events.

        Delegates to ``execute_multi`` and yields intermediate status updates
        and streaming tokens before yielding the full ``MultiAgentResponse``.
        """
        import asyncio
        import json
        from app.agents.framework.planner import PlanExecutor

        queue: asyncio.Queue[tuple[str, Any] | None] = asyncio.Queue()

        async def event_callback(event_type: str, data: Any) -> None:
            await queue.put((event_type, data))

        async def stream_callback(chunk: str) -> None:
            await queue.put(("token", chunk))

        # We must plan first to yield the plan event immediately.
        if agent_ids:
            from app.agents.framework.planner import ExecutionStep
            steps = [
                ExecutionStep(
                    step_id=f"step_{i}", description=f"Execute {aid}",
                    agent_id=aid, output_key=f"result_{aid}",
                )
                for i, aid in enumerate(agent_ids)
            ]
            from app.agents.framework.planner import ExecutionPlan
            plan = ExecutionPlan(goal=question, steps=steps, reasoning="Explicit agent selection.")
        else:
            plan = await self._planner.plan(
                question, user_role=user_role,
                context_hints={"mode": mode} if mode != "auto" else None,
            )

        executor = PlanExecutor(
            registry=self._registry,
            factory=self._factory,
            memory_manager=memory_manager or self._memory_manager,
            llm_provider=self._llm,
        )

        yield f"event: plan\ndata: {plan.model_dump_json()}\n\n"

        async def _run_executor():
            try:
                result = await executor.execute(
                    plan=plan,
                    question=question,
                    user_id=user_id,
                    user_role=user_role,
                    conversation_id=conversation_id,
                    session=session,
                    memory_manager=memory_manager or self._memory_manager,
                    event_callback=event_callback,
                    stream_callback=stream_callback,
                )
                await queue.put(("done", result.model_dump()))
            except asyncio.CancelledError:
                await queue.put(("error", {"message": "Cancelled"}))
            except Exception as e:
                logger.exception("Multi-agent executor failed in stream")
                await queue.put(("error", {"message": str(e)}))
            finally:
                await queue.put(None)

        task = asyncio.create_task(_run_executor())

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                event_type, data = item
                yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        except asyncio.CancelledError:
            task.cancel()
            raise

    # ── Internal helpers ───────────────────────────────────────

    async def _select_agent(
        self,
        question: str,
        agent_id: str | None,
        user_role: str = "",
    ) -> BaseAgent:
        if agent_id is not None:
            try:
                agent = self._registry.get_agent(agent_id)
            except AgentNotFoundError:
                raise OrchestrationError(
                    f"Requested agent '{agent_id}' is not registered."
                )
            err = check_agent_permissions(agent, user_role)
            if err is not None:
                raise OrchestrationError(err)
            return agent

        plan = await self._planner.plan(question, user_role=user_role)
        if not plan.steps or plan.steps[0].agent_id is None:
            agent = self._graceful_fallback(question)
            if agent is None:
                raise OrchestrationError(
                    "No agent is registered to handle this request. "
                    "Ensure at least one agent is initialized at startup."
                )
            return agent

        try:
            agent = self._registry.get_agent(plan.steps[0].agent_id)
        except AgentNotFoundError:
            agent = None

        if agent is None:
            agent = self._graceful_fallback(question)

        if agent is None:
            raise OrchestrationError(
                "No agent is registered to handle this request. "
                "Ensure at least one agent is initialized at startup."
            )

        err = check_agent_permissions(agent, user_role)
        if err is not None:
            raise OrchestrationError(err)

        logger.debug(
            "_select_agent: question=%r planner \u2192 agent=%s reasoning=%r",
            question[:60],
            agent.agent_id,
            plan.reasoning[:100],
        )
        return agent

    async def _build_context(
        self,
        question: str,
        user_id: str,
        user_role: str,
        conversation_id: str | None,
        session: AsyncSession | None,
        memory_manager: MemoryManager | None = None,
    ) -> AgentContext:
        if not question.strip():
            raise InvalidContextError("Question cannot be empty.")

        context = AgentContext(
            user_id=user_id,
            user_role=user_role,
            conversation_id=conversation_id,
            question=question,
            session=session,
            orchestrator=self,
        )

        # Use MemoryManager when available (Milestone 10 Prompt 2)
        if memory_manager is not None:
            await memory_manager.load_conversation(
                conversation_id=conversation_id,
                user_id=user_id,
            )

            # Collect all entity mentions for this conversation
            all_entities: list[dict[str, Any]] = []
            if conversation_id is not None:
                all_entities = list(
                    memory_manager.entity_memory_service.get_conversation_entities(
                        str(conversation_id)
                    )
                )

            # Extract entities from the current question
            current_entities = memory_manager.entity_memory_service.extract_entities_from_text(question)
            if current_entities:
                if conversation_id is not None:
                    memory_manager.entity_memory_service.store_entities(
                        str(conversation_id), current_entities
                    )
                all_entities.extend(current_entities)

            # Resolve ambiguous references ("it", "the pump", etc.)
            resolved = memory_manager.entity_memory_service.resolve_entity_reference(
                question, all_entities
            )

            # Initialise working memory with entity context
            await memory_manager.init_working(
                task=question,
                entity_mentions=all_entities,
            )

            if resolved is not None:
                memory_manager.working.resolved_entity = resolved
                context.metadata["resolved_entity"] = resolved

            # Long-term memory retrieval (Milestone 11)
            await memory_manager.retrieve_relevant(
                query=question,
                user_id=user_id,
                limit=10,
            )

            # User preference retrieval
            if session is not None:
                try:
                    from app.services.preference_service import UserPreferenceService
                    pref_svc = UserPreferenceService(session)
                    user_prefs = await pref_svc.get_preferences(str(user_id))
                    context.metadata["user_preferences"] = user_prefs
                except Exception:
                    logger.warning("User preference retrieval failed (non-fatal)", exc_info=True)

            memory_manager.merge_into(context)
        elif conversation_id and session is not None:
            # Legacy path — direct ConversationRepository access
            from app.repositories.conversation_repository import (
                ConversationRepository,
            )

            repo = ConversationRepository(session)
            conv = await repo.get_conversation_with_messages(
                conversation_id,
                user_id=user_id,
            )
            if conv is not None:
                context.chat_history = [
                    {"role": m.role, "content": m.content}
                    for m in conv.messages
                ]

        return context

    def _graceful_fallback(self, question: str) -> BaseAgent | None:
        for preferred in ("document_analysis", "asset_intelligence", "knowledge_graph"):
            try:
                agent = self._registry.get_agent(preferred)
                logger.warning(
                    "Planner: no confident match for %r \u2014 "
                    "falling back to %s",
                    question[:60],
                    preferred,
                )
                return agent
            except AgentNotFoundError:
                continue
        all_agents = self._registry.list_agents()
        if all_agents:
            logger.warning(
                "Planner: using first available agent %s as last-resort fallback",
                all_agents[0].agent_id,
            )
            return all_agents[0]
        return None

    @staticmethod
    async def _consolidate_memories(
        mgr: MemoryManager,
        question: str,
        answer: str,
        user_id: str,
        conversation_id: str | None,
    ) -> None:
        """Analyse the completed Q&A and persist any important knowledge.

        Called automatically after every ``execute()`` call.
        """
        if mgr.memory_service is None:
            return
        try:
            conversation_text = (
                f"User: {question}\nAssistant: {answer}"
            )
            await mgr.consolidate(
                conversation_text=conversation_text,
                user_id=user_id,
                conversation_id=conversation_id,
            )
        except Exception:
            logger.warning("Memory consolidation failed (non-fatal)", exc_info=True)
