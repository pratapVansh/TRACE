from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.hybrid import GraphFact, UnifiedContextItem
from app.schemas.memory import MemorySearchResult

if TYPE_CHECKING:
    from app.agents.framework.memory.conversation_memory import ConversationMemory
    from app.agents.framework.memory.retrieval_cache import RetrievalCacheEntry
    from app.agents.framework.memory.working_memory import WorkingMemory
    from app.agents.framework.memory.semantic_memory import SemanticMemory
    from app.agents.framework.memory.episodic_memory import EpisodicMemory
    from app.agents.framework.memory.reflection_memory import ReflectionMemory
    from app.agents.framework.memory.planning_memory import PlanningMemory
    from app.agents.framework.memory.shared_agent_memory import SharedAgentMemory


def _truncate(text: str, max_chars: int = 200) -> str:
    """Truncate *text* to *max_chars* characters, appending ``...``."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."



@dataclass
class AgentContext:
    """Shared execution context for all agents.

    Carries everything an agent needs to respond: who the user is,
    what conversation this belongs to, what knowledge has already been
    retrieved, and any execution metadata.  Reuses the existing
    Conversation system for chat history — nothing is duplicated.

    Memory integration (Milestone 10 Prompt 2):
    ``conversation_memory`` and ``working_memory`` are attached by
    ``MemoryManager.merge_into()`` before execution.  Agents read
    history from ``conversation_memory.load()`` or
    ``conversation_memory.summarize()`` instead of the raw
    ``chat_history`` list.  Both fields are optional so that existing
    code that constructs ``AgentContext`` directly still works.

    Long-term memory (Milestone 11):
    ``retrieved_memories`` contains semantically-relevant memories
    fetched before execution.  Agents can use them for context-aware
    responses (e.g. "Continue yesterday's RCA").
    """

    user_id: str
    user_role: str
    conversation_id: str | None = None
    question: str = ""

    chat_history: list[dict] = field(default_factory=list)
    retrieved_documents: list[UnifiedContextItem] = field(default_factory=list)
    graph_facts: list[GraphFact] = field(default_factory=list)
    uploaded_document_ids: list[str] = field(default_factory=list)

    session: AsyncSession | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Memory integration — set by MemoryManager.merge_into()
    conversation_memory: ConversationMemory | None = None
    working_memory: WorkingMemory | None = None
    semantic_memory: SemanticMemory | None = None
    episodic_memory: EpisodicMemory | None = None
    reflection_memory: ReflectionMemory | None = None
    planning_memory: PlanningMemory | None = None
    shared_memory: SharedAgentMemory | None = None

    # Long-term memory retrieval — set by MemoryManager.merge_into()
    retrieved_memories: list[MemorySearchResult] = field(default_factory=list)

    # Per-conversation retrieval cache — avoids duplicate lookups
    # across multiple queries in the same conversation.
    retrieval_cache: RetrievalCacheEntry | None = None

    # Multi-agent delegation
    orchestrator: Any | None = None

    # ── Shared context prompt ──────────────────────────────────────

    def build_shared_context_prompt(self) -> str:
        """Build a formatted markdown block with all shared context data.

        Includes conversation history, retrieved documents, graph facts,
        long-term memories, entity mentions, and the cross-agent
        scratchpad (working memory temp variables).

        Agents can inject this into their LLM prompts via
        ``context.metadata["shared_context_prompt"]`` (set automatically
        by ``BaseAgent.prepare_context()``).

        Returns:
            An empty string if nothing is available, otherwise a
            markdown-formatted block.
        """
        lines: list[str] = []
        has_content = False

        # ── Conversation history ─────────────────────────────────
        if self.chat_history:
            has_content = True
            lines.append("## Conversation History\n")
            for msg in self.chat_history[-6:]:
                role = msg.get("role", "unknown")
                content = _truncate(msg.get("content", ""), 300)
                lines.append(f"- **{role}**: {content}")
            lines.append("")

        # ── Retrieved documents ──────────────────────────────────
        if self.retrieved_documents:
            has_content = True
            lines.append(
                f"## Retrieved Documents ({len(self.retrieved_documents)})\n"
            )
            for doc in self.retrieved_documents[:5]:
                snippet = _truncate(doc.content, 200) if hasattr(doc, "content") else str(doc)
                lines.append(f"- {snippet}")
            lines.append("")

        # ── Graph facts ──────────────────────────────────────────
        if self.graph_facts:
            has_content = True
            lines.append(f"## Graph Facts ({len(self.graph_facts)})\n")
            for fact in self.graph_facts[:5]:
                lines.append(
                    f"- **{fact.entity_name}** --[{fact.relationship_type}]--> "
                    f"**{fact.related_entity}**"
                )
            lines.append("")

        # ── Long-term memories ───────────────────────────────────
        if self.retrieved_memories:
            has_content = True
            lines.append(
                f"## Relevant Long-term Memories ({len(self.retrieved_memories)})\n"
            )
            for mem in self.retrieved_memories[:5]:
                title = _truncate(mem.title, 100) if hasattr(mem, "title") else "?"
                score = mem.similarity_score if hasattr(mem, "similarity_score") else 0.0
                mtype = mem.type if hasattr(mem, "type") else "memory"
                lines.append(f"- [{mtype}] *{title}* (score={score:.2f})")
            lines.append("")

        # ── Entity mentions (from working memory) ────────────────
        if self.working_memory is not None:
            entities = self.working_memory.entity_mentions
            if entities:
                has_content = True
                lines.append(
                    f"## Known Entities ({len(entities)})\n"
                )
                for ent in entities[:5]:
                    name = ent.get("name", "?")
                    etype = ent.get("type", "unknown")
                    lines.append(f"- **{name}** ({etype})")
                lines.append("")

            # ── Cross-agent scratchpad ───────────────────────────
            temp_vars = self.working_memory.temp_variables
            if temp_vars:
                has_content = True
                lines.append("## Agent Scratchpad (shared working memory)\n")
                for key, value in temp_vars.items():
                    val_str = _truncate(str(value), 150)
                    lines.append(f"- **{key}**: {val_str}")
                lines.append("")

        # ── Prior step outputs ───────────────────────────────────
        step_outputs = self.metadata.get("step_outputs", {})
        if step_outputs:
            has_content = True
            lines.append("## Prior Agent Outputs\n")
            for key, output in step_outputs.items():
                agent_id = output.get("agent_id", key)
                answer = _truncate(output.get("answer", ""), 300)
                conf = output.get("confidence", 0.0)
                lines.append(f"- **{agent_id}** (confidence={conf:.2f}): {answer}")
            lines.append("")

        if not has_content:
            return ""

        return "\n".join(lines)
