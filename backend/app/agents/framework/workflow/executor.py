import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.framework.base import BaseAgent, check_agent_permissions
from app.agents.framework.exceptions import OrchestrationError
from app.agents.framework.context import AgentContext
from app.agents.framework.factory import AgentFactory
from app.agents.framework.memory.manager import MemoryManager
from app.agents.framework.registry import AgentRegistry
from app.agents.framework.response import AgentResponse
from app.agents.framework.workflow.router import AgentRouter, RoutingPlan
from app.agents.framework.workflow.schemas import MultiAgentResponse, TimelineEntry
from app.schemas.hybrid import GraphFact, UnifiedContextItem

logger = logging.getLogger(__name__)


class MultiAgentExecutor:
    """Executes multi-agent workflows with shared memory, chaining,
    parallel execution, and fallback support.

    Delegates agent instantiation to ``AgentFactory`` and uses
    ``AgentRouter`` for automatic routing.  When the router has a
    ``PlannerAgent`` attached, routing is performed via the LLM-powered
    planner instead of keyword rules.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        factory: AgentFactory,
        router: AgentRouter | None = None,
        memory_manager: MemoryManager | None = None,
    ) -> None:
        self._registry = registry
        self._factory = factory
        self._router = router or AgentRouter(registry)
        self._memory_manager = memory_manager

    async def execute(
        self,
        question: str,
        user_id: str,
        user_role: str,
        conversation_id: str | None = None,
        agent_ids: list[str] | None = None,
        mode: str = "auto",
        session: AsyncSession | None = None,
        memory_manager: MemoryManager | None = None,
    ) -> MultiAgentResponse:
        """Execute a multi-agent workflow.

        Args:
            question: The user's question.
            user_id: Authenticated user id.
            user_role: Authenticated user role.
            conversation_id: Optional conversation for history.
            agent_ids: Explicit agent list (skips routing).
            mode: ``"auto"`` (default), ``"single"``, ``"sequential"``,
                  or ``"parallel"``.
            session: Optional DB session.
            memory_manager: Optional MemoryManager.

        Returns:
            A ``MultiAgentResponse`` with combined results.
        """
        start = time.perf_counter()
        mgr = memory_manager or self._memory_manager

        if agent_ids:
            plan = RoutingPlan(
                primary_agents=agent_ids,
                execution_mode=mode if mode != "auto" else "multi",
            )
        else:
            route_fn = getattr(self._router, "route_async", None)
            if route_fn is not None:
                plan = await route_fn(question, mode=mode)
            else:
                plan = self._router.route(question, mode=mode)

        context = AgentContext(
            user_id=user_id,
            user_role=user_role,
            conversation_id=conversation_id,
            question=question,
            session=session,
            orchestrator=self,
        )

        if mgr is not None:
            await mgr.load_conversation(
                conversation_id=conversation_id,
                user_id=user_id,
            )
            await mgr.init_working(task=question)

            # Long-term memory retrieval (Milestone 11)
            await mgr.retrieve_relevant(
                query=question,
                user_id=user_id,
                limit=10,
            )

            mgr.merge_into(context)

        if plan.execution_mode == "parallel":
            result = await self._execute_parallel(plan, context, mgr, start)
        elif plan.execution_mode == "sequential":
            result = await self._execute_sequential(plan, context, mgr, start)
        else:
            result = await self._execute_multi(plan, context, mgr, start)

        result.execution_time = time.perf_counter() - start

        if mgr is not None:
            await mgr.save_conversation_turn("user", question)
            await mgr.save_conversation_turn(
                "assistant", result.answer,
                citations=[c.model_dump() for c in result.citations],
            )
            # Read back the (possibly auto-created) conversation id
            if mgr.conversation is not None:
                cid = mgr.conversation.conversation_id
                result.conversation_id = str(cid) if cid is not None else None

            # Long-term memory consolidation (Milestone 11)
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

    async def stream(
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

        Yields ``event: agent_progress`` for each completed agent and
        a final ``event: done`` with the full ``MultiAgentResponse``.
        """
        mgr = memory_manager or self._memory_manager
        start = time.perf_counter()

        if agent_ids:
            plan = RoutingPlan(
                primary_agents=agent_ids,
                execution_mode=mode if mode != "auto" else "multi",
            )
        else:
            route_fn = getattr(self._router, "route_async", None)
            if route_fn is not None:
                plan = await route_fn(question, mode=mode)
            else:
                plan = self._router.route(question, mode=mode)

        context = AgentContext(
            user_id=user_id,
            user_role=user_role,
            conversation_id=conversation_id,
            question=question,
            session=session,
            orchestrator=self,
        )

        if mgr is not None:
            await mgr.load_conversation(
                conversation_id=conversation_id,
                user_id=user_id,
            )
            await mgr.init_working(task=question)

            # Long-term memory retrieval (Milestone 11)
            await mgr.retrieve_relevant(
                query=question,
                user_id=user_id,
                limit=10,
            )

            mgr.merge_into(context)

        yield f"event: meta\ndata: {json.dumps({'conversation_id': conversation_id or ''})}\n\n"

        agents = [self._get_agent(aid, user_role) for aid in plan.primary_agents]
        timeline: list[TimelineEntry] = []
        all_results: list[AgentResponse] = []

        for agent in agents:
            entry_start = time.perf_counter()
            entry = TimelineEntry(
                agent_id=agent.agent_id, agent_name=agent.name,
                start_time=entry_start - start, end_time=0.0,
            )

            yield (
                f"event: agent_progress\n"
                f"data: {json.dumps({'agent_id': agent.agent_id, 'agent_name': agent.name, 'status': 'running'})}\n\n"
            )

            try:
                enriched = await agent.prepare_context(context)
                result = await agent.execute(enriched)
                result.agent_name = agent.name
                result.execution_time = time.perf_counter() - entry_start
                all_results.append(result)
                entry.end_time = time.perf_counter() - start
                entry.duration = entry.end_time - entry.start_time
                entry.confidence = result.confidence
                entry.tools_used = result.tools_used
                entry.status = "success"

                self._pass_context(result, context)

                yield (
                    f"event: agent_progress\n"
                    f"data: {json.dumps({'agent_id': agent.agent_id, 'agent_name': agent.name, 'status': 'success', 'confidence': result.confidence})}\n\n"
                )
            except Exception as exc:
                logger.warning("Agent %s failed: %s", agent.agent_id, exc)
                entry.end_time = time.perf_counter() - start
                entry.duration = entry.end_time - entry.start_time
                entry.status = "error"
                all_results.append(AgentResponse(
                    answer=f"Agent {agent.name} encountered an error.",
                    agent_name=agent.name,
                    confidence=0.0,
                ))

                yield (
                    f"event: agent_progress\n"
                    f"data: {json.dumps({'agent_id': agent.agent_id, 'agent_name': agent.name, 'status': 'error'})}\n\n"
                )

            timeline.append(entry)

            if plan.fallback_agents and entry.status == "error":
                fb = await self._try_fallback(
                    plan.fallback_agents, context, mgr, start,
                )
                if fb is not None:
                    all_results.append(fb[0])
                    timeline.append(fb[1])

        final = self._merge_results(all_results, timeline, plan)
        final.execution_time = time.perf_counter() - start

        if mgr is not None:
            await mgr.save_conversation_turn("user", question)
            await mgr.save_conversation_turn(
                "assistant", final.answer,
                citations=[c.model_dump() for c in final.citations],
            )
            if mgr.conversation is not None:
                cid = mgr.conversation.conversation_id
                final.conversation_id = str(cid) if cid is not None else None

            # Long-term memory consolidation (Milestone 11)
            try:
                conversation_text = f"User: {question}\nAssistant: {final.answer}"
                await mgr.consolidate(
                    conversation_text=conversation_text,
                    user_id=user_id,
                    conversation_id=conversation_id,
                )
            except Exception:
                logger.warning("Memory consolidation failed (non-fatal)", exc_info=True)

        yield f"event: done\ndata: {final.model_dump_json()}\n\n"

    async def _execute_multi(
        self, plan: RoutingPlan, context: AgentContext,
        mgr: MemoryManager | None, start: float,
    ) -> MultiAgentResponse:
        agents = [self._get_agent(aid, context.user_role) for aid in plan.primary_agents]
        timeline: list[TimelineEntry] = []
        all_results: list[AgentResponse] = []

        for i, agent in enumerate(agents):
            entry_start = time.perf_counter()
            entry = TimelineEntry(
                agent_id=agent.agent_id, agent_name=agent.name,
                start_time=entry_start - start, end_time=0.0,
            )

            try:
                enriched = await agent.prepare_context(context)
                result = await agent.execute(enriched)
                result.agent_name = agent.name
                result.execution_time = time.perf_counter() - entry_start
                all_results.append(result)
                entry.end_time = time.perf_counter() - start
                entry.duration = entry.end_time - entry.start_time
                entry.confidence = result.confidence
                entry.tools_used = result.tools_used
                entry.status = "success"

                self._pass_context(result, context)
            except Exception as exc:
                logger.warning("Agent %s failed: %s", agent.agent_id, exc)
                entry.end_time = time.perf_counter() - start
                entry.duration = entry.end_time - entry.start_time
                entry.status = "error"
                all_results.append(AgentResponse(
                    answer=f"Agent {agent.name} encountered an error.",
                    agent_name=agent.name,
                    confidence=0.0,
                ))

            timeline.append(entry)

            if plan.fallback_agents and entry.status == "error":
                fallback_result = await self._try_fallback(
                    plan.fallback_agents, context, mgr, start,
                )
                if fallback_result is not None:
                    all_results.append(fallback_result[0])
                    timeline.append(fallback_result[1])

        return self._merge_results(all_results, timeline, plan)

    async def _execute_sequential(
        self, plan: RoutingPlan, context: AgentContext,
        mgr: MemoryManager | None, start: float,
    ) -> MultiAgentResponse:
        chain = plan.chain or plan.primary_agents
        agents = [self._get_agent(aid, context.user_role) for aid in chain]
        timeline: list[TimelineEntry] = []
        all_results: list[AgentResponse] = []

        for agent in agents:
            entry_start = time.perf_counter()
            entry = TimelineEntry(
                agent_id=agent.agent_id, agent_name=agent.name,
                start_time=entry_start - start, end_time=0.0,
            )

            try:
                enriched = await agent.prepare_context(context)
                result = await agent.execute(enriched)
                result.agent_name = agent.name
                result.execution_time = time.perf_counter() - entry_start
                all_results.append(result)
                entry.end_time = time.perf_counter() - start
                entry.duration = entry.end_time - entry.start_time
                entry.confidence = result.confidence
                entry.tools_used = result.tools_used
                entry.status = "success"

                self._pass_context(result, context)
            except Exception as exc:
                logger.warning("Chain agent %s failed: %s", agent.agent_id, exc)
                entry.end_time = time.perf_counter() - start
                entry.duration = entry.end_time - entry.start_time
                entry.status = "error"

            timeline.append(entry)

            if plan.fallback_agents and entry.status == "error":
                fb = await self._try_fallback(
                    plan.fallback_agents, context, mgr, start,
                )
                if fb is not None:
                    all_results.append(fb[0])
                    timeline.append(fb[1])

        return self._merge_results(all_results, timeline, plan)

    async def _execute_parallel(
        self, plan: RoutingPlan, context: AgentContext,
        mgr: MemoryManager | None, start: float,
    ) -> MultiAgentResponse:
        groups = plan.parallel_groups or [plan.primary_agents]
        timeline: list[TimelineEntry] = []
        all_results: list[AgentResponse] = []
        pg_info: list[list[str]] = []

        for group in groups:
            agents = [self._get_agent(aid, context.user_role) for aid in group]
            pg_info.append([a.agent_id for a in agents])

            async def run_agent(agent: BaseAgent) -> tuple[AgentResponse | None, TimelineEntry | None]:
                entry_start = time.perf_counter()
                entry = TimelineEntry(
                    agent_id=agent.agent_id, agent_name=agent.name,
                    start_time=entry_start - start, end_time=0.0,
                )
                try:
                    enriched = await agent.prepare_context(context)
                    result = await agent.execute(enriched)
                    result.agent_name = agent.name
                    result.execution_time = time.perf_counter() - entry_start
                    entry.end_time = time.perf_counter() - start
                    entry.duration = entry.end_time - entry.start_time
                    entry.confidence = result.confidence
                    entry.tools_used = result.tools_used
                    entry.status = "success"
                    return result, entry
                except Exception as exc:
                    logger.warning("Parallel agent %s failed: %s", agent.agent_id, exc)
                    entry.end_time = time.perf_counter() - start
                    entry.duration = entry.end_time - entry.start_time
                    entry.status = "error"
                    return None, entry

            tasks = [run_agent(a) for a in agents]
            completed = await asyncio.gather(*tasks)

            for result, entry in completed:
                if entry is not None:
                    timeline.append(entry)
                if result is not None:
                    self._pass_context(result, context)
                    all_results.append(result)
                elif entry is not None:
                    all_results.append(AgentResponse(
                        answer=f"Agent {entry.agent_name} encountered an error.",
                        agent_name=entry.agent_name,
                        confidence=0.0,
                    ))

            if plan.fallback_agents:
                for fb_aid in plan.fallback_agents:
                    fb_agent = self._get_agent(fb_aid, context.user_role)
                    fb_entry_start = time.perf_counter()
                    fb_entry = TimelineEntry(
                        agent_id=fb_agent.agent_id, agent_name=fb_agent.name,
                        start_time=fb_entry_start - start,
                        end_time=0.0, status="fallback",
                    )
                    try:
                        enriched = await fb_agent.prepare_context(context)
                        fb_result = await fb_agent.execute(enriched)
                        fb_result.agent_name = fb_agent.name
                        fb_entry.end_time = time.perf_counter() - start
                        fb_entry.duration = fb_entry.end_time - fb_entry.start_time
                        fb_entry.confidence = fb_result.confidence
                        fb_entry.tools_used = fb_result.tools_used
                        fb_entry.status = "success"
                        self._pass_context(fb_result, context)
                        all_results.append(fb_result)
                    except Exception:
                        fb_entry.end_time = time.perf_counter() - start
                        fb_entry.duration = fb_entry.end_time - fb_entry.start_time
                        fb_entry.status = "error"
                    timeline.append(fb_entry)

        response = self._merge_results(all_results, timeline, plan)
        response.parallel_groups = pg_info
        return response

    async def _try_fallback(
        self, fallback_ids: list[str], context: AgentContext,
        mgr: MemoryManager | None, start: float,
    ) -> tuple[AgentResponse, TimelineEntry] | None:
        for fb_aid in fallback_ids:
            try:
                fb_agent = self._get_agent(fb_aid, context.user_role)
                entry_start = time.perf_counter()
                entry = TimelineEntry(
                    agent_id=fb_agent.agent_id, agent_name=fb_agent.name,
                    start_time=entry_start - start, end_time=0.0,
                    status="fallback",
                )
                enriched = await fb_agent.prepare_context(context)
                fb_result = await fb_agent.execute(enriched)
                fb_result.agent_name = fb_agent.name
                fb_result.execution_time = time.perf_counter() - entry_start
                entry.end_time = time.perf_counter() - start
                entry.duration = entry.end_time - entry.start_time
                entry.confidence = fb_result.confidence
                entry.tools_used = fb_result.tools_used
                entry.status = "success"
                self._pass_context(fb_result, context)
                return fb_result, entry
            except Exception as exc:
                logger.warning("Fallback %s failed: %s", fb_aid, exc)
        return None

    @staticmethod
    def _pass_context(result: AgentResponse, context: AgentContext) -> None:
        if context.working_memory is None:
            return
        if result.citations:
            from app.schemas.hybrid import UnifiedContextItem
            for c in result.citations:
                context.retrieved_documents.append(UnifiedContextItem(
                    content=c.chunk_content or "",
                    source=c.document_name,
                    score=c.similarity_score,
                    metadata={},
                ))
        if result.graph_citations:
            from app.schemas.hybrid import GraphFact
            for gc in result.graph_citations:
                context.graph_facts.append(GraphFact(
                    entity_name=gc.entity_name,
                    relationship_type=gc.relationship_type,
                    related_entity=gc.related_entity,
                ))

    def _get_agent(self, agent_id: str, user_role: str = "") -> BaseAgent:
        agent = self._registry.get_agent(agent_id)
        err = check_agent_permissions(agent, user_role)
        if err is not None:
            raise OrchestrationError(err)
        return agent

    @staticmethod
    def _merge_results(
        results: list[AgentResponse],
        timeline: list[TimelineEntry],
        plan: RoutingPlan,
    ) -> MultiAgentResponse:
        if not results:
            return MultiAgentResponse(
                answer="No agents could process this request.",
                execution_order=plan.primary_agents,
                timeline=timeline,
            )

        seen_citations: set[str] = set()
        combined_citations = []
        seen_graph_citations: set[str] = set()
        combined_graph_citations = []

        all_tools: set[str] = set()
        execution_order: list[str] = []
        seen_order: set[str] = set()
        answers: list[str] = []
        confidences: list[float] = []

        for r in results:
            if r.tools_used:
                all_tools.update(r.tools_used)

            if r.agent_name and r.agent_name not in seen_order:
                seen_order.add(r.agent_name)
                execution_order.append(r.agent_name)

            for c in r.citations:
                key = f"{c.document_name}:{c.page_number}:{c.chunk_content}"
                if key not in seen_citations:
                    seen_citations.add(key)
                    combined_citations.append(c)

            for gc in r.graph_citations:
                key = f"{gc.entity_name}:{gc.relationship_type}:{gc.related_entity}"
                if key not in seen_graph_citations:
                    seen_graph_citations.add(key)
                    combined_graph_citations.append(gc)

            if r.answer and r.confidence > 0:
                answers.append(r.answer)
                confidences.append(r.confidence)

        combined_answer = MultiAgentExecutor._combine_answers(answers, confidences)
        avg_confidence = (
            sum(confidences) / len(confidences)
            if confidences else 0.0
        )
        weighted_confidence = max(
            avg_confidence,
            max(confidences) if confidences else 0.0,
        )

        return MultiAgentResponse(
            answer=combined_answer,
            agent_results=results,
            citations=combined_citations,
            graph_citations=combined_graph_citations,
            confidence=weighted_confidence,
            execution_order=execution_order,
            timeline=timeline,
            all_tools_used=sorted(all_tools),
        )

    @staticmethod
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
