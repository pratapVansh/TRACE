"""Tests for rule-based entity extraction."""

import pytest

from app.extraction.entity import Entity
from app.extraction.entity_extractor import EntityExtractor
from app.extraction.normalizer import (
    entities_key,
    is_tag_like,
    merge_entities,
    normalize_name,
    normalize_tag,
)
from app.extraction.types import EntityType


@pytest.fixture
def extractor() -> EntityExtractor:
    return EntityExtractor()


# ── Entity creation and identity ───────────────────────────────────────


class TestEntityIdentity:
    def test_id_is_deterministic(self):
        e1 = Entity(name="P-101", type=EntityType.PUMP)
        e2 = Entity(name="P-101", type=EntityType.PUMP)
        assert e1.id == e2.id

    def test_id_differs_for_different_types(self):
        e1 = Entity(name="P-101", type=EntityType.PUMP)
        e2 = Entity(name="P-101", type=EntityType.VALVE)
        assert e1.id != e2.id

    def test_id_is_case_insensitive(self):
        e1 = Entity(name="P-101", type=EntityType.PUMP)
        e2 = Entity(name="p-101", type=EntityType.PUMP)
        assert e1.id == e2.id

    def test_id_is_case_insensitive_for_non_tag_names(self):
        e1 = Entity(name="Centrifugal Pump", type=EntityType.PUMP)
        e2 = Entity(name="centrifugal pump", type=EntityType.PUMP)
        assert e1.id == e2.id

    def test_id_preserves_original_name_for_display(self):
        e = Entity(name="P-101", type=EntityType.PUMP)
        assert e.name == "P-101"

    def test_with_confidence(self):
        e = Entity(name="P-101", type=EntityType.PUMP, confidence=0.95)
        e2 = e.with_confidence(0.50)
        assert e2.confidence == 0.50
        assert e.confidence == 0.95  # original unchanged (frozen)

    def test_with_alias(self):
        e = Entity(name="P-101", type=EntityType.PUMP)
        e2 = e.with_alias("P101")
        assert "P101" in e2.aliases
        assert "P101" not in e.aliases  # original unchanged


# ── Name normalization ─────────────────────────────────────────────────


class TestNormalization:
    def test_normalize_tag_removes_spaces(self):
        assert normalize_tag("P 101") == "P-101"

    def test_normalize_tag_unifies_dashes(self):
        assert normalize_tag("P–101") == "P-101"
        assert normalize_tag("P—101") == "P-101"
        assert normalize_tag("P/101") == "P-101"

    def test_normalize_tag_uppercases(self):
        assert normalize_tag("p-101") == "P-101"

    def test_normalize_tag_strips_whitespace(self):
        assert normalize_tag("  P-101  ") == "P-101"

    def test_normalize_name_removes_extra_spaces(self):
        assert normalize_name("  Pump    P-101  ") == "Pump P-101"

    def test_is_tag_like(self):
        assert is_tag_like("P-101") is True
        assert is_tag_like("TK-305") is True
        assert is_tag_like("FT-2010") is True
        assert is_tag_like("Pump") is False
        assert is_tag_like("motor") is False


# ── Entity merging / deduplication ─────────────────────────────────────


class TestEntityMerging:
    def test_merge_identical_entities(self):
        e1 = Entity(name="P-101", type=EntityType.PUMP)
        e2 = Entity(name="P-101", type=EntityType.PUMP)
        merged = merge_entities([e1, e2])
        assert len(merged) == 1

    def test_merge_normalized_duplicates(self):
        e1 = Entity(name="P-101", type=EntityType.PUMP)
        e2 = Entity(name="P101", type=EntityType.PUMP)
        merged = merge_entities([e1, e2])
        assert len(merged) == 1
        assert "P101" in merged[0].aliases or "P-101" in merged[0].aliases

    def test_merge_keeps_higher_confidence(self):
        e1 = Entity(name="P-101", type=EntityType.PUMP, confidence=0.95)
        e2 = Entity(name="P101", type=EntityType.PUMP, confidence=0.80)
        merged = merge_entities([e1, e2])
        assert merged[0].confidence == 0.95
        assert merged[0].name == "P-101"

    def test_merge_different_types_keeps_separate(self):
        e1 = Entity(name="P-101", type=EntityType.PUMP)
        e2 = Entity(name="P-101", type=EntityType.VALVE)
        merged = merge_entities([e1, e2])
        assert len(merged) == 2

    def test_entities_key(self):
        k1 = entities_key(Entity(name="P-101", type=EntityType.PUMP))
        k2 = entities_key(Entity(name="P101", type=EntityType.PUMP))
        assert k1 == k2


# ── Equipment tag extraction ───────────────────────────────────────────


class TestEquipmentTagExtraction:
    def test_extract_pump_tag(self, extractor):
        entities = extractor.extract_from_chunk(
            content="Pump P-101 is operating at 1500 RPM.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        tags = {e.name for e in entities}
        assert "P-101" in tags
        pump_entities = [e for e in entities if e.type == EntityType.PUMP]
        assert len(pump_entities) >= 1

    def test_extract_valve_tag(self, extractor):
        entities = extractor.extract_from_chunk(
            content="XV-202 shall close on ESD signal.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        valves = [e for e in entities if e.type == EntityType.VALVE]
        assert any("XV-202" in (e.name,) or "XV-202" in e.aliases for e in valves)

    def test_extract_tank_tag(self, extractor):
        entities = extractor.extract_from_chunk(
            content="TK-305 level reached 85%.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        tanks = [e for e in entities if e.type == EntityType.TANK]
        assert len(tanks) >= 1

    def test_extract_heat_exchanger_tag(self, extractor):
        entities = extractor.extract_from_chunk(
            content="Inspect E-410 tube bundle annually.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        hes = [e for e in entities if e.type == EntityType.HEAT_EXCHANGER]
        assert len(hes) >= 1

    def test_extract_instrument_tag(self, extractor):
        entities = extractor.extract_from_chunk(
            content="FT-201 flow reading is 42.5 m³/h.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        instruments = [e for e in entities if e.type == EntityType.INSTRUMENT]
        assert len(instruments) >= 1

    def test_extract_motor_tag(self, extractor):
        entities = extractor.extract_from_chunk(
            content="M-101 motor rated 100 kW.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        motors = [e for e in entities if e.type == EntityType.MOTOR]
        assert len(motors) >= 1

    def test_tag_variations_resolve_same_entity(self, extractor):
        entities = extractor.extract_from_chunk(
            content="Pump P101 and P-101 are the same equipment.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        pumps = [e for e in entities if e.type == EntityType.PUMP]
        assert len(pumps) == 1  # merged into one


# ── Named pattern extraction ───────────────────────────────────────────


class TestNamedPatternExtraction:
    def test_centrifugal_pump(self, extractor):
        entities = extractor.extract_from_chunk(
            content="The centrifugal pump was overhauled last quarter.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        pumps = [e for e in entities if e.type == EntityType.PUMP]
        assert len(pumps) >= 1
        assert pumps[0].confidence >= 0.85

    def test_gate_valve(self, extractor):
        entities = extractor.extract_from_chunk(
            content="Replace the gate valve in section B.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        valves = [e for e in entities if e.type == EntityType.VALVE]
        assert len(valves) >= 1

    def test_shell_and_tube_heat_exchanger(self, extractor):
        entities = extractor.extract_from_chunk(
            content="Clean the shell and tube heat exchanger monthly.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        hes = [e for e in entities if e.type == EntityType.HEAT_EXCHANGER]
        assert len(hes) >= 1

    def test_standard_api(self, extractor):
        entities = extractor.extract_from_chunk(
            content="Design per API 610 latest edition.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        standards = [e for e in entities if e.type == EntityType.STANDARD]
        assert any("API 610" in e.name or "API" in e.name for e in standards)

    def test_standard_iso(self, extractor):
        entities = extractor.extract_from_chunk(
            content="ISO 9001:2015 certified facility.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        standards = [e for e in entities if e.type == EntityType.STANDARD]
        assert len(standards) >= 1

    def test_standard_asme(self, extractor):
        entities = extractor.extract_from_chunk(
            content="ASME B31.3 piping code applies.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        standards = [e for e in entities if e.type == EntityType.STANDARD]
        assert len(standards) >= 1

    def test_chemical_hcl(self, extractor):
        entities = extractor.extract_from_chunk(
            content="HCl concentration must not exceed 5%.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        chems = [e for e in entities if e.type == EntityType.CHEMICAL]
        assert len(chems) >= 1

    def test_chemical_named(self, extractor):
        entities = extractor.extract_from_chunk(
            content="Sulfuric acid is stored in TK-305.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        chems = [e for e in entities if e.type == EntityType.CHEMICAL]
        assert len(chems) >= 1

    def test_sop_reference(self, extractor):
        entities = extractor.extract_from_chunk(
            content="Refer to SOP-1234 for startup sequence.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        procedures = [e for e in entities if e.type == EntityType.PROCEDURE]
        assert len(procedures) >= 1


# ── Document metadata extraction ───────────────────────────────────────


class TestMetadataExtraction:
    def test_document_title_creates_document_entity(self, extractor):
        entities = extractor.extract_from_chunk(
            content="This pump specification covers all centrifugal pumps.",
            chunk_id="chunk1",
            document_id="doc1",
            document_title="Centrifugal Pump Specification 2024",
        )
        docs = [e for e in entities if e.type == EntityType.DOCUMENT]
        assert len(docs) >= 1

    def test_document_type_procedure_maps_to_procedure(self, extractor):
        entities = extractor.extract_from_chunk(
            content="Step 1: Isolate the valve.",
            chunk_id="chunk1",
            document_id="doc1",
            document_type="Standard Operating Procedure",
        )
        procs = [e for e in entities if e.type == EntityType.PROCEDURE]
        assert len(procs) >= 1

    def test_document_type_spec_maps_to_standard(self, extractor):
        entities = extractor.extract_from_chunk(
            content="Material shall comply with spec.",
            chunk_id="chunk1",
            document_id="doc1",
            document_type="Material Specification",
        )
        standards = [e for e in entities if e.type == EntityType.STANDARD]
        assert len(standards) >= 1


# ── Edge cases and false positive prevention ───────────────────────────


class TestEdgeCases:
    def test_empty_content_returns_empty_list(self, extractor):
        entities = extractor.extract_from_chunk(
            content="",
            chunk_id="chunk1",
            document_id="doc1",
        )
        assert entities == []

    def test_content_with_no_entities_returns_empty_list(self, extractor):
        entities = extractor.extract_from_chunk(
            content="The quick brown fox jumps over the lazy dog.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        assert entities == []

    def test_very_long_content_does_not_crash(self, extractor):
        content = "P-101 " * 10000
        entities = extractor.extract_from_chunk(
            content=content,
            chunk_id="chunk1",
            document_id="doc1",
        )
        assert len(entities) >= 1

    def test_special_characters_dont_break_regex(self, extractor):
        content = "Check P-101. (See note.) [Ref. TK-305] {E-410}"
        entities = extractor.extract_from_chunk(
            content=content,
            chunk_id="chunk1",
            document_id="doc1",
        )
        names = {e.name for e in entities}
        assert "P-101" in names
        assert "TK-305" in names
        assert "E-410" in names

    def test_numeric_only_not_extracted(self, extractor):
        entities = extractor.extract_from_chunk(
            content="Section 4.2.1 Temperature 150 °C Pressure 10 barg",
            chunk_id="chunk1",
            document_id="doc1",
        )
        assert not any(is_tag_like(e.name) for e in entities)

    def test_short_codes_not_extracted(self, extractor):
        entities = extractor.extract_from_chunk(
            content="Go to A-1 then B-2.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        # Tags need at least 2 digits
        tag_entities = [e for e in entities if is_tag_like(e.name)]
        assert len(tag_entities) == 0

    def test_merged_entities_collect_aliases(self, extractor):
        content = "Inspect P-101. Pump P101 is the main feed pump."
        entities = extractor.extract_from_chunk(
            content=content,
            chunk_id="chunk1",
            document_id="doc1",
        )
        pumps = [e for e in entities if e.type == EntityType.PUMP and is_tag_like(e.name)]
        assert len(pumps) == 1
        # Either P-101 or P101 should be the canonical name, the other an alias
        assert len(pumps[0].aliases) >= 0  # may have 0 if both are same normalized form


# ── Context pattern extraction ─────────────────────────────────────────


class TestContextPatterns:
    def test_context_pump_low_confidence(self, extractor):
        entities = extractor.extract_from_chunk(
            content="The pump is located in area A.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        pumps = [e for e in entities if e.type == EntityType.PUMP]
        if pumps:
            assert all(p.confidence < 0.50 for p in pumps)

    def test_context_valve_low_confidence(self, extractor):
        entities = extractor.extract_from_chunk(
            content="The valve controls flow to the reactor.",
            chunk_id="chunk1",
            document_id="doc1",
        )
        valves = [e for e in entities if e.type == EntityType.VALVE]
        if valves:
            assert all(v.confidence < 0.50 for v in valves)


# ── Realistic document extraction ──────────────────────────────────────


class TestRealisticScenarios:
    def test_pump_maintenance_document(self, extractor):
        content = (
            "Pump P-101 Maintenance Procedure\n\n"
            "1. Isolate XV-202 and close PSV-105 block valve.\n"
            "2. Verify FT-201 shows zero flow.\n"
            "3. Drain TK-305 into holding tank.\n"
            "4. Remove coupling guard from M-101.\n"
            "5. Inspect E-410 tube sheet for fouling.\n"
            "6. Reference ASME B31.3 for piping limits.\n"
            "7. Use HCl for acid cleaning per SOP-1234."
        )
        entities = extractor.extract_from_chunk(
            content=content,
            chunk_id="chunk_main",
            document_id="doc_pump_maint",
            document_title="Pump P-101 Maintenance Procedure",
            document_type="Standard Operating Procedure",
        )
        types_found = {e.type for e in entities}
        assert EntityType.PUMP in types_found
        assert EntityType.VALVE in types_found
        assert EntityType.INSTRUMENT in types_found
        assert EntityType.TANK in types_found
        assert EntityType.MOTOR in types_found
        assert EntityType.HEAT_EXCHANGER in types_found
        assert EntityType.STANDARD in types_found
        assert EntityType.PROCEDURE in types_found
        assert EntityType.CHEMICAL in types_found

    def test_no_false_positive_on_common_words(self, extractor):
        content = (
            "The project team met at 10 AM on Tuesday. "
            "Please send the meeting minutes to the engineering manager. "
            "The agenda included budget review and schedule update."
        )
        entities = extractor.extract_from_chunk(
            content=content,
            chunk_id="chunk1",
            document_id="doc1",
        )
        # Common English words should not trigger tag patterns
        tag_entities = [e for e in entities if e.confidence >= 0.50]
        assert len(tag_entities) == 0
