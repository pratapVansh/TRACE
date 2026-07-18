"""Tests for HybridRetriever, VectorRetriever, GraphRetriever, ContextMerger."""

from unittest.mock import AsyncMock, patch

import pytest

from app.graph.base import GraphStoreOperationError
from app.graph.graph_query import GraphQueryService
from app.schemas.graph import EntityResponse, NeighborResponse, RelationshipResponse
from app.schemas.hybrid import GraphFact, UnifiedContext, UnifiedContextItem
from app.schemas.retrieval import RetrievedChunk
from app.services.hybrid_retriever import (
    ContextMerger,
    GraphRetriever,
    HybridRetriever,
    VectorRetriever,
)
from app.services.vector_store import VectorStore, VectorStoreOperationError


# ══════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_vector_store() -> AsyncMock:
    return AsyncMock(spec=VectorStore)


@pytest.fixture
def mock_graph_query_service() -> AsyncMock:
    return AsyncMock(spec=GraphQueryService)


@pytest.fixture
def sample_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            score=0.92,
            document_id="doc1",
            document_name="proc.pdf",
            content="P-101 is a centrifugal pump.",
            page_number=5,
            chunk_index=2,
            metadata={"language": "en"},
        ),
        RetrievedChunk(
            score=0.85,
            document_id="doc1",
            document_name="proc.pdf",
            content="TK-305 is a storage tank.",
            page_number=6,
            chunk_index=3,
            metadata={"language": "en"},
        ),
        RetrievedChunk(
            score=0.70,
            document_id="doc2",
            document_name="piping.pdf",
            content="Pipe segments are labeled P-201 through P-210.",
            page_number=10,
            chunk_index=0,
            metadata={"language": "en"},
        ),
    ]


@pytest.fixture
def sample_entities() -> list[EntityResponse]:
    return [
        EntityResponse(
            id="ent1", name="P-101", type="Pump",
            confidence=0.95, source_document="proc.pdf",
        ),
        EntityResponse(
            id="ent2", name="TK-305", type="Tank",
            confidence=0.90, source_document="proc.pdf",
        ),
    ]


@pytest.fixture
def sample_graph_facts() -> list[GraphFact]:
    return [
        GraphFact(
            entity_name="P-101", entity_type="Pump",
            confidence=0.95, source_document="proc.pdf",
        ),
        GraphFact(
            entity_name="P-101", entity_type="Pump",
            relationship_type="CONNECTED_TO",
            related_entity="TK-305",
            confidence=0.90, source_document="proc.pdf",
        ),
        GraphFact(
            entity_name="TK-305", entity_type="Tank",
            confidence=0.90, source_document="proc.pdf",
        ),
    ]


# ══════════════════════════════════════════════════════════════════════
# VectorRetriever
# ══════════════════════════════════════════════════════════════════════

class TestVectorRetriever:
    @patch("app.services.hybrid_retriever._encode_batch_async")
    async def test_retrieve_returns_chunks(
        self,
        mock_encode: AsyncMock,
        mock_vector_store: AsyncMock,
    ) -> None:
        mock_encode.return_value = [[0.1, 0.2, 0.3]]
        mock_vector_store.search.return_value = [
            {"score": 0.92, "payload": {
                "document_id": "doc1", "filename": "proc.pdf",
                "content": "P-101 pump info", "page_number": 5,
                "chunk_index": 2, "metadata": {"language": "en"},
            }},
        ]

        retriever = VectorRetriever(vector_store=mock_vector_store)
        results = await retriever.retrieve("pump", top_k=5)

        assert len(results) == 1
        assert results[0].score == 0.92
        assert results[0].content == "P-101 pump info"
        assert results[0].document_name == "proc.pdf"
        assert results[0].chunk_index == 2
        mock_encode.assert_called_once_with(["pump"])
        mock_vector_store.search.assert_called_once_with(
            query_vector=[0.1, 0.2, 0.3], top_k=5,
        )

    @patch("app.services.hybrid_retriever._encode_batch_async")
    async def test_retrieve_empty(
        self,
        mock_encode: AsyncMock,
        mock_vector_store: AsyncMock,
    ) -> None:
        mock_encode.return_value = [[0.1, 0.2, 0.3]]
        mock_vector_store.search.return_value = []
        retriever = VectorRetriever(vector_store=mock_vector_store)
        results = await retriever.retrieve("unknown")
        assert results == []

    @patch("app.services.hybrid_retriever._encode_batch_async")
    async def test_retrieve_propagates_store_error(
        self,
        mock_encode: AsyncMock,
        mock_vector_store: AsyncMock,
    ) -> None:
        mock_encode.return_value = [[0.1, 0.2, 0.3]]
        mock_vector_store.search.side_effect = VectorStoreOperationError("Qdrant down")
        retriever = VectorRetriever(vector_store=mock_vector_store)
        with pytest.raises(VectorStoreOperationError):
            await retriever.retrieve("pump")

    @patch("app.services.hybrid_retriever._encode_batch_async")
    async def test_retrieve_maps_minimal_payload(
        self,
        mock_encode: AsyncMock,
        mock_vector_store: AsyncMock,
    ) -> None:
        mock_encode.return_value = [[0.1, 0.2, 0.3]]
        mock_vector_store.search.return_value = [
            {"score": 0.5, "payload": {}},
        ]
        retriever = VectorRetriever(vector_store=mock_vector_store)
        results = await retriever.retrieve("test")
        assert results[0].score == 0.5
        assert results[0].document_id == ""
        assert results[0].content == ""
        assert results[0].metadata == {}


# ══════════════════════════════════════════════════════════════════════
# GraphRetriever (M31: batch neighbors)
# ══════════════════════════════════════════════════════════════════════

def _neighbor(entity_id: str, entity_name: str, rel_type: str) -> NeighborResponse:
    return NeighborResponse(
        entity=EntityResponse(id=entity_id, name=entity_name, type="Tank",
                              source_document="proc.pdf"),
        relationship=RelationshipResponse(id="r1", type=rel_type,
                                          source=entity_id, target="ent1"),
    )


class TestGraphRetriever:
    async def test_retrieve_returns_facts(
        self,
        mock_graph_query_service: AsyncMock,
        sample_entities: list[EntityResponse],
    ) -> None:
        mock_graph_query_service.search_entities.return_value = (sample_entities, 2)
        mock_graph_query_service.get_neighbors_for_entities.return_value = {
            "ent1": [_neighbor("ent2", "TK-305", "CONNECTED_TO")],
            "ent2": [],
        }

        retriever = GraphRetriever(graph_query_service=mock_graph_query_service)
        facts = await retriever.retrieve("pump", top_k=5)

        assert len(facts) == 3
        mock_graph_query_service.search_entities.assert_called_once_with("pump", limit=5)
        mock_graph_query_service.get_neighbors_for_entities.assert_called_once_with(["ent1", "ent2"])

        entity_names = {f.entity_name for f in facts}
        rel_types = {f.relationship_type for f in facts if f.relationship_type}
        assert "P-101" in entity_names
        assert "TK-305" in entity_names
        assert "CONNECTED_TO" in rel_types

    async def test_retrieve_no_entities(
        self,
        mock_graph_query_service: AsyncMock,
    ) -> None:
        mock_graph_query_service.search_entities.return_value = ([], 0)

        retriever = GraphRetriever(graph_query_service=mock_graph_query_service)
        facts = await retriever.retrieve("zzzz")
        assert facts == []

    async def test_retrieve_deduplicates(
        self,
        mock_graph_query_service: AsyncMock,
    ) -> None:
        dup_entities = [
            EntityResponse(id="e1", name="P-101", type="Pump"),
            EntityResponse(id="e1", name="P-101", type="Pump"),
        ]
        mock_graph_query_service.search_entities.return_value = (dup_entities, 2)
        mock_graph_query_service.get_neighbors_for_entities.return_value = {"e1": []}

        retriever = GraphRetriever(graph_query_service=mock_graph_query_service)
        facts = await retriever.retrieve("P-101")
        assert len(facts) == 1
        assert facts[0].entity_name == "P-101"

    async def test_retrieve_no_neighbors(
        self,
        mock_graph_query_service: AsyncMock,
        sample_entities: list[EntityResponse],
    ) -> None:
        mock_graph_query_service.search_entities.return_value = (sample_entities[:1], 1)
        mock_graph_query_service.get_neighbors_for_entities.return_value = {"ent1": []}

        retriever = GraphRetriever(graph_query_service=mock_graph_query_service)
        facts = await retriever.retrieve("P-101")
        assert len(facts) == 1
        assert facts[0].entity_name == "P-101"
        assert facts[0].relationship_type is None

    async def test_retrieve_with_graph_error(
        self,
        mock_graph_query_service: AsyncMock,
    ) -> None:
        mock_graph_query_service.search_entities.side_effect = GraphStoreOperationError("Neo4j down")
        retriever = GraphRetriever(graph_query_service=mock_graph_query_service)
        with pytest.raises(GraphStoreOperationError):
            await retriever.retrieve("pump")


# ══════════════════════════════════════════════════════════════════════
# ContextMerger (H12 + M30)
# ══════════════════════════════════════════════════════════════════════

class TestContextMerger:
    def test_merge_attaches_graph_facts_to_matching_chunks(
        self,
        sample_chunks: list[RetrievedChunk],
        sample_graph_facts: list[GraphFact],
    ) -> None:
        merger = ContextMerger()
        result = merger.merge("pump", sample_chunks, sample_graph_facts, top_k=10)

        assert result.query == "pump"
        assert result.total == 3
        assert result.vector_count == 3
        assert result.graph_count == 0

        proc_items = [i for i in result.items if i.document_name == "proc.pdf"]
        for item in proc_items:
            assert len(item.graph_facts) > 0
            assert item.source == "merged"

    def test_merge_adds_graph_only_items(
        self,
        sample_chunks: list[RetrievedChunk],
    ) -> None:
        graph_only_fact = GraphFact(
            entity_name="V-101", entity_type="Valve",
            confidence=0.85, source_document="valves.pdf",
        )
        merger = ContextMerger()
        result = merger.merge("valve", sample_chunks, [graph_only_fact], top_k=10)

        assert result.total == 4
        assert result.vector_count == 3
        assert result.graph_count == 1

        graph_items = [i for i in result.items if i.source == "graph"]
        assert len(graph_items) == 1
        assert graph_items[0].document_name == "valves.pdf"
        assert len(graph_items[0].graph_facts) == 1
        assert graph_items[0].graph_facts[0].entity_name == "V-101"

    def test_merge_respects_top_k(
        self,
        sample_chunks: list[RetrievedChunk],
        sample_graph_facts: list[GraphFact],
    ) -> None:
        merger = ContextMerger()
        result = merger.merge("pump", sample_chunks, sample_graph_facts, top_k=2)
        assert result.total == 2

    def test_merge_empty_vector_results(
        self,
        sample_graph_facts: list[GraphFact],
    ) -> None:
        merger = ContextMerger()
        result = merger.merge("test", [], sample_graph_facts, top_k=10)

        assert result.vector_count == 0
        assert result.graph_count == 1
        assert result.total == 1
        assert result.items[0].source == "graph"

    def test_merge_empty_graph_results(
        self,
        sample_chunks: list[RetrievedChunk],
    ) -> None:
        merger = ContextMerger()
        result = merger.merge("test", sample_chunks, [], top_k=10)

        assert result.total == 3
        assert result.vector_count == 3
        assert result.graph_count == 0
        for item in result.items:
            assert item.source == "vector"
            assert item.graph_facts == []

    def test_merge_both_empty(self) -> None:
        merger = ContextMerger()
        result = merger.merge("test", [], [])
        assert result.total == 0
        assert result.vector_count == 0
        assert result.graph_count == 0
        assert result.items == []

    def test_merge_sorts_by_score_descending(
        self,
    ) -> None:
        chunks = [
            RetrievedChunk(score=0.5, document_id="d1", document_name="a.pdf",
                           content="low", metadata={}),
            RetrievedChunk(score=0.9, document_id="d2", document_name="b.pdf",
                           content="high", metadata={}),
            RetrievedChunk(score=0.7, document_id="d3", document_name="c.pdf",
                           content="mid", metadata={}),
        ]
        merger = ContextMerger()
        result = merger.merge("test", chunks, [], top_k=10)

        scores = [i.score for i in result.items]
        assert scores == sorted(scores, reverse=True)
        assert result.items[0].content == "high"

    def test_merge_document_name_matching(
        self,
    ) -> None:
        chunks = [
            RetrievedChunk(score=0.9, document_id="d1", document_name="report.pdf",
                           content="Piping info", metadata={}),
        ]
        facts = [
            GraphFact(entity_name="P-201", entity_type="Pipe",
                      confidence=0.90, source_document="report.pdf"),
            GraphFact(entity_name="V-101", entity_type="Valve",
                      confidence=0.85, source_document="report.pdf"),
        ]
        merger = ContextMerger()
        result = merger.merge("pipe", chunks, facts, top_k=10)

        assert len(result.items) == 1
        assert len(result.items[0].graph_facts) == 2
        assert result.items[0].source == "merged"

    def test_merge_document_name_case_insensitive(
        self,
    ) -> None:
        chunks = [
            RetrievedChunk(score=0.9, document_id="d1", document_name="Report.PDF",
                           content="Info", metadata={}),
        ]
        facts = [
            GraphFact(entity_name="P-201", entity_type="Pipe",
                      confidence=0.90, source_document="report.pdf"),
        ]
        merger = ContextMerger()
        result = merger.merge("test", chunks, facts, top_k=10)

        proc_items = [i for i in result.items if i.document_name == "Report.PDF"]
        assert len(proc_items) == 1
        # Document name matching is now case-insensitive,
        # so "Report.PDF" matches "report.pdf"
        assert len(proc_items[0].graph_facts) == 1

    def test_merge_with_empty_document_name_graph_fact(
        self,
    ) -> None:
        chunks = [
            RetrievedChunk(score=0.9, document_id="d1", document_name="",
                           content="Info", metadata={}),
        ]
        fact_no_doc = GraphFact(entity_name="X", entity_type="Y",
                                confidence=0.50, source_document="")
        merger = ContextMerger()
        result = merger.merge("test", chunks, [fact_no_doc], top_k=10)

        assert result.total >= 1
        for item in result.items:
            if item.source == "graph":
                assert item.document_name == ""

    # ── H12: content-based cross-referencing ────────────────

    def test_merge_cross_references_by_content(
        self,
    ) -> None:
        """H12: facts should attach to chunks when entity name appears in content."""
        chunks = [
            RetrievedChunk(score=0.80, document_id="d1", document_name="report.pdf",
                           content="The P-101 pump was overhauled.", metadata={}),
        ]
        # Fact has different source_document but entity name appears in content
        facts = [
            GraphFact(entity_name="P-101", entity_type="Pump",
                      confidence=0.95, source_document="other.pdf"),
        ]
        merger = ContextMerger()
        result = merger.merge("pump", chunks, facts, top_k=10)

        assert len(result.items[0].graph_facts) == 1
        assert result.items[0].graph_facts[0].entity_name == "P-101"

    def test_merge_cross_references_by_related_entity(
        self,
    ) -> None:
        """H12: facts attach via related_entity name in content."""
        chunks = [
            RetrievedChunk(score=0.85, document_id="d1", document_name="report.pdf",
                           content="TK-305 level reading is 50%.", metadata={}),
        ]
        facts = [
            GraphFact(entity_name="P-101", entity_type="Pump",
                      relationship_type="CONNECTED_TO", related_entity="TK-305",
                      confidence=0.90, source_document="report.pdf"),
        ]
        merger = ContextMerger()
        result = merger.merge("pump", chunks, facts, top_k=10)

        assert len(result.items[0].graph_facts) == 1

    # ── M30: score normalization ────────────────────────────

    def test_merge_graph_only_score_from_confidence(
        self,
    ) -> None:
        """M30: graph-only items score derived from fact confidence."""
        facts = [
            GraphFact(entity_name="V-101", entity_type="Valve",
                      confidence=0.95, source_document="valves.pdf"),
        ]
        merger = ContextMerger()
        result = merger.merge("test", [], facts, top_k=10)

        assert len(result.items) == 1
        # max_conf=0.95 → score = max(0.3, 0.95*0.7) = max(0.3, 0.665) = 0.665
        assert result.items[0].score == pytest.approx(0.665)
        assert result.items[0].source == "graph"

    def test_merge_graph_only_low_confidence_min_score(
        self,
    ) -> None:
        """M30: graph-only item with very low confidence gets min score 0.3."""
        facts = [
            GraphFact(entity_name="X", entity_type="Y",
                      confidence=0.10, source_document="doc.pdf"),
        ]
        merger = ContextMerger()
        result = merger.merge("test", [], facts, top_k=10)

        assert result.items[0].score == 0.3  # max(0.3, 0.1*0.7) = max(0.3, 0.07) = 0.3

    def test_merge_combined_score_with_graph(
        self,
    ) -> None:
        """M30: merged items get score = max(vector_score, max_fact_conf * 0.8)."""
        chunks = [
            RetrievedChunk(score=0.70, document_id="d1", document_name="a.pdf",
                           content="P-101 is running.", metadata={}),
        ]
        facts = [
            GraphFact(entity_name="P-101", entity_type="Pump",
                      confidence=0.95, source_document="a.pdf"),
        ]
        merger = ContextMerger()
        result = merger.merge("test", chunks, facts, top_k=10)

        # max(0.70, 0.95*0.8) = max(0.70, 0.76) = 0.76
        assert result.items[0].score == 0.76


# ══════════════════════════════════════════════════════════════════════
# HybridRetriever (orchestrator)
# ══════════════════════════════════════════════════════════════════════

class TestHybridRetriever:
    async def test_retrieve_runs_both_retrievers(
        self,
        sample_chunks: list[RetrievedChunk],
        sample_graph_facts: list[GraphFact],
    ) -> None:
        mock_vr = AsyncMock(spec=VectorRetriever)
        mock_gr = AsyncMock(spec=GraphRetriever)
        mock_cm = AsyncMock(spec=ContextMerger)

        mock_vr.retrieve.return_value = sample_chunks
        mock_gr.retrieve.return_value = sample_graph_facts

        expected = UnifiedContext(query="pump", items=[], total=0, vector_count=0, graph_count=0)
        mock_cm.merge.return_value = expected

        hybrid = HybridRetriever(
            vector_retriever=mock_vr,
            graph_retriever=mock_gr,
            context_merger=mock_cm,
        )

        result = await hybrid.retrieve("pump", top_k=8, vector_top_k=5, graph_top_k=3)

        assert result is expected
        mock_vr.retrieve.assert_awaited_once_with("pump", 5)
        mock_gr.retrieve.assert_awaited_once_with("pump", 3)
        mock_cm.merge.assert_called_once_with("pump", sample_chunks, sample_graph_facts, 8)

    async def test_retrieve_with_empty_results(
        self,
    ) -> None:
        mock_vr = AsyncMock(spec=VectorRetriever)
        mock_gr = AsyncMock(spec=GraphRetriever)
        mock_cm = AsyncMock(spec=ContextMerger)

        mock_vr.retrieve.return_value = []
        mock_gr.retrieve.return_value = []
        mock_cm.merge.return_value = UnifiedContext(
            query="unknown", items=[], total=0, vector_count=0, graph_count=0,
        )

        hybrid = HybridRetriever(
            vector_retriever=mock_vr,
            graph_retriever=mock_gr,
            context_merger=mock_cm,
        )

        result = await hybrid.retrieve("unknown")
        assert result.total == 0

    async def test_retrieve_propagates_vector_error(
        self,
    ) -> None:
        mock_vr = AsyncMock(spec=VectorRetriever)
        mock_gr = AsyncMock(spec=GraphRetriever)
        mock_cm = AsyncMock(spec=ContextMerger)

        mock_vr.retrieve.side_effect = VectorStoreOperationError("Qdrant down")

        hybrid = HybridRetriever(
            vector_retriever=mock_vr,
            graph_retriever=mock_gr,
            context_merger=mock_cm,
        )

        with pytest.raises(VectorStoreOperationError):
            await hybrid.retrieve("pump")

    async def test_retrieve_propagates_graph_error(
        self,
    ) -> None:
        mock_vr = AsyncMock(spec=VectorRetriever)
        mock_gr = AsyncMock(spec=GraphRetriever)
        mock_cm = AsyncMock(spec=ContextMerger)

        mock_vr.retrieve.return_value = []
        mock_gr.retrieve.side_effect = GraphStoreOperationError("Neo4j down")

        hybrid = HybridRetriever(
            vector_retriever=mock_vr,
            graph_retriever=mock_gr,
            context_merger=mock_cm,
        )

        with pytest.raises(GraphStoreOperationError):
            await hybrid.retrieve("pump")

    async def test_retrieve_default_parameters(
        self,
    ) -> None:
        mock_vr = AsyncMock(spec=VectorRetriever)
        mock_gr = AsyncMock(spec=GraphRetriever)
        mock_cm = AsyncMock(spec=ContextMerger)

        mock_vr.retrieve.return_value = []
        mock_gr.retrieve.return_value = []
        mock_cm.merge.return_value = UnifiedContext(
            query="test", items=[], total=0, vector_count=0, graph_count=0,
        )

        hybrid = HybridRetriever(
            vector_retriever=mock_vr,
            graph_retriever=mock_gr,
            context_merger=mock_cm,
        )

        await hybrid.retrieve("test")
        mock_vr.retrieve.assert_awaited_once_with("test", 10)
        mock_gr.retrieve.assert_awaited_once_with("test", 5)
        mock_cm.merge.assert_called_once()
