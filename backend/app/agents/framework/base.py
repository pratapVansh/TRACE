from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from app.agents.framework.context import AgentContext
from app.agents.framework.response import AgentResponse
from app.core.authorization import Permission


def check_agent_permissions(agent: BaseAgent, user_role: str) -> str | None:
    """Check whether *user_role* has the permissions required by *agent*.

    Returns ``None`` if the user is authorised, or an error message
    (suitable for an ``OrchestrationError``) listing every missing
    permission.

    This is a module-level function so it can be reused by
    ``AIOrchestrator`` and ``MultiAgentExecutor`` without code
    duplication or circular imports.
    """
    if not agent.required_permissions:
        return None
    from app.core.authorization import get_permissions_for_role

    user_perms = get_permissions_for_role(user_role)
    missing = agent.required_permissions - set(user_perms)
    if not missing:
        return None
    return (
        f"Access denied: agent '{agent.agent_id}' requires "
        f"{', '.join(sorted(p.value for p in missing))}."
    )


class BaseAgent(ABC):
    """Abstract base for every TRACE AI agent.

    Every agent exposes:
    - ``agent_id``  — unique machine-readable identifier
    - ``name``      — human-readable display name
    - ``description`` — what this agent does
    - ``supported_tasks`` — task labels this agent can handle
    - ``required_permissions`` — set of Permission values a user must hold

    Subclasses implement ``execute()`` with the core logic.
    The framework calls ``prepare_context()`` before execution so agents
    can enrich the shared context with agent-specific data.
    """

    agent_id: str
    name: str
    description: str
    supported_tasks: list[str] = []
    required_permissions: set[Permission] = set()

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResponse:
        """Run the agent's core logic and return a response."""

    def can_handle(self, task: str) -> float:
        """Return a confidence score (0.0 – 1.0) for a given task.

        Default implementation checks ``supported_tasks``.
        Subclasses may override with custom logic (e.g. LLM-based
        intent matching).
        """
        return 1.0 if task in self.supported_tasks else 0.0

    async def prepare_context(self, context: AgentContext) -> AgentContext:
        """Enrich the execution context before ``execute()`` is called.

        The base implementation:
        1. Injects collaboration context — prior agents' findings,
           messages, and execution history — into
           ``context.metadata["collaboration"]``.
        2. Injects shared context — conversation history, retrieved
           documents, graph facts, long-term memories, entity
           mentions, and the cross-agent scratchpad — into
           ``context.metadata["shared_context_prompt"]``.

        Subclasses that override **must** call ``super().prepare_context()``
        to preserve both injections, or call the individual helpers.
        """
        self._inject_collaboration_context(context)
        self._inject_shared_context(context)
        return context

    # ── Collaboration helpers ──────────────────────────────────

    def _inject_collaboration_context(self, context: AgentContext) -> None:
        """Inject prior agent outputs and messages into context metadata.

        Called automatically by ``prepare_context()``.  No-op if no
        working memory or no prior execution history exists.
        """
        wm = context.working_memory
        if wm is None:
            return

        collab_ctx = wm.build_collaboration_context(self.agent_id)
        context.metadata["collaboration_context"] = collab_ctx
        context.metadata["collaboration_prompt"] = collab_ctx.to_prompt_block()

    def _inject_shared_context(self, context: AgentContext) -> None:
        """Inject conversation history, retrieved data, and scratchpad.

        Builds a single ``shared_context_prompt`` string from
        ``AgentContext.build_shared_context_prompt()`` and stores it
        in ``context.metadata["shared_context_prompt"]`` so every
        agent has a unified view of everything known so far.

        No-op if no shared data is available (e.g. first agent in a
        chain with no conversation history and empty working memory).
        """
        shared = context.build_shared_context_prompt()
        if shared:
            context.metadata["shared_context_prompt"] = shared

    def _post_message(
        self,
        context: AgentContext,
        message_type: str,
        content: str,
        target_agent_id: str | None = None,
    ) -> None:
        """Post a structured message to the collaboration message bus.

        Args:
            context: The execution context (must have ``working_memory``).
            message_type: ``analysis_summary``, ``challenge``,
                ``evidence_request``, ``evidence_response``,
                ``critique``, or ``suggestion``.
            content: The message body.
            target_agent_id: Specific agent to address, or ``None``
                for broadcast.
        """
        from app.agents.framework.collaboration.schemas import AgentMessage

        wm = context.working_memory
        if wm is None:
            return

        msg = AgentMessage(
            agent_id=self.agent_id,
            message_type=message_type,
            content=content,
            target_agent_id=target_agent_id,
            timestamp=time.time(),
        )
        wm.add_message(msg)

    def _get_collaboration_messages(
        self,
        context: AgentContext,
        message_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return collaboration messages from the message bus.

        Args:
            context: The execution context.
            message_type: Optional filter by type (e.g. ``"challenge"``).

        Returns:
            List of message dicts sent to this agent.
        """
        wm = context.working_memory
        if wm is None:
            return []

        msgs = wm.get_messages_for_agent(self.agent_id)
        if message_type:
            msgs = [m for m in msgs if m.message_type == message_type]
        return [m.model_dump() for m in msgs]

    def evaluate_confidence(
        self,
        has_evidence: bool,
        search_data: dict | None = None,
        answer: str = "",
    ) -> tuple[float, str]:
        """Evidence-driven confidence scoring.
        
        Extracts document and graph scores from standard search_data structure.
        """
        if not has_evidence:
            return 0.0, "No supporting evidence found."
        
        score = 0.5  # Base score for having some grounded evidence
        explanation_parts = []
        
        # Extract scores
        document_scores = []
        graph_scores = []
        if search_data:
            if "documents" in search_data:
                document_scores = [d.get("score", 0.5) for d in search_data["documents"]]
            elif "document_evidence" in search_data:
                document_scores = [d.get("score", 0.5) for d in search_data["document_evidence"]]
            elif "related_documents" in search_data:
                document_scores = [d.get("score", 0.5) for d in search_data["related_documents"]]
                
            if "incidents" in search_data:
                graph_scores = [d.get("confidence", 0.5) for d in search_data["incidents"]]
            elif "graph_evidence" in search_data:
                graph_scores = [d.get("confidence", 0.5) for d in search_data["graph_evidence"]]
            elif "relationships" in search_data:
                graph_scores = [d.get("confidence", 0.5) for d in search_data["relationships"]]
            elif "similar_incidents" in search_data:
                graph_scores = [d.get("confidence", 0.5) for d in search_data["similar_incidents"]]

        doc_count = len(document_scores)
        if doc_count > 0:
            max_doc = max(document_scores)
            score += min(0.15, max_doc * 0.15)
            score += min(0.1, doc_count * 0.02)
            explanation_parts.append(f"Supported by {doc_count} document(s) (max retrieval score: {max_doc:.2f}).")
            
        graph_count = len(graph_scores)
        if graph_count > 0:
            max_graph = max(graph_scores)
            score += min(0.15, max_graph * 0.15)
            score += min(0.1, graph_count * 0.02)
            explanation_parts.append(f"Supported by {graph_count} graph connection(s) (max score: {max_graph:.2f}).")
            
        # Tool agreement & conflicting evidence heuristics based on answer text
        ans_lower = answer.lower()
        if "conflict" in ans_lower or "contradict" in ans_lower or "disagree" in ans_lower:
            score -= 0.2
            explanation_parts.append("Conflicting evidence detected.")
        else:
            score += 0.05
            explanation_parts.append("Tools and sources are in agreement.")
            
        # LLM Uncertainty
        if "uncertain" in ans_lower or "not sure" in ans_lower or "unclear" in ans_lower or "might" in ans_lower or "possibly" in ans_lower:
            score -= 0.15
            explanation_parts.append("LLM expressed uncertainty in generation.")
            
        score = round(max(0.0, min(0.95, score)), 2)
        explanation = " ".join(explanation_parts) if explanation_parts else "Default evidence-based confidence."
        return score, explanation
