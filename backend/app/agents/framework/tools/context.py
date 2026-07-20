from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.agents.framework.context import AgentContext

if TYPE_CHECKING:
    from app.agents.framework.memory.retrieval_cache import RetrievalCacheEntry
    from app.agents.framework.memory.working_memory import WorkingMemory


@dataclass
class ToolContext:
    """Context object shared with every tool execution.

    Wraps the lower-level ``AgentContext`` and adds tool-specific
    views.  Raw repositories are **not** exposed — tools interact
    with the system through memory and the agent framework instead.
    """

    # ── Identity ───────────────────────────────────────────────
    user_id: str
    user_role: str
    conversation_id: str | None = None

    # ── Permissions ────────────────────────────────────────────
    permissions: set[str] = field(default_factory=set)

    # ── Execution metadata ─────────────────────────────────────
    agent_name: str = ""
    execution_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Working memory reference (read-only via accessors) ─────
    _working_memory: Any = None  # WorkingMemory — TYPE_CHECKING

    # ── Source agent context (kept for advanced use) ───────────
    _agent_context: AgentContext | None = None

    # ── Convenience factories ──────────────────────────────────

    @classmethod
    def from_agent_context(
        cls,
        agent_ctx: AgentContext,
        *,
        agent_name: str = "",
        execution_id: str = "",
        user_permissions: set[str] | None = None,
    ) -> ToolContext:
        """Build a ``ToolContext`` from an ``AgentContext``.

        Extracts user identity, conversation id, working memory, and
        copies relevant metadata automatically.
        """
        working = getattr(agent_ctx, "working_memory", None)
        perms = (
            user_permissions
            if user_permissions is not None
            else set()
        )

        return cls(
            user_id=agent_ctx.user_id,
            user_role=agent_ctx.user_role,
            conversation_id=agent_ctx.conversation_id,
            permissions=perms,
            agent_name=agent_name,
            execution_id=execution_id,
            metadata=dict(agent_ctx.metadata),
            _working_memory=working,
            _agent_context=agent_ctx,
        )

    # ── Working memory helpers ─────────────────────────────────

    def get_temp(self, key: str, default: Any = None) -> Any:
        """Read a temporary variable from working memory."""
        if self._working_memory is not None:
            return self._working_memory.get_temp(key, default)
        return default

    def set_temp(self, key: str, value: Any) -> None:
        """Write a temporary variable to working memory."""
        if self._working_memory is not None:
            self._working_memory.set_temp(key, value)

    def add_reasoning_step(self, step: str) -> None:
        """Append a reasoning step to working memory."""
        if self._working_memory is not None:
            self._working_memory.add_reasoning_step(step)

    @property
    def retrieval_cache(self) -> RetrievalCacheEntry | None:
        """Access the per-conversation retrieval cache, if available."""
        if self._agent_context is not None:
            return getattr(self._agent_context, "retrieval_cache", None)
        return None

    @property
    def chat_history(self) -> list[dict]:
        """All conversation turns from the current conversation, newest last."""
        if self._agent_context is not None:
            return getattr(self._agent_context, "chat_history", [])
        return []

    def build_conversation_summary(self) -> str:
        """Build a markdown summary of all conversation turns."""
        history = self.chat_history
        if not history:
            return ""
        lines = [f"**Total turns:** {len(history)}", ""]
        for msg in history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if len(content) > 300:
                content = content[:300].rstrip() + "…"
            lines.append(f"- **{role}**: {content}")
        return "\n".join(lines)

    def build_accumulated_findings(self) -> str:
        """Build a markdown block of findings from working memory and prior step outputs."""
        lines: list[str] = []

        # Execution snapshots from working memory
        wm = self._working_memory
        if wm is not None:
            snapshots = getattr(wm, "execution_history", [])
            if snapshots:
                lines.append(f"### Prior Agent Outputs ({len(snapshots)})\n")
                for snap in snapshots:
                    agent = snap.get("agent_name", snap.get("agent_id", "?"))
                    answer = snap.get("answer", "")
                    reasoning = snap.get("reasoning", "")
                    conf = snap.get("confidence", 0.0)
                    if len(answer) > 300:
                        answer = answer[:300].rstrip() + "…"
                    if len(reasoning) > 200:
                        reasoning = reasoning[:200].rstrip() + "…"
                    lines.append(f"- **{agent}** (confidence={conf:.2f})")
                    if reasoning:
                        lines.append(f"  Reasoning: {reasoning}")
                    if answer:
                        lines.append(f"  Findings: {answer}")
                lines.append("")

        # Step outputs from agent context metadata
        step_outputs = self.metadata.get("step_outputs", {})
        if step_outputs:
            lines.append(f"### Step Outputs ({len(step_outputs)})\n")
            for key, output in step_outputs.items():
                agent_id = output.get("agent_id", key)
                answer = output.get("answer", "")
                conf = output.get("confidence", 0.0)
                if len(answer) > 300:
                    answer = answer[:300].rstrip() + "…"
                lines.append(f"- **{agent_id}** (confidence={conf:.2f}): {answer}")
            lines.append("")

        return "\n".join(lines)

    def build_accumulated_evidence(self) -> str:
        """Build a markdown block of evidence from the agent context."""
        if self._agent_context is None:
            return ""
        lines: list[str] = []

        ctx = self._agent_context
        docs = getattr(ctx, "retrieved_documents", [])
        if docs:
            lines.append(f"### Retrieved Documents ({len(docs)})\n")
            for i, doc in enumerate(docs[:10]):
                content = getattr(doc, "content", str(doc))
                if len(content) > 250:
                    content = content[:250].rstrip() + "…"
                score = getattr(doc, "score", 0.0)
                source = getattr(doc, "source", "?")
                lines.append(f"{i+1}. [{source}] (score={score:.2f}): {content}")
            lines.append("")

        facts = getattr(ctx, "graph_facts", [])
        if facts:
            lines.append(f"### Graph Facts ({len(facts)})\n")
            for fact in facts[:10]:
                lines.append(
                    f"- **{fact.entity_name}** --[{fact.relationship_type}]--> "
                    f"**{fact.related_entity}**"
                )
            lines.append("")

        return "\n".join(lines)
