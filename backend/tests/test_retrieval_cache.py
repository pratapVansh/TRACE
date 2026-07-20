"""Tests for the per-conversation RetrievalCache.

Covers:
- Basic storage, retrieval, clear
- Query coverage detection (is_query_cached / missing_terms)
- merge_search_results with deduplication
- Integration with search_hybrid (cache-hit shortcut)
- Integration with MemoryManager (cache attached via merge_into)
- Integration with ToolContext (cache accessible from tools)
"""
from unittest.mock import AsyncMock

import pytest

from app.agents.framework.context import AgentContext
from app.agents.framework.memory.conversation_memory import ConversationMemory
from app.agents.framework.memory.manager import MemoryManager
from app.agents.framework.memory.retrieval_cache import (
    RetrievalCacheEntry,
    clear_retrieval_cache,
    get_retrieval_cache,
)
from app.agents.framework.memory.working_memory import WorkingMemory
from app.agents.framework.tools.search_helper import search_hybrid, HybridSearchResult


# ── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the global cache registry before each test."""
    clear_retrieval_cache()
    yield


def make_doc(document_id: str, content: str = "test", score: float = 0.8) -> dict:
    return {
        "document_id": document_id,
        "content": content,
        "score": score,
        "document_name": f"doc_{document_id}",
        "source": "vector",
        "page_number": 1,
    }


def make_entity(entity_id: str, name: str = "Test", etype: str = "Equipment") -> dict:
    return {
        "id": entity_id,
        "name": name,
        "type": etype,
        "confidence": 0.9,
        "source_document": "",
        "aliases": [],
    }


# ── Basic CRUD ─────────────────────────────────────────────────────

class TestRetrievalCacheBasic:
    def test_get_or_create(self):
        entry = get_retrieval_cache("conv_1")
        assert entry.conversation_id == "conv_1"
        # Same conversation returns same entry
        assert get_retrieval_cache("conv_1") is entry

    def test_distinct_conversations(self):
        a = get_retrieval_cache("conv_a")
        b = get_retrieval_cache("conv_b")
        assert a is not b

    def test_clear_single(self):
        entry = get_retrieval_cache("conv_1")
        entry.merge_search_results("pump", [make_doc("d1")], [])
        assert entry.get_document_count() == 1

        clear_retrieval_cache("conv_1")
        # After clear, get_retrieval_cache returns a fresh entry
        fresh = get_retrieval_cache("conv_1")
        assert fresh.get_document_count() == 0

    def test_clear_all(self):
        get_retrieval_cache("conv_a").merge_search_results("a", [make_doc("d1")], [])
        get_retrieval_cache("conv_b").merge_search_results("b", [make_doc("d2")], [])
        clear_retrieval_cache()
        assert get_retrieval_cache("conv_a").get_document_count() == 0
        assert get_retrieval_cache("conv_b").get_document_count() == 0

    def test_to_dict(self):
        entry = get_retrieval_cache("conv_1")
        entry.merge_search_results("pump", [make_doc("d1")], [make_entity("e1")])
        d = entry.to_dict()
        assert d["conversation_id"] == "conv_1"
        assert d["document_count"] == 1
        assert d["entity_count"] == 1
        assert "d1" in d["document_ids"]
        assert "e1" in d["asset_ids"]


# ── Query coverage ─────────────────────────────────────────────────

class TestQueryCoverage:
    def test_is_query_cached_empty_cache(self):
        entry = RetrievalCacheEntry()
        assert not entry.is_query_cached("P-101 vibration")

    def test_is_query_cached_exact_match(self):
        entry = RetrievalCacheEntry()
        entry.merge_search_results("C-201 overview", [], [])
        assert entry.is_query_cached("C-201 overview")

    def test_is_query_cached_subset(self):
        entry = RetrievalCacheEntry()
        entry.merge_search_results("C-201 pump overview", [], [])
        # "C-201" is a subset of the cached terms
        assert entry.is_query_cached("C-201")

    def test_is_query_cached_new_terms_not_covered(self):
        entry = RetrievalCacheEntry()
        entry.merge_search_results("C-201", [], [])
        # "maintenance" was not in the original query
        assert not entry.is_query_cached("C-201 maintenance schedule")

    def test_missing_returns_new_terms(self):
        entry = RetrievalCacheEntry()
        entry.merge_search_results("C-201 pump", [], [])
        missing = entry.missing_terms("C-201 maintenance")
        assert "maintenance" in missing
        assert "C-201" not in missing  # already cached
        assert "pump" not in missing  # not in the new query

    def test_missing_all_new(self):
        entry = RetrievalCacheEntry()
        entry.merge_search_results("C-201", [], [])
        missing = entry.missing_terms("P-101 maintenance")
        assert missing == {"p-101", "maintenance"}


# ── merge_search_results ───────────────────────────────────────────

class TestMergeSearchResults:
    def test_merge_documents_and_entities(self):
        entry = RetrievalCacheEntry()
        entry.merge_search_results(
            "pump",
            [make_doc("d1"), make_doc("d2")],
            [make_entity("e1"), make_entity("e2")],
        )
        assert entry.get_document_count() == 2
        assert entry.get_entity_count() == 2
        assert "d1" in entry.document_ids
        assert "e1" in entry.asset_ids

    def test_deduplicates_documents_by_id(self):
        entry = RetrievalCacheEntry()
        entry.merge_search_results("pump", [make_doc("d1")], [])
        entry.merge_search_results("pump again", [make_doc("d1")], [])
        assert entry.get_document_count() == 1

    def test_deduplicates_entities_by_id(self):
        entry = RetrievalCacheEntry()
        entry.merge_search_results("pump", [], [make_entity("e1")])
        entry.merge_search_results("pump again", [], [make_entity("e1")])
        assert entry.get_entity_count() == 1

    def test_tracks_cached_queries(self):
        entry = RetrievalCacheEntry()
        entry.merge_search_results("first query", [], [])
        entry.merge_search_results("second query", [], [])
        assert entry.cached_queries == ["first query", "second query"]

    def test_has_asset(self):
        entry = RetrievalCacheEntry()
        entry.merge_search_results("pump", [], [make_entity("e1")])
        assert entry.has_asset("e1")
        assert not entry.has_asset("e2")


# ── search_hybrid integration ─────────────────────────────────────

class TestSearchHybridCache:
    @pytest.mark.asyncio
    async def test_cache_hit_skips_retrieval(self):
        """When cache covers a query, graph_svc and hybrid are NOT called."""
        cache = RetrievalCacheEntry()
        cache.merge_search_results("C-201", [make_doc("d1")], [make_entity("e1")])

        graph_svc = AsyncMock()
        hybrid = AsyncMock()

        result = await search_hybrid(
            query="C-201",
            graph_svc=graph_svc,
            hybrid=hybrid,
            cache=cache,
            tool_name="TestTool",
        )

        # Cache hit: neither service should have been called
        graph_svc.search_entities.assert_not_called()
        hybrid.retrieve.assert_not_called()
        assert result.total_documents == 1
        assert result.total_entities == 1

    @pytest.mark.asyncio
    async def test_cache_miss_triggers_retrieval(self):
        """When cache does NOT cover a query, retrieval runs normally."""
        cache = RetrievalCacheEntry()
        # cache has data about C-201 only
        cache.merge_search_results("C-201", [make_doc("d1")], [])

        graph_svc = AsyncMock()
        graph_svc.search_entities.return_value = ([AsyncMock(id="e2", name="M-101", type="Motor", confidence=0.9, source_document="", aliases=[])], 1)
        hybrid = AsyncMock()
        mock_item = AsyncMock()
        mock_item.content = "motor data"
        mock_item.score = 0.85
        mock_item.document_name = "motor_doc"
        mock_item.document_id = "d2"
        mock_item.page_number = 1
        mock_item.source = "vector"
        hybrid.retrieve.return_value = AsyncMock(items=[mock_item])

        result = await search_hybrid(
            query="M-101 motor",
            graph_svc=graph_svc,
            hybrid=hybrid,
            cache=cache,
            tool_name="TestTool",
        )

        # Cache miss: services were called
        graph_svc.search_entities.assert_called_once()
        hybrid.retrieve.assert_called_once()
        # New results were cached
        assert cache.has_asset("e2")
        assert "d2" in cache.document_ids

    @pytest.mark.asyncio
    async def test_cache_hit_without_graph_svc(self):
        """Cache hit works even when graph_svc is None."""
        cache = RetrievalCacheEntry()
        cache.merge_search_results("C-201", [make_doc("d1")], [make_entity("e1")])

        result = await search_hybrid(
            query="C-201",
            graph_svc=None,
            hybrid=None,
            cache=cache,
            tool_name="TestTool",
        )
        assert result.total_documents == 1
        assert result.total_entities == 1

    @pytest.mark.asyncio
    async def test_no_cache_passed(self):
        """When no cache is passed, retrieval works as before."""
        graph_svc = AsyncMock()
        graph_svc.search_entities.return_value = ([], 0)
        hybrid = AsyncMock()
        hybrid.retrieve.return_value = AsyncMock(items=[])

        result = await search_hybrid(
            query="C-201",
            graph_svc=graph_svc,
            hybrid=hybrid,
            cache=None,
            tool_name="TestTool",
        )
        graph_svc.search_entities.assert_called_once()
        hybrid.retrieve.assert_called_once()


# ── MemoryManager integration ─────────────────────────────────────

class TestMemoryManagerIntegration:
    @pytest.mark.asyncio
    async def test_merge_into_attaches_cache(self):
        """MemoryManager.merge_into() attaches retrieval cache to context."""
        repo = AsyncMock()
        cm = ConversationMemory(repository=repo)
        mgr = MemoryManager(
            conversation_memory=cm,
            working_memory=WorkingMemory(),
        )

        ctx = AgentContext(user_id="u1", user_role="Admin", conversation_id="conv_1")
        mgr.merge_into(ctx)

        assert ctx.retrieval_cache is not None
        assert ctx.retrieval_cache.conversation_id == "conv_1"

    @pytest.mark.asyncio
    async def test_same_conversation_returns_same_cache(self):
        """Two contexts with the same conversation_id share the cache."""
        repo = AsyncMock()
        cm1 = ConversationMemory(repository=repo)
        mgr1 = MemoryManager(conversation_memory=cm1, working_memory=WorkingMemory())
        ctx1 = AgentContext(user_id="u1", user_role="Admin", conversation_id="conv_1")
        mgr1.merge_into(ctx1)

        cm2 = ConversationMemory(repository=repo)
        mgr2 = MemoryManager(conversation_memory=cm2, working_memory=WorkingMemory())
        ctx2 = AgentContext(user_id="u1", user_role="Admin", conversation_id="conv_1")
        mgr2.merge_into(ctx2)

        assert ctx1.retrieval_cache is ctx2.retrieval_cache

    @pytest.mark.asyncio
    async def test_no_conversation_id_no_cache(self):
        """Without conversation_id, no cache is attached."""
        repo = AsyncMock()
        cm = ConversationMemory(repository=repo)
        mgr = MemoryManager(conversation_memory=cm, working_memory=WorkingMemory())

        ctx = AgentContext(user_id="u1", user_role="Admin")
        mgr.merge_into(ctx)

        assert ctx.retrieval_cache is None


# ── ToolContext integration ───────────────────────────────────────

class TestToolContextIntegration:
    def test_retrieval_cache_property(self):
        """ToolContext.retrieval_cache returns the AgentContext's cache."""
        from app.agents.framework.tools.context import ToolContext

        cache = RetrievalCacheEntry(conversation_id="conv_1")
        ctx = AgentContext(
            user_id="u1", user_role="Admin",
            conversation_id="conv_1",
        )
        ctx.retrieval_cache = cache

        tool_ctx = ToolContext.from_agent_context(ctx)
        assert tool_ctx.retrieval_cache is cache

    def test_retrieval_cache_none_when_no_agent_context(self):
        """Without _agent_context, retrieval_cache is None."""
        from app.agents.framework.tools.context import ToolContext

        tool_ctx = ToolContext(
            user_id="u1", user_role="Admin",
        )
        assert tool_ctx.retrieval_cache is None
