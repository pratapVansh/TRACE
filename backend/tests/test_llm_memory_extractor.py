"""Tests for LLM-based memory extraction and the new MemoryService pipeline."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.llm_memory_extractor import (
    LLMMemoryExtractor,
    MemoryExtraction,
    _EXTRACTION_SYSTEM_PROMPT,
)
from app.schemas.memory import (
    MemoryCreate,
    MemoryResponse,
    MemorySearchResult,
    MemoryType,
    MemoryUpdate,
)
from app.services.memory_service import MemoryService


# ──────────────────────────────────────────────────────────────
# LLMMemoryExtractor unit tests
# ──────────────────────────────────────────────────────────────

class TestMemoryExtractionModel:
    def test_defaults(self):
        m = MemoryExtraction(title="T", summary="S", content="C")
        assert m.should_remember is True
        assert m.importance == 0.5
        assert m.confidence == 0.5
        assert m.category == "general"
        assert m.entities == []
        assert m.relationships == []

    def test_validates_ranges(self):
        with pytest.raises(Exception):
            MemoryExtraction(title="T", summary="S", content="C", importance=2.0)

    def test_full_extraction(self):
        m = MemoryExtraction(
            title="P-101 centrifugal pump specs",
            summary="P-101 is a centrifugal pump rated for 150 GPM at 50 PSI",
            content="P-101 is a centrifugal pump that handles 150 GPM at 50 PSI discharge pressure.",
            importance=0.85,
            confidence=0.9,
            category="asset_knowledge",
            entities=[{"name": "P-101", "type": "pump"}, {"name": "Centrifugal", "type": "pump_type"}],
            relationships=[{"source": "P-101", "target": "Centrifugal", "relation": "is_a"}],
        )
        assert m.should_remember is True
        assert m.importance == 0.85
        assert len(m.entities) == 2


class TestLLMMemoryExtractorInit:
    @pytest.mark.asyncio
    async def test_no_llm_returns_empty(self):
        ext = LLMMemoryExtractor(llm=None)
        result = await ext.extract("hello")
        assert result == []


class TestLLMMemoryExtractorParse:
    @pytest.fixture
    def extractor(self) -> LLMMemoryExtractor:
        return LLMMemoryExtractor(llm=MagicMock())

    def test_parse_empty_array(self, extractor):
        assert extractor._parse_response("[]") == []

    def test_parse_empty_string(self, extractor):
        assert extractor._parse_response("") == []

    def test_parse_code_fenced(self, extractor):
        raw = '```json\n[{"should_remember": true, "title": "Test", "summary": "S", "content": "C", "importance": 0.5, "confidence": 0.5}]\n```'
        results = extractor._parse_response(raw)
        assert len(results) == 1
        assert results[0].title == "Test"

    def test_parse_single_item(self, extractor):
        raw = json.dumps([{
            "should_remember": True,
            "title": "P-101 Spec",
            "summary": "P-101 is a centrifugal pump",
            "content": "P-101 is a centrifugal pump rated for 150 GPM.",
            "importance": 0.85,
            "confidence": 0.9,
            "category": "asset_knowledge",
            "entities": [{"name": "P-101", "type": "pump"}],
            "relationships": [],
        }])
        results = extractor._parse_response(raw)
        assert len(results) == 1
        assert results[0].title == "P-101 Spec"
        assert results[0].importance == 0.85
        assert len(results[0].entities) == 1

    def test_parse_multiple_items(self, extractor):
        raw = json.dumps([
            {
                "should_remember": True,
                "title": "Memory 1",
                "summary": "S1",
                "content": "C1",
                "importance": 0.5,
                "confidence": 0.5,
            },
            {
                "should_remember": True,
                "title": "Memory 2",
                "summary": "S2",
                "content": "C2",
                "importance": 0.7,
                "confidence": 0.6,
            },
        ])
        results = extractor._parse_response(raw)
        assert len(results) == 2

    def test_skips_not_remember(self, extractor):
        raw = json.dumps([
            {"should_remember": False, "title": "Skip", "summary": "S", "content": "C", "importance": 0.5, "confidence": 0.5},
            {"should_remember": True, "title": "Keep", "summary": "S", "content": "C", "importance": 0.5, "confidence": 0.5},
        ])
        results = extractor._parse_response(raw)
        assert len(results) == 1
        assert results[0].title == "Keep"

    def test_skips_invalid_items(self, extractor):
        raw = json.dumps([
            {"should_remember": True, "title": "Valid", "summary": "S", "content": "C", "importance": 0.5, "confidence": 0.5},
            {"should_remember": True},  # missing required fields
        ])
        results = extractor._parse_response(raw)
        assert len(results) == 1
        assert results[0].title == "Valid"

    def test_parse_not_json(self, extractor):
        assert extractor._parse_response("not json") == []

    def test_parse_not_list(self, extractor):
        assert extractor._parse_response('{"should_remember": true}') == []


class TestLLMMemoryExtractorIntegration:
    @pytest.fixture
    def mock_llm(self) -> AsyncMock:
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value=json.dumps([
            {
                "should_remember": True,
                "title": "P-101 is centrifugal",
                "summary": "The user stated P-101 is a centrifugal pump.",
                "content": "P-101 is a centrifugal pump that operates at 150 GPM.",
                "importance": 0.85,
                "confidence": 0.9,
                "category": "asset_knowledge",
                "entities": [{"name": "P-101", "type": "pump"}],
                "relationships": [],
            },
        ]))
        return llm

    @pytest.fixture
    def extractor(self, mock_llm) -> LLMMemoryExtractor:
        return LLMMemoryExtractor(llm=mock_llm)

    async def test_extract_calls_llm_with_prompt(self, extractor, mock_llm):
        results = await extractor.extract("User: What is P-101?\nAssistant: It is a centrifugal pump.")
        assert len(results) == 1
        assert results[0].title == "P-101 is centrifugal"
        mock_llm.generate.assert_awaited_once()
        args, kwargs = mock_llm.generate.call_args
        assert "User: What is P-101?" in kwargs["prompt"]
        assert _EXTRACTION_SYSTEM_PROMPT in kwargs["system_prompt"]

    async def test_extract_llm_failure_returns_empty(self):
        failing = AsyncMock()
        failing.generate = AsyncMock(side_effect=Exception("LLM down"))
        ext = LLMMemoryExtractor(llm=failing)
        results = await ext.extract("hello")
        assert results == []


# ──────────────────────────────────────────────────────────────
# MemoryService with LLM-based consolidation
# ──────────────────────────────────────────────────────────────

class TestMemoryServiceLLMConsolidation:
    @pytest.fixture
    def mock_repo(self) -> MagicMock:
        repo = MagicMock()
        # All repo methods that are awaited must be AsyncMock
        repo.search_by_keyword = AsyncMock(return_value=[])
        repo.create = AsyncMock()
        repo.get = AsyncMock()
        repo.update = AsyncMock()
        return repo

    @pytest.fixture
    def mock_embed(self) -> AsyncMock:
        fn = AsyncMock()
        fn.return_value = [[0.1, 0.2, 0.3]]
        return fn

    @pytest.fixture
    def mock_llm(self) -> AsyncMock:
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value=json.dumps([
            {
                "should_remember": True,
                "title": "P-101 Spec",
                "summary": "P-101 is a centrifugal pump rated for 150 GPM.",
                "content": "P-101 is a centrifugal pump that operates at 150 GPM.",
                "importance": 0.85,
                "confidence": 0.9,
                "category": "asset_knowledge",
                "entities": [{"name": "P-101", "type": "pump"}],
                "relationships": [],
            },
        ]))
        return llm

    @pytest.fixture
    def svc(self, mock_repo, mock_embed, mock_llm) -> MemoryService:
        return MemoryService(repository=mock_repo, embed_fn=mock_embed, llm=mock_llm)

    def _make_mem_model(self, **overrides) -> MagicMock:
        vals = dict(
            id=uuid.uuid4(),
            user_id=uuid.UUID(int=1),
            type="asset_knowledge",
            title="P-101 Spec",
            content="P-101 is a centrifugal pump that operates at 150 GPM.",
            summary="P-101 is a centrifugal pump rated for 150 GPM.",
            importance=0.85,
            confidence=0.9,
            status="active",
            source="auto:consolidation",
            category="asset_knowledge",
            entities=[{"name": "P-101", "type": "pump"}],
            relationships=[],
            metadata_={},
            embedding=[0.1, 0.2, 0.3],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            expires_at=None,
        )
        vals.update(overrides)
        return MagicMock(**vals)

    async def test_consolidate_extracts_and_creates_memory(self, svc, mock_repo):
        mem = self._make_mem_model()
        mock_repo.create.return_value = mem

        results = await svc.consolidate_conversation(
            conversation_text="User: My P-101 is a centrifugal pump.\nAssistant: Noted.",
            user_id="00000000-0000-0000-0000-000000000001",
        )

        assert len(results) == 1
        assert results[0].title == "P-101 Spec"
        mock_repo.create.assert_awaited_once()

    async def test_consolidate_with_existing_merges(self, svc, mock_repo):
        existing = self._make_mem_model(
            id=uuid.uuid4(),
            title="Old",
            content="Old content",
            summary="Old summary",
            importance=0.5,
            confidence=0.5,
            source="old",
            category="asset_knowledge",
        )
        mock_repo.search_by_keyword = AsyncMock(return_value=[existing])
        mock_repo.get.return_value = existing
        mock_repo.update.return_value = existing

        results = await svc.consolidate_conversation(
            conversation_text="User: P-101 is a centrifugal pump.\nAssistant: OK.",
            user_id="00000000-0000-0000-0000-000000000001",
        )

        assert len(results) == 1
        mock_repo.update.assert_called()
        # First update call has the blended importance
        first_call = mock_repo.update.call_args_list[0]
        update_payload = first_call[0][1]
        assert update_payload.importance is not None
        assert 0.5 < update_payload.importance < 0.85

    async def test_consolidate_no_extractor_returns_empty(self, mock_repo):
        svc = MemoryService(repository=mock_repo, embed_fn=None, llm=None)
        results = await svc.consolidate_conversation("hello", "uid")
        assert results == []

    async def test_consolidate_empty_text_returns_empty(self, svc):
        results = await svc.consolidate_conversation("", "uid")
        assert results == []

    async def test_consolidate_llm_extracts_nothing(self, svc, mock_llm):
        mock_llm.generate = AsyncMock(return_value="[]")
        results = await svc.consolidate_conversation("Hello", "uid")
        assert results == []


class TestMemoryServiceNewMethods:
    @pytest.fixture
    def mock_repo(self) -> MagicMock:
        repo = MagicMock()
        repo.get = AsyncMock()
        repo.update = AsyncMock()
        repo.search_by_entity = AsyncMock()
        return repo

    @pytest.fixture
    def svc(self, mock_repo) -> MemoryService:
        return MemoryService(repository=mock_repo)

    def _make_mem_model(self, **overrides) -> MagicMock:
        vals = dict(
            id=uuid.uuid4(),
            type="asset_knowledge",
            title="P-101 Spec",
            content="P-101 is centrifugal",
            summary="Summary",
            importance=0.8,
            confidence=0.7,
            status="active",
            source="test",
            category="asset_knowledge",
            entities=[{"name": "P-101", "type": "pump"}],
            relationships=[],
            metadata_={},
            embedding=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            expires_at=None,
        )
        vals.update(overrides)
        return MagicMock(**vals)

    async def test_search_by_entity(self, svc, mock_repo):
        mock_repo.search_by_entity = AsyncMock(return_value=[
            self._make_mem_model(title="P-101 Spec", content="P-101 is centrifugal"),
        ])
        results = await svc.search_by_entity("P-101", user_id="550e8400-e29b-41d4-a716-446655440000")
        assert len(results) == 1
        assert results[0].title == "P-101 Spec"
        mock_repo.search_by_entity.assert_awaited_once_with("P-101", user_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"), limit=10)

    async def test_resolve_conflict(self, svc, mock_repo):
        existing = self._make_mem_model(content="Old content", importance=0.5, confidence=0.5)
        mock_repo.get.return_value = existing
        mock_repo.update.return_value = existing

        ext = MemoryExtraction(
            title="New",
            summary="New summary",
            content="New content",
            importance=0.9,
            confidence=0.8,
        )
        result = await svc.resolve_conflict(str(existing.id), ext)
        assert result is not None
        assert mock_repo.update.call_count >= 1

    async def test_resolve_conflict_no_existing(self, svc, mock_repo):
        mock_repo.get.return_value = None
        ext = MemoryExtraction(title="T", summary="S", content="C")
        result = await svc.resolve_conflict(str(uuid.uuid4()), ext)
        assert result is None


class TestMemorySearchWithEntities:
    @pytest.fixture
    def mock_repo(self) -> MagicMock:
        repo = MagicMock()
        repo._cosine_similarity = staticmethod(lambda a, b: 0.95)
        repo.search_by_embedding = AsyncMock()
        repo.search_by_keyword = AsyncMock()
        repo.touch = AsyncMock()
        return repo

    @pytest.fixture
    def svc(self, mock_repo) -> MemoryService:
        # Provide embed_fn so search uses embedding-based path
        async def embed(texts):
            return [[0.1, 0.2, 0.3]]
        return MemoryService(repository=mock_repo, embed_fn=embed)

    async def test_search_includes_entities(self, svc, mock_repo):
        mem = MagicMock(
            id=uuid.uuid4(),
            type="asset_knowledge",
            title="P-101 Spec",
            content="P-101 is a pump",
            summary="Summary",
            importance=0.8,
            confidence=0.7,
            status="active",
            source="test",
            category="asset_knowledge",
            entities=[{"name": "P-101", "type": "pump"}],
            embedding=[0.1, 0.2, 0.3],
            created_at=datetime.now(timezone.utc),
        )
        mock_repo.search_by_embedding = AsyncMock(return_value=[mem])

        results = await svc.search(query="P-101", user_id="550e8400-e29b-41d4-a716-446655440000")
        assert len(results) == 1
        assert results[0].entities == [{"name": "P-101", "type": "pump"}]
        assert results[0].category == "asset_knowledge"


class TestMemorySearchResultSchema:
    def test_search_result_has_entities_and_category(self):
        r = MemorySearchResult(
            memory_id=str(uuid.uuid4()),
            type="asset_knowledge",
            title="Test",
            content="Content",
            importance=0.5,
            confidence=0.5,
            category="asset_knowledge",
            entities=[{"name": "P-101", "type": "pump"}],
        )
        assert r.category == "asset_knowledge"
        assert r.entities == [{"name": "P-101", "type": "pump"}]


class TestRepositorySearchByEntity:
    @pytest.mark.asyncio
    async def test_search_by_entity_query(self):
        """Verify the SQLAlchemy query logic in search_by_entity."""
        from app.repositories.memory_repository import MemoryRepository

        mock_session = MagicMock()
        # execute returns an awaitable that resolves to mock_result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        repo = MemoryRepository(mock_session)

        results = await repo.search_by_entity("P-101", user_id=uuid.UUID(int=1))
        assert results == []
        mock_session.execute.assert_awaited_once()


class TestChatServiceWiring:
    def test_memory_service_with_llm_creates_extractor(self):
        repo = MagicMock()
        llm = MagicMock()
        svc = MemoryService(repository=repo, llm=llm)
        assert svc._extractor is not None
        assert svc._extractor._llm is llm

    def test_memory_service_without_llm_no_extractor(self):
        repo = MagicMock()
        svc = MemoryService(repository=repo, llm=None)
        assert svc._extractor is None


class TestMemoryCreateSchema:
    def test_memory_create_with_new_fields(self):
        c = MemoryCreate(
            user_id="uid",
            type=MemoryType.ASSET_KNOWLEDGE,
            title="Test",
            content="Content",
            category="asset_knowledge",
            entities=[{"name": "P-101", "type": "pump"}],
            relationships=[{"source": "A", "target": "B", "relation": "connects"}],
        )
        assert c.category == "asset_knowledge"
        assert c.entities == [{"name": "P-101", "type": "pump"}]
        assert c.relationships == [{"source": "A", "target": "B", "relation": "connects"}]

    def test_memory_update_with_new_fields(self):
        u = MemoryUpdate(
            category="new_category",
            entities=[{"name": "E1", "type": "type1"}],
            relationships=[{"source": "X", "target": "Y", "relation": "Z"}],
        )
        assert u.category == "new_category"
        assert u.entities == [{"name": "E1", "type": "type1"}]
        assert u.relationships == [{"source": "X", "target": "Y", "relation": "Z"}]


class TestSystemPromptContent:
    def test_prompt_contains_instructions(self):
        assert "should_remember" in _EXTRACTION_SYSTEM_PROMPT
        assert "title" in _EXTRACTION_SYSTEM_PROMPT
        assert "summary" in _EXTRACTION_SYSTEM_PROMPT
        assert "importance" in _EXTRACTION_SYSTEM_PROMPT
        assert "confidence" in _EXTRACTION_SYSTEM_PROMPT
        assert "category" in _EXTRACTION_SYSTEM_PROMPT
        assert "entities" in _EXTRACTION_SYSTEM_PROMPT
        assert "relationships" in _EXTRACTION_SYSTEM_PROMPT
        assert "JSON array" in _EXTRACTION_SYSTEM_PROMPT
