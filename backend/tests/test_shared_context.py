"""Tests for multi-agent shared context injection.

Covers:
- ConversationMemory.messages property
- MemoryManager.merge_into() populating scalar context fields
- AgentContext.build_shared_context_prompt() for every data type
- BaseAgent._inject_shared_context() setting metadata
- End-to-end shared context flow in PlanExecutor
"""
import uuid
from unittest.mock import AsyncMock

import pytest

from app.agents.framework.base import BaseAgent
from app.agents.framework.context import AgentContext
from app.agents.framework.factory import AgentFactory
from app.agents.framework.memory.conversation_memory import ConversationMemory
from app.agents.framework.memory.manager import MemoryManager
from app.agents.framework.memory.working_memory import WorkingMemory
from app.agents.framework.planner import ExecutionPlan, ExecutionStep, PlanExecutor
from app.agents.framework.registry import AgentRegistry
from app.agents.framework.response import AgentResponse
from app.schemas.hybrid import GraphFact, UnifiedContextItem
from app.schemas.memory import MemorySearchResult


# ── Test agents that inspect their context ──────────────────────────

class InspectAgent(BaseAgent):
    """Records the context it receives so tests can verify shared data."""

    agent_id = "inspect"
    name = "Inspect Agent"
    description = "Records context for test assertions."
    supported_tasks = ["test"]
    required_permissions = set()

    def __init__(self) -> None:
        self.received_ctx: AgentContext | None = None

    async def execute(self, context: AgentContext) -> AgentResponse:
        self.received_ctx = context
        wm = context.working_memory
        if wm is not None:
            wm.set_temp("inspect_finding", "analysed")
        shared = context.metadata.get("shared_context_prompt", "")
        has_collab = "collaboration_prompt" in context.metadata
        return AgentResponse(
            answer=f"inspect done; shared={bool(shared)}, collab={has_collab}",
            confidence=0.9,
        )


class ConsumerAgent(BaseAgent):
    """Reads from the shared context and working memory."""

    agent_id = "consumer"
    name = "Consumer Agent"
    description = "Consumes shared context."
    supported_tasks = ["consumer"]
    required_permissions = set()

    def __init__(self) -> None:
        self.received_ctx: AgentContext | None = None

    async def execute(self, context: AgentContext) -> AgentResponse:
        self.received_ctx = context
        shared = context.metadata.get("shared_context_prompt", "")
        collab = context.metadata.get("collaboration_prompt", "")
        prior = context.metadata.get("step_outputs", {})
        wm = context.working_memory
        prev_finding = wm.get_temp("inspect_finding", "") if wm is not None else ""
        return AgentResponse(
            answer=f"consumer sees: chat={bool(context.chat_history)}, "
                   f"shared={bool(shared)}, collab={bool(collab)}, "
                   f"prior={bool(prior)}, prev_finding={prev_finding}",
            confidence=0.85,
        )


# ── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def registry():
    r = AgentRegistry()
    r.register(InspectAgent())
    r.register(ConsumerAgent())
    return r


@pytest.fixture
def factory(registry):
    return AgentFactory(registry)


# ── ConversationMemory.messages property ───────────────────────────

class TestConversationMemoryMessages:
    @pytest.mark.asyncio
    async def test_messages_property_returns_loaded_messages(self):
        repo = AsyncMock()
        repo.get_conversation = AsyncMock(return_value=AsyncMock())
        repo.get_messages = AsyncMock(return_value=[
            AsyncMock(role="user", content="Hello"),
            AsyncMock(role="assistant", content="Hi there"),
        ])
        cm = ConversationMemory(repository=repo)
        cm.conversation_id = uuid.uuid4()

        loaded = await cm.load()
        assert len(loaded) == 2
        assert len(cm.messages) == 2
        assert cm.messages[0]["role"] == "user"
        assert cm.messages[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_messages_returns_copy(self):
        repo = AsyncMock()
        repo.get_conversation.return_value = AsyncMock()
        repo.get_messages.return_value = []
        cm = ConversationMemory(repository=repo)
        await cm.load()
        msgs = cm.messages
        msgs.append({"role": "user", "content": "injected"})
        assert len(cm.messages) == 0


# ── MemoryManager.merge_into() ─────────────────────────────────────

class TestMemoryManagerMergeInto:
    @pytest.mark.asyncio
    async def test_populates_chat_history(self):
        repo = AsyncMock()
        repo.get_conversation.return_value = AsyncMock()
        repo.get_messages.return_value = [
            AsyncMock(role="user", content="Question"),
        ]
        cm = ConversationMemory(repository=repo)
        mgr = MemoryManager(conversation_memory=cm, working_memory=WorkingMemory())
        await mgr.load_conversation(conversation_id=uuid.uuid4(), user_id="u1")

        ctx = AgentContext(user_id="u1", user_role="Admin")
        mgr.merge_into(ctx)

        assert len(ctx.chat_history) == 1
        assert ctx.chat_history[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_populates_retrieved_documents_from_working(self):
        mgr = MemoryManager(
            conversation_memory=ConversationMemory(repository=AsyncMock()),
            working_memory=WorkingMemory(),
        )
        doc = UnifiedContextItem(content="pump P-101 vibration", score=0.85)
        mgr.working.retrieved_documents = [doc]

        ctx = AgentContext(user_id="u1", user_role="Admin")
        mgr.merge_into(ctx)

        assert len(ctx.retrieved_documents) == 1
        assert ctx.retrieved_documents[0].content == "pump P-101 vibration"

    @pytest.mark.asyncio
    async def test_populates_graph_facts_from_working(self):
        mgr = MemoryManager(
            conversation_memory=ConversationMemory(repository=AsyncMock()),
            working_memory=WorkingMemory(),
        )
        fact = GraphFact(
            entity_name="P-101", entity_type="Pump",
            relationship_type="connected_to", related_entity="M-101",
        )
        mgr.working.graph_facts = [fact]

        ctx = AgentContext(user_id="u1", user_role="Admin")
        mgr.merge_into(ctx)

        assert len(ctx.graph_facts) == 1
        assert ctx.graph_facts[0].entity_name == "P-101"

    @pytest.mark.asyncio
    async def test_populates_retrieved_memories(self):
        mgr = MemoryManager(
            conversation_memory=ConversationMemory(repository=AsyncMock()),
            working_memory=WorkingMemory(),
        )
        mem = MemorySearchResult(
            memory_id="m1", type="observation", title="Pump issue",
            content="P-101 had vibration", importance=0.7, confidence=0.8,
            similarity_score=0.92,
        )
        mgr._retrieved_memories = [mem]

        ctx = AgentContext(user_id="u1", user_role="Admin")
        mgr.merge_into(ctx)

        assert len(ctx.retrieved_memories) == 1
        assert ctx.retrieved_memories[0].title == "Pump issue"


# ── AgentContext.build_shared_context_prompt() ──────────────────────

class TestBuildSharedContextPrompt:
    def test_empty_context_returns_empty_string(self):
        ctx = AgentContext(user_id="u1", user_role="Admin")
        prompt = ctx.build_shared_context_prompt()
        assert prompt == ""

    def test_includes_chat_history(self):
        ctx = AgentContext(
            user_id="u1", user_role="Admin",
            chat_history=[
                {"role": "user", "content": "What is the status of P-101?"},
                {"role": "assistant", "content": "P-101 is running normally."},
            ],
        )
        prompt = ctx.build_shared_context_prompt()
        assert "Conversation History" in prompt
        assert "What is the status of P-101?" in prompt

    def test_includes_retrieved_documents(self):
        ctx = AgentContext(user_id="u1", user_role="Admin")
        ctx.retrieved_documents = [
            UnifiedContextItem(content="Maintenance log for P-101", score=0.9),
        ]
        prompt = ctx.build_shared_context_prompt()
        assert "Retrieved Documents" in prompt
        assert "Maintenance log" in prompt

    def test_includes_graph_facts(self):
        ctx = AgentContext(user_id="u1", user_role="Admin")
        ctx.graph_facts = [
            GraphFact(entity_name="P-101", entity_type="Pump",
                      relationship_type="connected_to", related_entity="M-101"),
        ]
        prompt = ctx.build_shared_context_prompt()
        assert "Graph Facts" in prompt
        assert "P-101" in prompt
        assert "M-101" in prompt

    def test_includes_retrieved_memories(self):
        ctx = AgentContext(user_id="u1", user_role="Admin")
        ctx.retrieved_memories = [
            MemorySearchResult(
                memory_id="m1", type="insight", title="Previous RCA",
                content="RCA identified bearing wear", importance=0.8,
                confidence=0.9, similarity_score=0.85,
            ),
        ]
        prompt = ctx.build_shared_context_prompt()
        assert "Long-term Memories" in prompt
        assert "Previous RCA" in prompt

    def test_includes_entity_mentions(self):
        ctx = AgentContext(user_id="u1", user_role="Admin")
        ctx.working_memory = WorkingMemory()
        ctx.working_memory.add_entity_mention({"name": "P-101", "type": "equipment"})
        prompt = ctx.build_shared_context_prompt()
        assert "Known Entities" in prompt
        assert "P-101" in prompt

    def test_includes_scratchpad_temp_vars(self):
        ctx = AgentContext(user_id="u1", user_role="Admin")
        ctx.working_memory = WorkingMemory()
        ctx.working_memory.set_temp("asset_search_results", ["P-101", "M-101"])
        prompt = ctx.build_shared_context_prompt()
        assert "Agent Scratchpad" in prompt
        assert "asset_search_results" in prompt

    def test_includes_prior_step_outputs(self):
        ctx = AgentContext(
            user_id="u1", user_role="Admin",
            metadata={
                "step_outputs": {
                    "result_asset": {
                        "agent_id": "asset_intelligence",
                        "answer": "P-101 status: running",
                        "confidence": 0.9,
                    },
                },
            },
        )
        prompt = ctx.build_shared_context_prompt()
        assert "Prior Agent Outputs" in prompt
        assert "asset_intelligence" in prompt
        assert "running" in prompt


# ── BaseAgent._inject_shared_context() ─────────────────────────────

class TestInjectSharedContext:
    @pytest.mark.asyncio
    async def test_sets_shared_context_prompt_metadata(self):
        agent = InspectAgent()
        ctx = AgentContext(
            user_id="u1", user_role="Admin", question="test",
            chat_history=[{"role": "user", "content": "Hello"}],
            metadata={},
        )
        ctx.working_memory = WorkingMemory()

        await agent.prepare_context(ctx)

        assert "shared_context_prompt" in ctx.metadata
        assert "Conversation History" in ctx.metadata["shared_context_prompt"]

    @pytest.mark.asyncio
    async def test_noop_when_no_shared_data(self):
        agent = InspectAgent()
        ctx = AgentContext(user_id="u1", user_role="Admin", question="test", metadata={})
        ctx.working_memory = WorkingMemory()

        await agent.prepare_context(ctx)

        assert "shared_context_prompt" not in ctx.metadata

    @pytest.mark.asyncio
    async def test_also_injects_collaboration_context(self):
        agent = InspectAgent()
        ctx = AgentContext(user_id="u1", user_role="Admin", question="test", metadata={})
        ctx.working_memory = WorkingMemory()

        await agent.prepare_context(ctx)

        assert "collaboration_prompt" in ctx.metadata
        assert "No prior agents" in ctx.metadata["collaboration_prompt"]

    @pytest.mark.asyncio
    async def test_working_memory_not_required(self):
        agent = InspectAgent()
        ctx = AgentContext(
            user_id="u1", user_role="Admin", question="test",
            chat_history=[{"role": "user", "content": "Hi"}],
            metadata={},
        )
        ctx.working_memory = None

        await agent.prepare_context(ctx)

        assert "shared_context_prompt" in ctx.metadata
        # No working-memory sections, but chat_history is still there
        assert "Conversation History" in ctx.metadata["shared_context_prompt"]


# ── End-to-end PlanExecutor shared context flow ────────────────────

class TestPlanExecutorSharedContext:
    @staticmethod
    def _make_memory_manager():
        """Create a MemoryManager with a WorkingMemory but no real DB.
        
        ``load_conversation`` is a no-op when conversation_id is None,
        so this works for unit tests that don't need persisted history.
        """
        repo = AsyncMock()
        cm = ConversationMemory(repository=repo)
        return MemoryManager(
            conversation_memory=cm,
            working_memory=WorkingMemory(),
        )

    @staticmethod
    def _make_registry(*agents):
        r = AgentRegistry()
        for a in agents:
            r.register(a)
        return r

    @pytest.mark.asyncio
    async def test_single_agent_gets_no_shared_context(self):
        """A lone agent with no history has nothing to share."""
        agent = InspectAgent()
        reg = self._make_registry(agent)
        fac = AgentFactory(reg)

        plan = ExecutionPlan(
            goal="test",
            steps=[
                ExecutionStep(step_id="s1", description="inspect",
                            agent_id="inspect", output_key="result"),
            ],
        )

        executor = PlanExecutor(reg, fac, memory_manager=self._make_memory_manager())
        await executor.execute(
            plan=plan, question="analyse P-101",
            user_id="u1", user_role="Admin",
        )

        assert agent.received_ctx is not None
        # First agent has no prior outputs, so shared_context_prompt is empty
        assert agent.received_ctx.metadata.get("shared_context_prompt", "") == ""
        # Collaboration context exists even for first agent (shows "No prior agents")
        assert "collaboration_prompt" in agent.received_ctx.metadata
        assert "No prior agents" in agent.received_ctx.metadata["collaboration_prompt"]

    @pytest.mark.asyncio
    async def test_consumer_sees_scratchpad_and_prior_outputs(self):
        """A downstream agent sees temp vars + step_outputs from upstream."""
        inspect_agent = InspectAgent()
        consumer_agent = ConsumerAgent()
        reg = self._make_registry(inspect_agent, consumer_agent)
        fac = AgentFactory(reg)

        plan = ExecutionPlan(
            goal="test scratchpad sharing",
            steps=[
                ExecutionStep(step_id="s1", description="inspect",
                            agent_id="inspect", output_key="result_a"),
                ExecutionStep(step_id="s2", description="consume",
                            agent_id="consumer", depends_on=["s1"],
                            output_key="result_b"),
            ],
        )

        executor = PlanExecutor(reg, fac, memory_manager=self._make_memory_manager())
        await executor.execute(
            plan=plan, question="analyse P-101",
            user_id="u1", user_role="Admin",
        )

        assert consumer_agent.received_ctx is not None

        # Shared context includes prior step outputs
        shared = consumer_agent.received_ctx.metadata.get("shared_context_prompt", "")
        assert "Prior Agent Outputs" in shared
        assert "inspect" in shared

        # Working memory scratchpad: the inspect agent stored "inspect_finding"
        # via working_memory.set_temp() which is shared with consumer
        assert "inspect_finding" in shared
        assert "Agent Scratchpad" in shared

        # Step outputs metadata
        prior = consumer_agent.received_ctx.metadata.get("step_outputs", {})
        assert "result_a" in prior
        assert prior["result_a"]["agent_id"] == "inspect"

        # Collaboration context shows inspect agent's execution
        collab = consumer_agent.received_ctx.metadata.get("collaboration_prompt", "")
        assert "Inspect Agent" in collab or "inspect" in collab

    @pytest.mark.asyncio
    async def test_chat_history_in_context_with_memory_manager(self):
        """When a MemoryManager is provided, chat_history is populated."""
        mgr = self._make_memory_manager()
        agent = InspectAgent()
        reg = self._make_registry(agent)
        fac = AgentFactory(reg)

        plan = ExecutionPlan(
            goal="test",
            steps=[
                ExecutionStep(step_id="s1", description="inspect",
                            agent_id="inspect", output_key="result"),
            ],
        )

        executor = PlanExecutor(reg, fac, memory_manager=mgr)
        await executor.execute(
            plan=plan, question="analyse P-101",
            user_id="u1", user_role="Admin",
        )

        # Chat history is available (empty since no persisted history)
        assert agent.received_ctx is not None
        assert agent.received_ctx.chat_history == []

        # Working memory was merged into the context
        assert agent.received_ctx.working_memory is not None
        assert agent.received_ctx.conversation_memory is not None
