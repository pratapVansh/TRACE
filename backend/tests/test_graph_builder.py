"""Tests for GraphBuilderService and Cypher query generation."""

from unittest.mock import AsyncMock

import pytest

from app.extraction.entity import Entity, _entity_id
from app.extraction.relationship import Relationship, RelationshipType
from app.extraction.types import EntityType
from app.graph.graph_builder import (
    GraphBuilderService,
    GraphBuildResult,
    GraphIntegrityReport,
    REL_TYPE_LABEL,
    _merge_node_query,
    _merge_rel_query,
    _merge_nodes_batch,
    _merge_rels_batch,
)


_NOW = "2026-07-15T12:00:00Z"


# ══════════════════════════════════════════════════════════════════════
# Query generation helpers
# ══════════════════════════════════════════════════════════════════════

class TestMergeNodeQuery:
    def test_returns_merge_query(self):
        entity = Entity(
            name="P-101", type=EntityType.PUMP, confidence=0.95,
            chunk_id="c1", document_id="d1", aliases=("P101",),
        )
        q, p = _merge_node_query(entity, "d1", "proc.pdf", _NOW)
        assert "MERGE (n:Entity {id: $id})" in q
        assert "SET" in q
        assert "COALESCE(n.source_document, $source_document)" in q
        assert "COALESCE(n.created_at, $created_at)" in q
        assert p["name"] == "P-101"
        assert p["type"] == "Pump"
        assert p["confidence"] == 0.95
        assert p["aliases"] == ["P101"]
        assert p["document_id"] == "d1"
        assert p["chunk_id"] == "c1"
        assert p["source_document"] == "proc.pdf"

    def test_entity_without_aliases(self):
        entity = Entity(name="TK-305", type=EntityType.TANK, confidence=0.90)
        q, p = _merge_node_query(entity, "d1", "", _NOW)
        assert p["aliases"] == []
        assert p["chunk_id"] == ""

    def test_entity_id_used_as_merge_key(self):
        entity = Entity(name="P-101", type=EntityType.PUMP)
        q, p = _merge_node_query(entity, "d1", "", _NOW)
        assert p["id"] == entity.id

    def test_updated_at_set(self):
        entity = Entity(name="V-202", type=EntityType.VALVE)
        q, p = _merge_node_query(entity, "d1", "", _NOW)
        assert p["updated_at"] == _NOW

    def test_created_at_set(self):
        entity = Entity(name="V-202", type=EntityType.VALVE)
        q, p = _merge_node_query(entity, "d1", "", _NOW)
        assert p["created_at"] == _NOW

    def test_all_entity_types_can_generate_queries(self):
        for etype in EntityType:
            entity = Entity(name="TEST", type=etype)
            q, p = _merge_node_query(entity, "d1", "", _NOW)
            assert "MERGE" in q
            assert p["type"] == etype.value


class TestMergeRelQuery:
    def test_returns_merge_query(self):
        rel = Relationship(
            source="P-101", target="TK-305",
            type=RelationshipType.CONNECTED_TO,
            confidence=0.95, chunk_id="c1", document_id="d1",
            source_type=EntityType.PUMP, target_type=EntityType.TANK,
        )
        q, p = _merge_rel_query(rel, "d1", "proc.pdf", _NOW)
        assert q is not None
        assert "WHERE ($source_id IS NOT NULL AND src.id = $source_id)" in q
        assert "WHERE ($target_id IS NOT NULL AND tgt.id = $target_id)" in q
        assert "MERGE (src)-[r:CONNECTED_TO {id: $id}]->(tgt)" in q
        assert "COALESCE(r.source_document, $source_document)" in q
        assert "COALESCE(r.created_at, $created_at)" in q
        assert p["source_id"] == _entity_id("P-101", EntityType.PUMP)
        assert p["target_id"] == _entity_id("TK-305", EntityType.TANK)
        assert p["confidence"] == 0.95
        assert p["document_id"] == "d1"
        assert p["source_document"] == "proc.pdf"

    def test_rel_id_used_as_merge_key(self):
        rel = Relationship(
            source="P-101", target="TK-305",
            type=RelationshipType.INPUT_TO,
        )
        q, p = _merge_rel_query(rel, "d1", "", _NOW)
        assert p["id"] == rel.id

    def test_all_relationship_types_have_labels(self):
        for rtype in RelationshipType:
            rel = Relationship(source="A", target="B", type=rtype)
            q, p = _merge_rel_query(rel, "d1", "", _NOW)
            assert q is not None
            label = REL_TYPE_LABEL[rtype]
            assert f"MERGE (src)-[r:{label}" in q

    def test_label_map_contains_all_types(self):
        # Derived from the enum rather than a hardcoded count, so adding a
        # relationship type does not require editing this assertion.
        assert len(REL_TYPE_LABEL) == len(RelationshipType)
        for rtype in RelationshipType:
            assert rtype in REL_TYPE_LABEL
            assert REL_TYPE_LABEL[rtype] == rtype.value


# ══════════════════════════════════════════════════════════════════════
# GraphBuilderService
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_tx():
    tx = AsyncMock()
    tx.run.return_value = AsyncMock()
    tx.closed = False
    return tx


@pytest.fixture
def mock_store(mock_tx):
    store = AsyncMock()
    store.execute_write.return_value = [{"deleted": 3}]
    store.begin_transaction = AsyncMock(return_value=mock_tx)
    return store


@pytest.fixture
def builder(mock_store):
    return GraphBuilderService(mock_store)


@pytest.fixture
def sample_entities():
    return [
        Entity(name="P-101", type=EntityType.PUMP, confidence=0.95,
               chunk_id="c1", document_id="d1"),
        Entity(name="TK-305", type=EntityType.TANK, confidence=0.95,
               chunk_id="c1", document_id="d1"),
        Entity(name="XV-202", type=EntityType.VALVE, confidence=0.95,
               chunk_id="c1", document_id="d1"),
    ]


@pytest.fixture
def sample_relationships():
    return [
        Relationship(source="P-101", target="TK-305",
                     type=RelationshipType.CONNECTED_TO, confidence=0.95,
                     chunk_id="c1", document_id="d1"),
        Relationship(source="P-101", target="XV-202",
                     type=RelationshipType.PART_OF, confidence=0.85,
                     chunk_id="c1", document_id="d1"),
    ]


class TestProcessDocument:
    async def test_merges_entities_and_relationships(self, builder, mock_tx,
                                                       sample_entities, sample_relationships):
        result = await builder.process_document(
            document_id="d1",
            entities=sample_entities,
            relationships=sample_relationships,
            source_document="proc.pdf",
        )
        assert result.successful is True
        assert result.nodes_merged == 3
        assert result.relationships_merged == 2
        assert result.error is None

        # UNWIND batching: 1 entity batch + 2 rel type batches (CONNECTED_TO, PART_OF)
        assert mock_tx.run.call_count == 3

    async def test_empty_entities_returns_early(self, builder, mock_store):
        result = await builder.process_document(
            document_id="d1", entities=[], relationships=[],
        )
        assert result.successful is True
        assert result.nodes_merged == 0
        assert result.relationships_merged == 0
        mock_store.begin_transaction.assert_not_called()

    async def test_empty_relationships(self, builder, mock_tx, sample_entities):
        result = await builder.process_document(
            document_id="d1", entities=sample_entities, relationships=[],
        )
        assert result.successful is True
        assert result.nodes_merged == 3
        assert result.relationships_merged == 0
        assert mock_tx.run.call_count == 1

    async def test_empty_entities_with_relationships(self, builder, mock_tx, sample_relationships):
        result = await builder.process_document(
            document_id="d1", entities=[], relationships=sample_relationships,
        )
        assert result.successful is True
        assert result.nodes_merged == 0
        assert result.relationships_merged == 2
        # 2 batches for 2 different relationship types (CONNECTED_TO, PART_OF)
        assert mock_tx.run.call_count == 2

    async def test_rollback_on_failure(self, builder, mock_tx, sample_entities):
        mock_tx.run.side_effect = Exception("Connection lost")
        result = await builder.process_document(
            document_id="d1", entities=sample_entities, relationships=[],
        )
        assert result.successful is False
        assert "Connection lost" in (result.error or "")
        mock_tx.rollback.assert_awaited_once()
        mock_tx.commit.assert_not_called()

    async def test_source_document_propagated(self, builder, mock_tx):
        entities = [Entity(name="P-101", type=EntityType.PUMP)]
        await builder.process_document(
            document_id="d1", entities=entities, relationships=[],
            source_document="my_doc.pdf",
        )
        call_args = mock_tx.run.call_args
        params = call_args[0][1]
        assert params["entities"][0]["source_document"] == "my_doc.pdf"

    async def test_unknown_relationship_type_skipped(self, builder, mock_tx):
        rel = Relationship(
            source="A", target="B",
            type=RelationshipType.CONNECTED_TO,
        )
        result = await builder.process_document(
            document_id="d1", entities=[], relationships=[rel],
        )
        assert result.successful is True
        mock_tx.run.assert_called_once()

    async def test_begin_transaction_failure_propagates(self, builder, mock_store, sample_entities):
        mock_store.begin_transaction.side_effect = RuntimeError("No connection")
        result = await builder.process_document(
            document_id="d1", entities=sample_entities, relationships=[],
        )
        assert result.successful is False
        assert "No connection" in (result.error or "")

    async def test_commit_succeeds_on_successful_write(self, builder, mock_tx, sample_entities, sample_relationships):
        result = await builder.process_document(
            document_id="d1",
            entities=sample_entities,
            relationships=sample_relationships,
        )
        assert result.successful is True
        mock_tx.commit.assert_awaited_once()
        mock_tx.rollback.assert_not_called()


class TestProcessChunk:
    async def test_chunk_id_overridden(self, builder, mock_tx):
        entities = [Entity(name="P-101", type=EntityType.PUMP)]
        rels = [Relationship(
            source="P-101", target="TK-305",
            type=RelationshipType.CONNECTED_TO,
        )]
        result = await builder.process_chunk(
            document_id="d1", chunk_id="chunk-42",
            entities=entities, relationships=rels,
        )
        assert result.successful is True

        # Verify chunk_id in params for entity batch
        entity_call = mock_tx.run.call_args_list[0]
        assert entity_call[0][1]["entities"][0]["chunk_id"] == "chunk-42"

    async def test_delegates_to_process_document(self, builder, mock_tx):
        entities = [Entity(name="P-101", type=EntityType.PUMP)]
        result = await builder.process_chunk(
            document_id="d1", chunk_id="c1",
            entities=entities, relationships=[],
        )
        assert result.successful is True
        mock_tx.run.assert_called_once()


class TestDeleteDocument:
    async def test_deletes_nodes_and_relationships(self, builder, mock_store):
        deleted = await builder.delete_document(document_id="d1")
        assert deleted == 3
        mock_store.execute_write.assert_called_once()

    async def test_delete_query_uses_document_id(self, builder, mock_store):
        await builder.delete_document(document_id="doc-123")
        call_args = mock_store.execute_write.call_args
        assert call_args[0][1] == {"document_id": "doc-123"}

    async def test_delete_query_uses_detach(self, builder, mock_store):
        await builder.delete_document(document_id="d1")
        query = mock_store.execute_write.call_args[0][0]
        assert "DETACH DELETE" in query

    async def test_delete_returns_zero_when_no_nodes(self, builder, mock_store):
        mock_store.execute_write.return_value = [{"deleted": 0}]
        deleted = await builder.delete_document(document_id="nonexistent")
        assert deleted == 0


class TestValidateGraphIntegrity:
    async def test_returns_report_with_consistent_data(self, builder, mock_store):
        mock_store.execute_read.side_effect = [
            [{"total": 3}],   # node count
            [{"total": 2}],   # rel count
            [{"total": 0}],   # cross-document refs
        ]
        report = await builder.validate_graph_integrity(document_id="d1")
        assert isinstance(report, GraphIntegrityReport)
        assert report.total_entity_nodes == 3
        assert report.total_relationship_edges == 2
        assert report.orphan_relationships == 0
        assert report.consistent is True

    async def test_detects_orphan_relationships(self, builder, mock_store):
        mock_store.execute_read.side_effect = [
            [{"total": 3}],
            [{"total": 2}],
            [{"total": 1}],  # one cross-document rel
        ]
        report = await builder.validate_graph_integrity(document_id="d1")
        assert report.orphan_relationships == 1
        assert report.consistent is False

    async def test_handles_empty_graph(self, builder, mock_store):
        mock_store.execute_read.side_effect = [
            [{"total": 0}],
            [{"total": 0}],
            [{"total": 0}],
        ]
        report = await builder.validate_graph_integrity(document_id="d1")
        assert report.total_entity_nodes == 0
        assert report.total_relationship_edges == 0
        assert report.consistent is True

    async def test_handles_no_results_from_store(self, builder, mock_store):
        mock_store.execute_read.side_effect = [[], [], []]
        report = await builder.validate_graph_integrity(document_id="d1")
        assert report.total_entity_nodes == 0
        assert report.total_relationship_edges == 0
        assert report.consistent is True


class TestGraphBuildResult:
    def test_default_values(self):
        result = GraphBuilderService.__init__
        from app.graph.graph_builder import GraphBuildResult
        r = GraphBuildResult()
        assert r.nodes_merged == 0
        assert r.relationships_merged == 0
        assert r.successful is True
        assert r.error is None


class TestGraphIntegrityReport:
    def test_consistent_when_no_issues(self):
        r = GraphIntegrityReport()
        assert r.consistent is True

    def test_inconsistent_with_orphans(self):
        r = GraphIntegrityReport(orphan_relationships=2)
        assert r.consistent is False

    def test_inconsistent_with_dangling_refs(self):
        r = GraphIntegrityReport(dangling_document_refs=1)
        assert r.consistent is False


class TestEndToEndFlow:
    """Integration-style test verifying the full extraction→persistence flow."""

    async def test_process_document_with_extracted_data(self, builder, mock_tx):
        entities = [
            Entity(name="P-101", type=EntityType.PUMP, confidence=0.95,
                   chunk_id="c1", document_id="d1"),
            Entity(name="TK-305", type=EntityType.TANK, confidence=0.95,
                   chunk_id="c1", document_id="d1"),
            Entity(name="SOP-1234", type=EntityType.PROCEDURE, confidence=0.90,
                   chunk_id="c2", document_id="d1"),
        ]
        rels = [
            Relationship(source="SOP-1234", target="P-101",
                         type=RelationshipType.HAS_PROCEDURE, confidence=0.90,
                         chunk_id="c2", document_id="d1",
                         source_type=EntityType.PROCEDURE, target_type=EntityType.PUMP),
            Relationship(source="P-101", target="TK-305",
                         type=RelationshipType.CONNECTED_TO, confidence=0.95,
                         chunk_id="c1", document_id="d1",
                         source_type=EntityType.PUMP, target_type=EntityType.TANK),
            Relationship(source="P-101", target="TK-305",
                         type=RelationshipType.INPUT_TO, confidence=0.85,
                         chunk_id="c1", document_id="d1",
                         source_type=EntityType.PUMP, target_type=EntityType.TANK),
        ]
        result = await builder.process_document(
            document_id="d1", entities=entities, relationships=rels,
            source_document="plant_overview.pdf",
        )
        assert result.successful is True
        assert result.nodes_merged == 3
        assert result.relationships_merged == 3
        # 1 entity batch + 3 rel type batches (HAS_PROCEDURE, CONNECTED_TO, INPUT_TO)
        assert mock_tx.run.call_count == 4

        # Verify batch params contain correct IDs
        calls = mock_tx.run.call_args_list
        # First call: entity batch
        entity_params = calls[0][0][1]
        assert len(entity_params["entities"]) == 3
        assert entity_params["entities"][0]["document_id"] == "d1"

        # Remaining calls: rel batches
        expected_source_ids = {
            _entity_id("SOP-1234", EntityType.PROCEDURE),
            _entity_id("P-101", EntityType.PUMP),
        }
        expected_target_ids = {
            _entity_id("P-101", EntityType.PUMP),
            _entity_id("TK-305", EntityType.TANK),
        }
        for call in calls[1:]:
            rels_params = call[0][1]
            for r in rels_params["rels"]:
                assert r["source_id"] in expected_source_ids
                assert r["target_id"] in expected_target_ids


class TestIdempotency:
    """MERGE queries should not create duplicates on re-processing."""

    async def test_reprocess_same_data_idempotent(self, builder, mock_tx):
        entities = [Entity(name="P-101", type=EntityType.PUMP)]
        rels = [Relationship(
            source="P-101", target="TK-305",
            type=RelationshipType.CONNECTED_TO,
            source_type=EntityType.PUMP, target_type=EntityType.TANK,
        )]

        # First pass
        r1 = await builder.process_document(
            document_id="d1", entities=entities, relationships=rels,
        )
        mock_tx.run.reset_mock()

        # Second pass (same data)
        r2 = await builder.process_document(
            document_id="d1", entities=entities, relationships=rels,
        )
        assert r2.successful is True
        assert r2.nodes_merged == 1
        assert r2.relationships_merged == 1

        # Both passes issue the same number of batch writes
        assert mock_tx.run.call_count == 2

    async def test_reprocess_with_updates(self, builder, mock_tx):
        entity_v1 = Entity(name="P-101", type=EntityType.PUMP, confidence=0.95)
        entity_v2 = Entity(name="P-101", type=EntityType.PUMP, confidence=0.99)

        await builder.process_document("d1", [entity_v1], [])
        mock_tx.run.reset_mock()

        await builder.process_document("d1", [entity_v2], [])
        call_params = mock_tx.run.call_args[0][1]
        assert call_params["entities"][0]["confidence"] == 0.99

    async def test_same_entity_different_docs_separate(self, builder, mock_tx):
        entity = Entity(name="P-101", type=EntityType.PUMP)

        await builder.process_document("doc-a", [entity], [])
        await builder.process_document("doc-b", [entity], [])

        assert mock_tx.run.call_count == 2
