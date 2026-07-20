import uuid
from typing import Any, Callable, Union

from app.agents.framework.context import AgentContext
from app.agents.framework.memory.base import Memory
from app.agents.framework.memory.conversation_memory import ConversationMemory
from app.agents.framework.memory.retrieval_cache import (
    RetrievalCacheEntry,
    get_retrieval_cache,
)
from app.agents.framework.memory.summarizer import ContextSummarizer, SimpleSummarizer
from app.agents.framework.memory.working_memory import WorkingMemory
from app.agents.framework.memory.semantic_memory import SemanticMemory
from app.agents.framework.memory.episodic_memory import EpisodicMemory
from app.core.observability import metrics
from app.agents.framework.memory.reflection_memory import ReflectionMemory
from app.agents.framework.memory.planning_memory import PlanningMemory
from app.agents.framework.memory.shared_agent_memory import SharedAgentMemory
from app.schemas.hybrid import GraphFact, UnifiedContextItem
from app.schemas.memory import MemorySearchResult
from app.services.entity_memory_service import EntityMemoryService
from app.services.memory_service import MemoryService


UUID_LIKE = Union[str, uuid.UUID, None]


class MemoryManager:
    """Central coordinator for all memory types used during agent execution.

    Responsibilities:
    - Load conversation history into ``ConversationMemory``.
    - Initialize ``WorkingMemory`` with the current task and context.
    - Merge both memories into the ``AgentContext`` before execution.
    - Persist new conversation turns after execution.
    - **Consolidate** completed conversations into long-term memory.
    - **Retrieve** relevant long-term memories before agent execution.
    - Produce context summaries for the prompt builder.
    """

    def __init__(
        self,
        conversation_memory: ConversationMemory,
        working_memory: WorkingMemory | None = None,
        summarizer: ContextSummarizer | None = None,
        semantic_memory: SemanticMemory | None = None,
        episodic_memory: EpisodicMemory | None = None,
        reflection_memory: ReflectionMemory | None = None,
        planning_memory: PlanningMemory | None = None,
        shared_memory: SharedAgentMemory | None = None,
        memory_service: MemoryService | None = None,
        entity_memory_service: EntityMemoryService | None = None,
    ) -> None:
        self._conversation = conversation_memory
        self._working = working_memory or WorkingMemory()
        self._summarizer = summarizer or SimpleSummarizer()

        self._semantic = semantic_memory or SemanticMemory()
        self._episodic = episodic_memory or EpisodicMemory()
        self._reflection = reflection_memory or ReflectionMemory()
        self._planning = planning_memory or PlanningMemory()
        self._shared = shared_memory or SharedAgentMemory()

        self._memory_service = memory_service
        self._entity_svc = entity_memory_service or EntityMemoryService()
        self._retrieved_memories: list[MemorySearchResult] = []

    # ── Properties ─────────────────────────────────────────────

    @property
    def conversation(self) -> ConversationMemory:
        return self._conversation

    @property
    def working(self) -> WorkingMemory:
        return self._working

    @property
    def semantic(self) -> SemanticMemory:
        return self._semantic

    @property
    def episodic(self) -> EpisodicMemory:
        return self._episodic

    @property
    def reflection(self) -> ReflectionMemory:
        return self._reflection

    @property
    def planning(self) -> PlanningMemory:
        return self._planning

    @property
    def shared(self) -> SharedAgentMemory:
        return self._shared

    @property
    def memory_service(self) -> MemoryService | None:
        return self._memory_service

    @property
    def entity_memory_service(self) -> EntityMemoryService:
        return self._entity_svc

    # ── Lifecycle ──────────────────────────────────────────────

    async def load_conversation(
        self,
        conversation_id: UUID_LIKE = None,
        user_id: UUID_LIKE = None,
    ) -> list[dict[str, Any]]:
        """Load conversation history into ``ConversationMemory``.

        Also extracts and loads any entity mentions previously
        stored for this conversation into ``EntityMemoryService``.

        Returns the loaded message list for convenience.
        """
        self._conversation.conversation_id = conversation_id
        self._conversation.user_id = user_id
        messages = await self._conversation.load()

        # Rehydrate entity mentions for this conversation
        if conversation_id is not None:
            cid = str(conversation_id)
            stored = self._entity_svc.get_conversation_entities(cid)
            if not stored:
                for msg in messages:
                    if msg.get("role") == "user":
                        extracted = self._entity_svc.extract_entities_from_text(msg.get("content", ""))
                        if extracted:
                            self._entity_svc.store_entities(cid, extracted)

        return messages

    async def init_working(
        self,
        task: str = "",
        retrieved_documents: list[UnifiedContextItem] | None = None,
        graph_facts: list[GraphFact] | None = None,
        entity_mentions: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize working memory for a new execution cycle."""
        await self._working.clear()
        self._working.current_task = task
        if retrieved_documents:
            self._working.retrieved_documents = retrieved_documents
        if graph_facts:
            self._working.graph_facts = graph_facts
        if entity_mentions:
            self._working.entity_mentions = entity_mentions
        for key, value in kwargs.items():
            self._working.set_temp(key, value)

    def merge_into(self, context: AgentContext) -> None:
        """Attach all memories to the given ``AgentContext``.

        Populates every memory type field and also fills scalar
        context fields (``chat_history``, ``retrieved_documents``,
        ``graph_facts``) so agents can access them directly without
        having to go through the memory objects.

        Does **not** duplicate data — the memory objects remain the
        primary interface for structured access.
        """
        context.conversation_memory = self._conversation
        context.working_memory = self._working
        context.semantic_memory = self._semantic
        context.episodic_memory = self._episodic
        context.reflection_memory = self._reflection
        context.planning_memory = self._planning
        context.shared_memory = self._shared
        context.retrieved_memories = self._retrieved_memories

        # Populate scalar context fields so agents that read
        # context.chat_history, context.retrieved_documents, or
        # context.graph_facts see the data already loaded.
        if self._conversation is not None:
            context.chat_history = self._conversation.messages
        context.retrieved_documents = list(self._working.retrieved_documents)
        context.graph_facts = list(self._working.graph_facts)

        # Attach per-conversation retrieval cache
        if context.conversation_id:
            context.retrieval_cache = get_retrieval_cache(
                str(context.conversation_id),
            )

    # ── Conversation persistence ───────────────────────────────

    async def save_conversation_turn(
        self,
        role: str,
        content: str,
        citations: list[dict] | None = None,
    ) -> None:
        """Persist one turn (user question or assistant answer) to the
        conversation store.

        Entity mentions in user messages are automatically extracted
        and stored in entity memory for future reference.
        """
        await self._conversation.append({
            "role": role,
            "content": content,
            "citations": citations,
        })

        if role == "user" and self._conversation.conversation_id is not None:
            cid = str(self._conversation.conversation_id)
            entities = self._entity_svc.extract_entities_from_text(content)
            if entities:
                new_entities = self._entity_svc.store_entities(cid, entities)
                for ent in new_entities:
                    self._working.add_entity_mention(ent)

    # ── Long-term memory retrieval ─────────────────────────────

    async def retrieve_relevant(
        self,
        query: str,
        user_id: str | None = None,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        import time
        start_time = time.perf_counter()
        
        if self._memory_service is not None and user_id is not None:
            results = await self._memory_service.search(
                query=query,
                user_id=str(user_id) if isinstance(user_id, uuid.UUID) else user_id,
                limit=limit,
            )
            self._retrieved_memories = results
            metrics.increment("memory.hits" if results else "memory.misses")
            metrics.record_histogram("memory.retrieval.time", time.perf_counter() - start_time)
            return results

        self._retrieved_memories = []
        metrics.increment("memory.misses")
        metrics.record_histogram("memory.retrieval.time", time.perf_counter() - start_time)
        return []

    # ── Long-term memory consolidation ─────────────────────────

    async def consolidate(
        self,
        conversation_text: str,
        user_id: str | None = None,
        conversation_id: str | None = None,
        llm_summarize: Callable[[str], str] | None = None,
    ) -> list[dict[str, Any]]:
        """Analyse a completed conversation and decide what to remember.

        Delegates to ``MemoryService.consolidate_conversation()`` which:
        1. Classifies content into ``MemoryType`` categories.
        2. Deduplicates against existing memories.
        3. Merges or creates new memory records.
        4. Assigns importance, confidence, and source.

        Returns a list of created/merged memory dicts.
        """
        if self._memory_service is None or not user_id:
            return []

        uid = str(user_id) if isinstance(user_id, uuid.UUID) else user_id
        results = await self._memory_service.consolidate_conversation(
            conversation_text=conversation_text,
            user_id=uid,
            conversation_id=conversation_id,
        )
        return [r.model_dump() for r in results]

    # ── Long-term memory lifecycle ─────────────────────────────

    async def remember(
        self,
        user_id: str,
        type_name: str,
        title: str,
        content: str,
        importance: float = 0.5,
        confidence: float = 0.5,
        source: str | None = None,
    ) -> dict[str, Any] | None:
        """Create a new long-term memory."""
        if self._memory_service is None:
            return None
        from app.schemas.memory import MemoryCreate, MemoryType
        mem_type = MemoryType(type_name) if type_name in MemoryType._value2member_map_ else MemoryType.TEMPORARY_MEMORY
        result = await self._memory_service.remember(
            MemoryCreate(
                user_id=user_id,
                type=mem_type,
                title=title,
                content=content,
                importance=importance,
                confidence=confidence,
                source=source,
            ),
        )
        return result.model_dump() if result else None

    async def recall(self, memory_id: str) -> dict[str, Any] | None:
        """Retrieve a specific memory by id."""
        if self._memory_service is None:
            return None
        result = await self._memory_service.recall(memory_id)
        return result.model_dump() if result else None

    async def update_memory(
        self,
        memory_id: str,
        title: str | None = None,
        content: str | None = None,
        importance: float | None = None,
        confidence: float | None = None,
    ) -> dict[str, Any] | None:
        """Update an existing memory."""
        if self._memory_service is None:
            return None
        from app.schemas.memory import MemoryUpdate
        result = await self._memory_service.update_memory(
            memory_id,
            MemoryUpdate(
                title=title,
                content=content,
                importance=importance,
                confidence=confidence,
            ),
        )
        return result.model_dump() if result else None

    async def merge_memories(
        self,
        target_id: str,
        source_ids: list[str],
        new_content: str,
        new_title: str | None = None,
        new_summary: str | None = None,
    ) -> dict[str, Any] | None:
        """Merge multiple memories into one."""
        if self._memory_service is None:
            return None
        result = await self._memory_service.merge_memories(
            target_id=target_id,
            source_ids=source_ids,
            new_content=new_content,
            new_title=new_title,
            new_summary=new_summary,
        )
        return result.model_dump() if result else None

    async def forget(self, memory_id: str) -> bool:
        """Mark a memory as forgotten."""
        if self._memory_service is None:
            return False
        return await self._memory_service.forget(memory_id)

    async def archive_memory(self, memory_id: str) -> bool:
        """Archive a memory for cold storage."""
        if self._memory_service is None:
            return False
        return await self._memory_service.archive_memory(memory_id)

    async def expire_stale(self) -> int:
        """Expire any timed-out memories."""
        if self._memory_service is None:
            return 0
        return await self._memory_service.expire_stale()

    # ── Context summary ────────────────────────────────────────

    async def get_context_summary(self, max_tokens: int = 2000) -> str:
        """Return a combined summary of conversation + working memory.

        Useful for fitting context into an LLM prompt window.
        """
        parts: list[str] = []

        if self._conversation is not None:
            conv_summary = await self._conversation.summarize(max_tokens // 2)
            if conv_summary:
                parts.append("--- Conversation ---\n" + conv_summary)

        working_summary = await self._working.summarize(max_tokens // 2)
        if working_summary:
            parts.append("--- Working Memory ---\n" + working_summary)

        if self._semantic:
            sem_summary = await self._semantic.summarize(max_tokens // 5)
            if sem_summary:
                parts.append("--- Semantic Memory ---\n" + sem_summary)

        if self._episodic:
            ep_summary = await self._episodic.summarize(max_tokens // 5)
            if ep_summary:
                parts.append("--- Episodic Memory ---\n" + ep_summary)

        if self._reflection:
            ref_summary = await self._reflection.summarize(max_tokens // 5)
            if ref_summary:
                parts.append("--- Reflection Memory ---\n" + ref_summary)

        if self._planning:
            plan_summary = await self._planning.summarize(max_tokens // 5)
            if plan_summary:
                parts.append("--- Planning Memory ---\n" + plan_summary)

        if self._shared:
            share_summary = await self._shared.summarize(max_tokens // 5)
            if share_summary:
                parts.append("--- Shared Agent Memory ---\n" + share_summary)

        if self._retrieved_memories:
            mem_lines = [f"- [{m.type}] {m.title} (score={m.similarity_score:.2f})" for m in self._retrieved_memories[:5]]
            parts.append("--- Relevant Memories ---\n" + "\n".join(mem_lines))

        return "\n\n".join(parts)

    async def clear_all(self) -> None:
        """Reset all memories including entity memory."""
        if self._conversation is not None:
            await self._conversation.clear()
        await self._working.clear()

        if self._semantic is not None:
            await self._semantic.clear()
        if self._episodic is not None:
            await self._episodic.clear()
        if self._reflection is not None:
            await self._reflection.clear()
        if self._planning is not None:
            await self._planning.clear()
        if self._shared is not None:
            await self._shared.clear()

        self._retrieved_memories = []
