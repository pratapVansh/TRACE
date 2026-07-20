from typing import Any

from app.agents.framework.collaboration.schemas import AgentMessage, CollaborationContext
from app.agents.framework.memory.base import Memory
from app.schemas.hybrid import GraphFact, UnifiedContextItem
from app.services.entity_memory_service import EntityMemoryService


class WorkingMemory(Memory):
    """Short-lived execution memory for a single agent request.

    Exists only during the lifetime of one ``AIOrchestrator.execute``
    call.  Nothing is persisted.
    """

    def __init__(self) -> None:
        self._current_task: str = ""
        self._retrieved_documents: list[UnifiedContextItem] = []
        self._graph_facts: list[GraphFact] = []
        self._intermediate_reasoning: list[str] = []
        self._temp_variables: dict[str, Any] = {}
        self._execution_metadata: dict[str, Any] = {}
        self._entity_mentions: list[dict[str, Any]] = []
        self._resolved_entity: dict[str, Any] | None = None
        self._messages: list[AgentMessage] = []
        self._execution_history: list[dict[str, Any]] = []

    # ── Accessors ──────────────────────────────────────────────

    @property
    def current_task(self) -> str:
        return self._current_task

    @current_task.setter
    def current_task(self, value: str) -> None:
        self._current_task = value

    @property
    def retrieved_documents(self) -> list[UnifiedContextItem]:
        return self._retrieved_documents

    @retrieved_documents.setter
    def retrieved_documents(self, value: list[UnifiedContextItem]) -> None:
        self._retrieved_documents = value

    @property
    def graph_facts(self) -> list[GraphFact]:
        return self._graph_facts

    @graph_facts.setter
    def graph_facts(self, value: list[GraphFact]) -> None:
        self._graph_facts = value

    @property
    def intermediate_reasoning(self) -> list[str]:
        return self._intermediate_reasoning

    @property
    def temp_variables(self) -> dict[str, Any]:
        return self._temp_variables

    @property
    def execution_metadata(self) -> dict[str, Any]:
        return self._execution_metadata

    @property
    def entity_mentions(self) -> list[dict[str, Any]]:
        return self._entity_mentions

    @entity_mentions.setter
    def entity_mentions(self, value: list[dict[str, Any]]) -> None:
        self._entity_mentions = value

    @property
    def resolved_entity(self) -> dict[str, Any] | None:
        return self._resolved_entity

    @resolved_entity.setter
    def resolved_entity(self, value: dict[str, Any] | None) -> None:
        self._resolved_entity = value

    def add_entity_mention(self, entity: dict[str, Any]) -> None:
        for existing in self._entity_mentions:
            if existing["name"] == entity["name"]:
                return
        self._entity_mentions.append(entity)

    def resolve_entity_reference(self, question: str) -> dict[str, Any] | None:
        svc = EntityMemoryService()
        resolved = svc.resolve_entity_reference(question, self._entity_mentions)
        if resolved is not None:
            self._resolved_entity = resolved
        return resolved

    # ── Collaboration (message bus) ────────────────────────────

    @property
    def messages(self) -> list[AgentMessage]:
        return list(self._messages)

    @property
    def execution_history(self) -> list[dict[str, Any]]:
        return list(self._execution_history)

    def add_message(self, msg: AgentMessage) -> None:
        self._messages.append(msg)

    def get_messages_for_agent(self, agent_id: str) -> list[AgentMessage]:
        return [
            m for m in self._messages
            if m.target_agent_id is None or m.target_agent_id == agent_id
        ]

    def get_messages_by_type(self, message_type: str) -> list[AgentMessage]:
        return [m for m in self._messages if m.message_type == message_type]

    def add_execution_snapshot(self, snapshot: dict[str, Any]) -> None:
        self._execution_history.append(snapshot)

    def build_collaboration_context(
        self,
        current_agent_id: str,
        current_step_index: int = 0,
    ) -> CollaborationContext:
        return CollaborationContext(
            execution_history=list(self._execution_history),
            messages=self.get_messages_for_agent(current_agent_id),
            total_steps=len(self._execution_history) + 1,
            current_step_index=current_step_index,
        )

    # ── Convenience methods ────────────────────────────────────

    def add_reasoning_step(self, step: str) -> None:
        self._intermediate_reasoning.append(step)

    def set_temp(self, key: str, value: Any) -> None:
        self._temp_variables[key] = value

    def get_temp(self, key: str, default: Any = None) -> Any:
        return self._temp_variables.get(key, default)

    # ── Memory interface ───────────────────────────────────────

    async def load(self) -> dict[str, Any]:
        return {
            "current_task": self._current_task,
            "retrieved_documents": self._retrieved_documents,
            "graph_facts": self._graph_facts,
            "intermediate_reasoning": self._intermediate_reasoning,
            "temp_variables": self._temp_variables,
            "execution_metadata": self._execution_metadata,
            "entity_mentions": self._entity_mentions,
            "resolved_entity": self._resolved_entity,
            "messages": [m.model_dump() for m in self._messages],
            "execution_history": list(self._execution_history),
        }

    async def save(self) -> None:
        """No-op — working memory is never persisted."""

    async def append(self, entry: Any) -> None:
        """Add an entry.

        Supported entry types:
        - ``{"type": "reasoning_step", "content": str}``
        - ``{"type": "temp_var", "key": str, "value": Any}``
        - ``{"type": "document", "document": UnifiedContextItem}``
        - ``{"type": "graph_fact", "fact": GraphFact}``
        - ``{"type": "entity_mention", "entity": dict}``
        - ``{"type": "resolved_entity", "entity": dict}``
        """
        entry_type = entry.get("type") if isinstance(entry, dict) else None
        if entry_type == "reasoning_step":
            self._intermediate_reasoning.append(entry["content"])
        elif entry_type == "temp_var":
            self._temp_variables[entry["key"]] = entry["value"]
        elif entry_type == "document":
            self._retrieved_documents.append(entry["document"])
        elif entry_type == "graph_fact":
            self._graph_facts.append(entry["fact"])
        elif entry_type == "entity_mention":
            self.add_entity_mention(entry["entity"])
        elif entry_type == "resolved_entity":
            self._resolved_entity = entry["entity"]
        elif entry_type == "agent_message":
            from app.agents.framework.collaboration.schemas import AgentMessage
            self._messages.append(AgentMessage(**entry["message"]))
        elif entry_type == "execution_snapshot":
            self._execution_history.append(entry["snapshot"])

    async def summarize(self, max_tokens: int = 2000) -> str:
        parts: list[str] = []
        if self._current_task:
            parts.append(f"Current task: {self._current_task}")
        if self._retrieved_documents:
            parts.append(
                f"Retrieved {len(self._retrieved_documents)} document(s)"
            )
        if self._graph_facts:
            parts.append(
                f"Loaded {len(self._graph_facts)} graph fact(s)"
            )
        if self._intermediate_reasoning:
            parts.append(
                f"Reasoning steps ({len(self._intermediate_reasoning)}): "
                + " | ".join(self._intermediate_reasoning[-3:])
            )
        if self._entity_mentions:
            mentions = ", ".join(
                f"{e.get('original', e['name'])} ({e.get('type', 'unknown')})"
                for e in self._entity_mentions
            )
            parts.append(f"Entity mentions: {mentions}")
        if self._resolved_entity:
            parts.append(
                f"Resolved entity: {self._resolved_entity.get('original', self._resolved_entity['name'])} "
                f"({self._resolved_entity.get('type', 'unknown')})"
            )
        if self._messages:
            parts.append(f"Collaboration messages: {len(self._messages)} message(s)")
        if self._execution_history:
            agents = ", ".join(s.get("agent_name", s.get("agent_id", "?")) for s in self._execution_history)
            parts.append(f"Prior agents: {agents}")
        return "\n".join(parts)

    async def search(self, query: str, limit: int = 10) -> list[Any]:
        q = query.lower()
        results: list[Any] = []
        for doc in self._retrieved_documents:
            if q in doc.content.lower():
                results.append(doc)
                if len(results) >= limit:
                    return results
        for fact in self._graph_facts:
            if q in fact.entity_name.lower() or q in (fact.related_entity or "").lower():
                results.append(fact)
                if len(results) >= limit:
                    return results
        return results

    async def clear(self) -> None:
        self._current_task = ""
        self._retrieved_documents = []
        self._graph_facts = []
        self._intermediate_reasoning = []
        self._temp_variables = {}
        self._execution_metadata = {}
        self._entity_mentions = []
        self._resolved_entity = None
        self._messages = []
        self._execution_history = []
