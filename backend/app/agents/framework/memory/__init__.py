"""Agent memory layer — shared across all future AI Agents.

This package provides the abstract ``Memory`` interface plus the two
concrete implementations required by the current milestone:

* **ConversationMemory** — wraps ``ConversationRepository`` to expose
  existing conversation history in an agent-friendly format.  No new
  database tables are created.
* **WorkingMemory** — short-lived in-memory scratchpad for a single
  agent request.  Nothing is persisted.
* **SemanticMemory** — Stores reusable knowledge.
* **EpisodicMemory** — Remembers previous executions.
* **ReflectionMemory** — Stores execution feedback.
* **PlanningMemory** — Stores execution plans.
* **SharedAgentMemory** — Multiple agents can reuse evidence.

The ``MemoryManager`` orchestrates both types and merges them into
``AgentContext`` before agent execution.
"""

from app.agents.framework.memory.base import Memory
from app.agents.framework.memory.conversation_memory import ConversationMemory
from app.agents.framework.memory.manager import MemoryManager
from app.agents.framework.memory.summarizer import (
    ContextSummarizer,
    SimpleSummarizer,
)
from app.agents.framework.memory.working_memory import WorkingMemory
from app.agents.framework.memory.semantic_memory import SemanticMemory
from app.agents.framework.memory.episodic_memory import EpisodicMemory
from app.agents.framework.memory.reflection_memory import ReflectionMemory
from app.agents.framework.memory.planning_memory import PlanningMemory
from app.agents.framework.memory.shared_agent_memory import SharedAgentMemory


__all__ = [
    "ConversationMemory",
    "ContextSummarizer",
    "Memory",
    "MemoryManager",
    "SimpleSummarizer",
    "WorkingMemory",
    "SemanticMemory",
    "EpisodicMemory",
    "ReflectionMemory",
    "PlanningMemory",
    "SharedAgentMemory",
]
