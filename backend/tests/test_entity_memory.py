"""Tests for EntityMemoryService."""
from app.services.entity_memory_service import EntityMemoryService


def test_extract_pump_with_tag():
    svc = EntityMemoryService()
    result = svc.extract_entities_from_text("What is wrong with Pump P101?")
    assert len(result) == 1
    assert result[0]["name"] == "P-101"
    assert result[0]["type"] == "Pump"
    assert result[0]["original"] == "Pump P101"


def test_extract_valve_with_tag():
    svc = EntityMemoryService()
    result = svc.extract_entities_from_text("Show maintenance for Valve V202.")
    assert len(result) == 1
    assert result[0]["name"] == "V-202"
    assert result[0]["type"] == "Valve"


def test_extract_boiler_with_single_digit():
    svc = EntityMemoryService()
    result = svc.extract_entities_from_text("Boiler B5 is overheating.")
    assert len(result) >= 1
    found = [e for e in result if "B-5" in e["name"] or "B5" in e["name"]]
    assert len(found) >= 1
    # Boiler word should map to equipment type
    assert found[0]["type"] in ("Equipment", "Heat Exchanger")


def test_extract_sop():
    svc = EntityMemoryService()
    result = svc.extract_entities_from_text("SOP-201 covers the procedure.")
    assert len(result) >= 1
    sop = [e for e in result if e["name"] == "SOP-201"]
    assert len(sop) >= 1
    assert sop[0]["type"] == "Procedure"


def test_extract_incident():
    svc = EntityMemoryService()
    result = svc.extract_entities_from_text("Investigate Incident-44.")
    assert len(result) >= 1
    inc = [e for e in result if e["name"] == "INCIDENT-44"]
    assert len(inc) >= 1
    assert inc[0]["type"] == "Failure"


def test_extract_bare_tag():
    svc = EntityMemoryService()
    result = svc.extract_entities_from_text("Check P-101 for leaks.")
    assert len(result) == 1
    assert result[0]["name"] == "P-101"
    assert result[0]["type"] == "Pump"


def test_no_duplicate_extraction():
    svc = EntityMemoryService()
    result = svc.extract_entities_from_text("Pump P101 and P-101 are the same.")
    assert len(result) == 1
    assert result[0]["name"] == "P-101"


def test_store_no_duplicates():
    svc = EntityMemoryService()
    svc.store_entities("conv-1", [{"name": "P-101", "type": "Pump", "original": "Pump P101", "confidence": 0.9}])
    new = svc.store_entities("conv-1", [{"name": "P-101", "type": "Pump", "original": "Pump P101", "confidence": 0.9}])
    assert len(new) == 0


def test_store_new_entities():
    svc = EntityMemoryService()
    svc.store_entities("conv-1", [{"name": "P-101", "type": "Pump", "original": "Pump P101", "confidence": 0.9}])
    new = svc.store_entities("conv-1", [{"name": "V-202", "type": "Valve", "original": "Valve V202", "confidence": 0.9}])
    assert len(new) == 1
    assert new[0]["name"] == "V-202"


def test_get_conversation_entities():
    svc = EntityMemoryService()
    svc.store_entities("conv-1", [{"name": "P-101", "type": "Pump", "original": "Pump P101", "confidence": 0.9}])
    entities = svc.get_conversation_entities("conv-1")
    assert len(entities) == 1
    assert entities[0]["name"] == "P-101"


def test_get_conversation_entities_empty():
    svc = EntityMemoryService()
    entities = svc.get_conversation_entities("nonexistent")
    assert entities == []


def test_resolve_direct_mention():
    svc = EntityMemoryService()
    entities = [
        {"name": "P-101", "type": "Pump", "original": "Pump P101", "confidence": 0.9},
        {"name": "V-202", "type": "Valve", "original": "Valve V202", "confidence": 0.9},
    ]
    resolved = svc.resolve_entity_reference("What about Valve V202?", entities)
    assert resolved is not None
    assert resolved["name"] == "V-202"


def test_resolve_ambiguous_it():
    svc = EntityMemoryService()
    entities = [
        {"name": "P-101", "type": "Pump", "original": "Pump P101", "confidence": 0.9},
    ]
    resolved = svc.resolve_entity_reference("What caused it?", entities)
    assert resolved is not None
    assert resolved["name"] == "P-101"


def test_resolve_ambiguous_the_pump():
    svc = EntityMemoryService()
    entities = [
        {"name": "P-101", "type": "Pump", "original": "Pump P101", "confidence": 0.9},
    ]
    resolved = svc.resolve_entity_reference("Show maintenance for the pump.", entities)
    assert resolved is not None
    assert resolved["name"] == "P-101"


def test_resolve_fallback_to_most_recent():
    svc = EntityMemoryService()
    entities = [
        {"name": "P-101", "type": "Pump", "original": "Pump P101", "confidence": 0.9},
        {"name": "V-202", "type": "Valve", "original": "Valve V202", "confidence": 0.9},
    ]
    resolved = svc.resolve_entity_reference("Compare with yesterday.", entities)
    assert resolved is not None
    assert resolved["name"] == "V-202"


def test_resolve_no_entities():
    svc = EntityMemoryService()
    resolved = svc.resolve_entity_reference("What caused it?", [])
    assert resolved is None


def test_clear_conversation():
    svc = EntityMemoryService()
    svc.store_entities("conv-1", [{"name": "P-101", "type": "Pump", "original": "Pump P101", "confidence": 0.9}])
    svc.clear_conversation("conv-1")
    assert svc.get_conversation_entities("conv-1") == []


def test_resolve_type_match_with_keyword():
    svc = EntityMemoryService()
    entities = [
        {"name": "P-101", "type": "Pump", "original": "Pump P101", "confidence": 0.9},
        {"name": "V-202", "type": "Valve", "original": "Valve V202", "confidence": 0.9},
        {"name": "TK-305", "type": "Tank", "original": "Tank TK-305", "confidence": 0.9},
    ]
    resolved = svc.resolve_entity_reference("Check the tank.", entities)
    assert resolved is not None
    # Tank is mentioned, so TK-305 should be resolved (most recent tank)
    assert resolved["name"] == "TK-305"


def test_full_conversation_flow():
    svc = EntityMemoryService()
    conv_id = "test-conv"

    # Turn 1: User asks about Pump P101
    entities = svc.extract_entities_from_text("What is wrong with Pump P101?")
    svc.store_entities(conv_id, entities)
    assert len(svc.get_conversation_entities(conv_id)) == 1

    # Turn 2: User asks "What caused it?"
    resolved = svc.resolve_entity_reference("What caused it?", svc.get_conversation_entities(conv_id))
    assert resolved is not None
    assert resolved["name"] == "P-101"

    # Turn 3: User asks "Compare with yesterday."
    resolved = svc.resolve_entity_reference("Compare with yesterday.", svc.get_conversation_entities(conv_id))
    assert resolved is not None
    assert resolved["name"] == "P-101"

    # Turn 4: User introduces new entity
    entities = svc.extract_entities_from_text("Also check Valve V202.")
    svc.store_entities(conv_id, entities)
    assert len(svc.get_conversation_entities(conv_id)) == 2

    # Turn 5: "Show maintenance." should resolve to V-202 (most recent)
    resolved = svc.resolve_entity_reference("Show maintenance.", svc.get_conversation_entities(conv_id))
    assert resolved is not None
    assert resolved["name"] == "V-202"
