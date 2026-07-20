"""Tests for conversational user knowledge extraction and persistence."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.user_graph_service import (
    UserGraphService,
    _extract_equipment_tag,
    _user_entity_id,
    _NAME_PATTERN,
    _MANAGE_PATTERN,
    _WORK_AT_PATTERN,
    _ROLE_PATTERN,
)


class TestPatternExtraction:
    def test_name_pattern_my_name_is(self):
        m = _NAME_PATTERN.search("My name is Vansh")
        assert m is not None
        assert m.group(1) == "Vansh"

    def test_name_pattern_i_am(self):
        m = _NAME_PATTERN.search("I am Vansh")
        assert m is not None
        assert m.group(1) == "Vansh"

    def test_name_pattern_i_m(self):
        m = _NAME_PATTERN.search("I'm Vansh")
        assert m is not None
        assert m.group(1) == "Vansh"

    def test_name_pattern_two_words(self):
        m = _NAME_PATTERN.search("My name is Vansh Pratap")
        assert m is not None
        assert m.group(1) == "Vansh Pratap"

    def test_name_pattern_no_match(self):
        assert _NAME_PATTERN.search("What is the weather?") is None

    def test_manage_pattern_pump(self):
        m = _MANAGE_PATTERN.search("I manage Pump P101")
        assert m is not None
        assert "Pump P101" in m.group(1)

    def test_manage_pattern_valve(self):
        m = _MANAGE_PATTERN.search("I manage the Valve V-202")
        assert m is not None
        assert "Valve V-202" in m.group(1)

    def test_work_at_pattern(self):
        m = _WORK_AT_PATTERN.search("I work in Cracker Unit")
        assert m is not None
        assert m.group(1).strip() == "Cracker Unit"

    def test_work_at_for(self):
        m = _WORK_AT_PATTERN.search("I work for the Maintenance Department")
        assert m is not None
        assert "Maintenance Department" in m.group(1)

    def test_role_pattern(self):
        m = _ROLE_PATTERN.search("I am a Engineer")
        assert m is not None
        assert m.group(1).strip() == "Engineer"

    def test_role_pattern_am_an(self):
        m = _ROLE_PATTERN.search("I am an Operator")
        assert m is not None
        assert m.group(1).strip() == "Operator"

    def test_role_pattern_have_role(self):
        m = _ROLE_PATTERN.search("I have role Manager")
        assert m is not None
        assert m.group(1).strip() == "Manager"


class TestEquipmentTagExtraction:
    def test_pump_tag(self):
        tag, etype, match = _extract_equipment_tag("Pump P101")
        assert tag == "P-101"

    def test_valve_tag(self):
        tag, etype, match = _extract_equipment_tag("Valve V-202")
        assert tag == "V-202"

    def test_bare_tag(self):
        tag, etype, match = _extract_equipment_tag("P-101 is failing")
        assert tag == "P-101"

    def test_no_equipment(self):
        assert _extract_equipment_tag("Cracker Unit") is None

    def test_compressor_tag(self):
        tag, etype, match = _extract_equipment_tag("Compressor C-201")
        assert tag == "C-201"


class TestUserGraphServiceExtraction:
    @pytest.fixture
    def svc(self) -> UserGraphService:
        return UserGraphService(graph_store=None)

    def test_extract_name(self, svc):
        triples = svc._extract_triples("My name is Vansh")
        assert len(triples) == 1
        assert triples[0]["obj_name"] == "Vansh"
        assert triples[0]["rel_type"] is None  # user self-id

    def test_extract_name_and_work(self, svc):
        triples = svc._extract_triples("My name is Vansh. I work in Cracker Unit.")
        assert len(triples) == 2
        types = {t["rel_type"] for t in triples}
        assert None in types  # name
        assert "WORKS_AT" in types

    def test_extract_manage(self, svc):
        triples = svc._extract_triples("I manage Pump P101")
        assert len(triples) == 1
        assert triples[0]["rel_type"] == "OWNS"
        assert triples[0]["obj_name"] == "P-101"

    def test_extract_role(self, svc):
        triples = svc._extract_triples("I am a Senior Engineer")
        assert len(triples) == 1
        assert triples[0]["rel_type"] == "HAS_ROLE"
        assert triples[0]["obj_name"] == "Senior Engineer"

    def test_extract_full_conversation(self, svc):
        text = "My name is Vansh. I manage Pump P101. I work in Cracker Unit. I am an Engineer."
        triples = svc._extract_triples(text)
        assert len(triples) == 4
        rels = {t["rel_type"] for t in triples}
        assert rels == {None, "OWNS", "WORKS_AT", "HAS_ROLE"}

    def test_no_extraction_for_irrelevant(self, svc):
        triples = svc._extract_triples("What is the pressure rating of P-101?")
        assert len(triples) == 0


class TestUserGraphServiceEntityId:
    def test_user_entity_id_deterministic(self):
        uid = "550e8400-e29b-41d4-a716-446655440000"
        eid1 = _user_entity_id(uid)
        eid2 = _user_entity_id(uid)
        assert eid1 == eid2
        assert len(eid1) == 16

    def test_user_entity_id_different_users(self):
        eid1 = _user_entity_id("user-a")
        eid2 = _user_entity_id("user-b")
        assert eid1 != eid2


class TestUserGraphServicePersistence:
    @pytest.fixture
    def mock_graph(self) -> AsyncMock:
        graph = AsyncMock()
        graph.begin_transaction.return_value = AsyncMock()
        return graph

    @pytest.fixture
    def svc(self, mock_graph) -> UserGraphService:
        return UserGraphService(graph_store=mock_graph)

    async def test_process_message_with_name(self, svc, mock_graph):
        await svc.process_message(
            user_id="550e8400-e29b-41d4-a716-446655440000",
            text="My name is Vansh",
        )

        # Should create User node and commit
        tx = await mock_graph.begin_transaction()
        assert tx.run.await_count >= 1
        tx.commit.assert_awaited_once()

    async def test_process_message_irrelevant_skips_write(self, svc, mock_graph):
        await svc.process_message(
            user_id="id",
            text="What is the weather?",
        )

        # No extractions → no transaction
        tx = await mock_graph.begin_transaction()
        assert tx.run.await_count == 0

    async def test_process_message_with_all_extractions(self, svc, mock_graph):
        await svc.process_message(
            user_id="550e8400-e29b-41d4-a716-446655440000",
            text="My name is Vansh. I manage Pump P101. I work in Cracker Unit.",
        )

        tx = await mock_graph.begin_transaction()
        # User node + 2 object nodes + 2 relationships = 5 run calls
        assert tx.run.await_count >= 3
        tx.commit.assert_awaited_once()

    async def test_rollback_on_failure(self, svc, mock_graph):
        tx = await mock_graph.begin_transaction()
        tx.run.side_effect = Exception("Neo4j error")

        # Should not raise — non-fatal
        await svc.process_message(
            user_id="id",
            text="My name is Vansh",
        )

        tx.rollback.assert_awaited_once()

    async def test_no_graph_store_skips(self):
        svc = UserGraphService(graph_store=None)
        # Should not raise
        await svc.process_message(user_id="id", text="My name is Vansh")


class TestUserGraphServiceRetrieval:
    @pytest.fixture
    def mock_graph(self) -> AsyncMock:
        graph = AsyncMock()

        async def execute_read(query, params=None):
            return [
                {
                    "obj_name": "P-101",
                    "obj_type": "Pump",
                    "rel_type": "OWNS",
                    "confidence": 0.8,
                    "source_id": _user_entity_id("uid"),
                    "target_id": "abc123",
                },
                {
                    "obj_name": "Cracker Unit",
                    "obj_type": "Department",
                    "rel_type": "WORKS_AT",
                    "confidence": 0.85,
                    "source_id": _user_entity_id("uid"),
                    "target_id": "def456",
                },
            ]

        graph.execute_read = execute_read
        return graph

    @pytest.fixture
    def svc(self, mock_graph) -> UserGraphService:
        return UserGraphService(graph_store=mock_graph)

    async def test_get_user_knowledge_returns_facts(self, svc):
        facts = await svc.get_user_knowledge("uid")
        assert len(facts) == 2
        assert facts[0].relationship_type == "OWNS"
        assert facts[0].related_entity == "P-101"
        assert facts[1].relationship_type == "WORKS_AT"
        assert facts[1].related_entity == "Cracker Unit"

    async def test_get_user_knowledge_no_graph(self):
        svc = UserGraphService(graph_store=None)
        facts = await svc.get_user_knowledge("uid")
        assert facts == []


class TestUserGraphServiceChatServiceIntegration:
    @pytest.fixture
    def chat_service(self) -> MagicMock:
        from app.services.chat_service import ChatService

        svc = MagicMock(spec=ChatService)
        svc._user_graph = UserGraphService(graph_store=None)
        return svc

    async def test_user_graph_accepts_none(self):
        from app.services.chat_service import ChatService
        # Should not raise — user_graph defaults to None
        svc = ChatService(rag=MagicMock())
        assert svc._user_graph is None


class TestEntityTypeEnum:
    def test_new_types_exist(self):
        from app.extraction.types import EntityType
        assert EntityType.USER.value == "User"
        assert EntityType.DEPARTMENT.value == "Department"
        assert EntityType.ROLE.value == "Role"

    def test_new_relationship_types_exist(self):
        from app.extraction.relationship import RelationshipType
        assert RelationshipType.OWNS.value == "OWNS"
        assert RelationshipType.WORKS_AT.value == "WORKS_AT"
        assert RelationshipType.HAS_ROLE.value == "HAS_ROLE"

    def test_rel_type_label_in_graph_builder(self):
        from app.graph.graph_builder import REL_TYPE_LABEL
        from app.extraction.relationship import RelationshipType
        assert REL_TYPE_LABEL[RelationshipType.OWNS] == "OWNS"
        assert REL_TYPE_LABEL[RelationshipType.WORKS_AT] == "WORKS_AT"
        assert REL_TYPE_LABEL[RelationshipType.HAS_ROLE] == "HAS_ROLE"
