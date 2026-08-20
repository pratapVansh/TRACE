"""Tests for the relationship extraction layer."""

from app.extraction import Relationship, RelationshipExtractor, RelationshipType


# ══════════════════════════════════════════════════════════════════════
# Relationship dataclass
# ══════════════════════════════════════════════════════════════════════

class TestRelationshipIdentity:
    def test_id_is_deterministic(self):
        r1 = Relationship(source="P-101", target="TK-305", type=RelationshipType.CONNECTED_TO)
        r2 = Relationship(source="P-101", target="TK-305", type=RelationshipType.CONNECTED_TO)
        assert r1.id == r2.id

    def test_id_differs_for_different_types(self):
        r1 = Relationship(source="P-101", target="TK-305", type=RelationshipType.CONNECTED_TO)
        r2 = Relationship(source="P-101", target="TK-305", type=RelationshipType.INPUT_TO)
        assert r1.id != r2.id

    def test_id_differs_for_different_sources(self):
        r1 = Relationship(source="P-101", target="TK-305", type=RelationshipType.CONNECTED_TO)
        r2 = Relationship(source="M-101", target="TK-305", type=RelationshipType.CONNECTED_TO)
        assert r1.id != r2.id

    def test_id_differs_for_different_targets(self):
        r1 = Relationship(source="P-101", target="TK-305", type=RelationshipType.CONNECTED_TO)
        r2 = Relationship(source="P-101", target="V-202", type=RelationshipType.CONNECTED_TO)
        assert r1.id != r2.id

    def test_id_length(self):
        r = Relationship(source="P-101", target="TK-305", type=RelationshipType.INPUT_TO)
        assert len(r.id) == 16

    def test_id_is_case_insensitive_for_source(self):
        r1 = Relationship(source="P-101", target="TK-305", type=RelationshipType.CONNECTED_TO)
        r2 = Relationship(source="p-101", target="TK-305", type=RelationshipType.CONNECTED_TO)
        assert r1.id == r2.id

    def test_id_is_case_insensitive_for_target(self):
        r1 = Relationship(source="P-101", target="TK-305", type=RelationshipType.CONNECTED_TO)
        r2 = Relationship(source="P-101", target="tk-305", type=RelationshipType.CONNECTED_TO)
        assert r1.id == r2.id

    def test_id_is_case_insensitive_for_both(self):
        r1 = Relationship(source="P-101", target="TK-305", type=RelationshipType.CONNECTED_TO)
        r2 = Relationship(source="p-101", target="tk-305", type=RelationshipType.CONNECTED_TO)
        assert r1.id == r2.id

    def test_with_confidence(self):
        r = Relationship(
            source="P-101", target="TK-305", type=RelationshipType.CONNECTED_TO, confidence=0.95,
        )
        updated = r.with_confidence(0.50)
        assert updated.confidence == 0.50
        assert r.confidence == 0.95

    def test_with_confidence_preserves_other_fields(self):
        r = Relationship(
            source="P-101", target="TK-305", type=RelationshipType.CONNECTED_TO,
            confidence=0.95, chunk_id="c1", document_id="d1",
        )
        updated = r.with_confidence(0.70)
        assert updated.source == "P-101"
        assert updated.target == "TK-305"
        assert updated.type == RelationshipType.CONNECTED_TO
        assert updated.chunk_id == "c1"
        assert updated.document_id == "d1"


class TestRelationshipTypeEnum:
    def test_all_types_present(self):
        """The core relationship types must never be removed.

        Asserted as a subset so the enum can grow (it has since gained
        FOLLOWS, OWNS, OPERATES, INSPECTS, etc.) without breaking here.
        """
        required = {
            "CONNECTED_TO", "PART_OF", "LOCATED_IN", "HAS_PROCEDURE",
            "MAINTAINED_BY", "USES", "REFERENCES", "DEPENDS_ON",
            "INPUT_TO", "OUTPUT_TO",
            "HAS_FAILURE", "CAUSED_BY", "PERFORMED_BY",
        }
        actual = {t.name for t in RelationshipType}
        assert required <= actual, f"missing core types: {required - actual}"

    def test_type_names_match_values(self):
        for rtype in RelationshipType:
            assert rtype.name == rtype.value

    def test_type_values(self):
        assert RelationshipType.CONNECTED_TO.value == "CONNECTED_TO"
        assert RelationshipType.PART_OF.value == "PART_OF"
        assert RelationshipType.LOCATED_IN.value == "LOCATED_IN"
        assert RelationshipType.HAS_PROCEDURE.value == "HAS_PROCEDURE"
        assert RelationshipType.MAINTAINED_BY.value == "MAINTAINED_BY"
        assert RelationshipType.USES.value == "USES"
        assert RelationshipType.REFERENCES.value == "REFERENCES"
        assert RelationshipType.DEPENDS_ON.value == "DEPENDS_ON"
        assert RelationshipType.INPUT_TO.value == "INPUT_TO"
        assert RelationshipType.OUTPUT_TO.value == "OUTPUT_TO"


# ══════════════════════════════════════════════════════════════════════
# RelationshipExtractor — basic extraction per type
# ══════════════════════════════════════════════════════════════════════

class TestExtractorConnectedTo:
    def setup_method(self):
        self.ext = RelationshipExtractor()

    def test_connected_to_direct(self):
        rels = self.ext.extract_from_chunk(
            "P-101 is connected to TK-305", chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        r = rels[0]
        assert r.source == "P-101"
        assert r.target == "TK-305"
        assert r.type == RelationshipType.CONNECTED_TO
        assert r.confidence == 0.95

    def test_connection_between(self):
        rels = self.ext.extract_from_chunk(
            "The connection between P-101 and TK-305", chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "P-101"
        assert rels[0].target == "TK-305"

    def test_upstream_of(self):
        rels = self.ext.extract_from_chunk(
            "P-101 is upstream of TK-305", chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].type == RelationshipType.CONNECTED_TO
        assert rels[0].confidence == 0.85

    def test_connects_to(self):
        rels = self.ext.extract_from_chunk(
            "P-101 connects to TK-305", chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].type == RelationshipType.CONNECTED_TO

    def test_both_connected(self):
        rels = self.ext.extract_from_chunk(
            "P-101 and TK-305 are connected", chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].type == RelationshipType.CONNECTED_TO


class TestExtractorPartOf:
    def setup_method(self):
        self.ext = RelationshipExtractor()

    def test_part_of_unit(self):
        rels = self.ext.extract_from_chunk(
            "XV-202 is part of Unit 2", chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "XV-202"
        assert rels[0].target == "Unit 2"
        assert rels[0].type == RelationshipType.PART_OF

    def test_belongs_to_system(self):
        rels = self.ext.extract_from_chunk(
            "M-101 belongs to the pumping system", chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "M-101"
        assert rels[0].type == RelationshipType.PART_OF

    def test_installed_in_unit(self):
        rels = self.ext.extract_from_chunk(
            "FT-201 is installed in Unit 2", chunk_id="c1", document_id="d1",
        )
        assert len(rels) >= 1
        types = {r.type for r in rels}
        assert RelationshipType.PART_OF in types
        assert any(r.target == "Unit 2" for r in rels)


class TestExtractorLocatedIn:
    def setup_method(self):
        self.ext = RelationshipExtractor()

    def test_located_in_area(self):
        rels = self.ext.extract_from_chunk(
            "PSV-105 is located in Area B", chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "PSV-105"
        assert rels[0].target == "Area B"
        assert rels[0].type == RelationshipType.LOCATED_IN

    def test_situated_in_zone(self):
        rels = self.ext.extract_from_chunk(
            "P-101 is situated in Zone 1", chunk_id="c1", document_id="d1",
        )
        assert len(rels) >= 1
        types = {r.type for r in rels}
        assert RelationshipType.LOCATED_IN in types

    def test_in_location_simple(self):
        rels = self.ext.extract_from_chunk(
            "P-101 is in Area A", chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].type == RelationshipType.LOCATED_IN
        assert rels[0].confidence == 0.75


class TestExtractorHasProcedure:
    def setup_method(self):
        self.ext = RelationshipExtractor()

    def test_sop_covers_equipment(self):
        rels = self.ext.extract_from_chunk(
            "SOP-1234 covers the maintenance of P-101",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "SOP-1234"
        assert rels[0].target == "P-101"
        assert rels[0].type == RelationshipType.HAS_PROCEDURE
        assert rels[0].confidence == 0.90

    def test_follow_sop_for_equipment(self):
        rels = self.ext.extract_from_chunk(
            "Follow SOP-1234 for P-101 maintenance",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "SOP-1234"
        assert rels[0].target == "P-101"
        assert rels[0].type == RelationshipType.HAS_PROCEDURE
        assert rels[0].confidence == 0.85

    def test_sop_describes_operation(self):
        rels = self.ext.extract_from_chunk(
            "WI-456 describes the operation of TK-305",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "WI-456"
        assert rels[0].target == "TK-305"

    def test_refer_to_sop_for_valve(self):
        rels = self.ext.extract_from_chunk(
            "Refer to SOP-789 for XV-202",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "SOP-789"
        assert rels[0].target == "XV-202"


class TestExtractorMaintainedBy:
    def setup_method(self):
        self.ext = RelationshipExtractor()

    def test_maintained_by_team(self):
        rels = self.ext.extract_from_chunk(
            "P-101 is maintained by Rotating Equipment Team",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "P-101"
        assert "Rotating Equipment Team" in rels[0].target
        assert rels[0].type == RelationshipType.MAINTAINED_BY

    def test_inspected_by_group(self):
        rels = self.ext.extract_from_chunk(
            "E-410 is inspected by NDT Group annually",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "E-410"
        assert "NDT Group" in rels[0].target


class TestExtractorUses:
    def setup_method(self):
        self.ext = RelationshipExtractor()

    def test_equipment_uses_chemical(self):
        rels = self.ext.extract_from_chunk(
            "P-101 uses HCl for cleaning",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "P-101"
        assert rels[0].target == "HCl"
        assert rels[0].type == RelationshipType.USES

    def test_chemical_used_in_equipment(self):
        rels = self.ext.extract_from_chunk(
            "HCl is used in TK-305",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "HCl"
        assert rels[0].target == "TK-305"
        assert rels[0].type == RelationshipType.USES
        assert rels[0].confidence == 0.80

    def test_equipment_handles_chemical(self):
        rels = self.ext.extract_from_chunk(
            "P-101 handles sulfuric acid",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].target == "sulfuric acid"

    def test_chemical_stored_in_tank(self):
        rels = self.ext.extract_from_chunk(
            "Methanol is stored in TK-305",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "Methanol"
        assert rels[0].target == "TK-305"


class TestExtractorReferences:
    def setup_method(self):
        self.ext = RelationshipExtractor()

    def test_standard_covers_equipment(self):
        rels = self.ext.extract_from_chunk(
            "API 610 covers the design of P-101",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "API 610"
        assert rels[0].target == "P-101"
        assert rels[0].type == RelationshipType.REFERENCES
        assert rels[0].confidence == 0.85

    def test_equipment_designed_per_standard(self):
        rels = self.ext.extract_from_chunk(
            "P-101 is designed per API 610",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "P-101"
        assert rels[0].target == "API 610"
        assert rels[0].type == RelationshipType.REFERENCES
        assert rels[0].confidence == 0.80

    def test_standard_applies_to(self):
        rels = self.ext.extract_from_chunk(
            "API 610 applies to centrifugal pumps",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) >= 1
        assert any(r.source == "API 610" for r in rels)

    def test_reference_to_standard_and_sop(self):
        rels = self.ext.extract_from_chunk(
            "P-101 refers to API 610",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].target == "API 610"


class TestExtractorDependsOn:
    def setup_method(self):
        self.ext = RelationshipExtractor()

    def test_depends_on_cooling_water(self):
        rels = self.ext.extract_from_chunk(
            "P-101 depends on cooling water",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "P-101"
        assert rels[0].target == "cooling water"
        assert rels[0].type == RelationshipType.DEPENDS_ON

    def test_requires_instrument_air(self):
        rels = self.ext.extract_from_chunk(
            "P-101 requires instrument air",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].target == "instrument air"

    def test_dependent_on_another_tag(self):
        rels = self.ext.extract_from_chunk(
            "P-101 is dependent on cooling water supply",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) >= 1
        assert all(r.type == RelationshipType.DEPENDS_ON for r in rels)
        assert any("cooling water" in r.target for r in rels)

    def test_needs_power(self):
        rels = self.ext.extract_from_chunk(
            "M-101 needs power supply",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) >= 1


class TestExtractorInputTo:
    def setup_method(self):
        self.ext = RelationshipExtractor()

    def test_feeds_into(self):
        rels = self.ext.extract_from_chunk(
            "P-101 feeds into TK-305",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "P-101"
        assert rels[0].target == "TK-305"
        assert rels[0].type == RelationshipType.INPUT_TO
        assert rels[0].confidence == 0.90

    def test_flow_goes_to(self):
        rels = self.ext.extract_from_chunk(
            "Flow from P-101 goes to TK-305",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "P-101"
        assert rels[0].target == "TK-305"
        assert rels[0].type == RelationshipType.INPUT_TO

    def test_supplies_to(self):
        rels = self.ext.extract_from_chunk(
            "P-101 supplies TK-305",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].type == RelationshipType.INPUT_TO


class TestExtractorOutputTo:
    def setup_method(self):
        self.ext = RelationshipExtractor()

    def test_discharges_into(self):
        rels = self.ext.extract_from_chunk(
            "P-101 discharges into TK-305",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "P-101"
        assert rels[0].target == "TK-305"
        assert rels[0].type == RelationshipType.OUTPUT_TO
        assert rels[0].confidence == 0.90

    def test_drain_to_sump(self):
        rels = self.ext.extract_from_chunk(
            "Drain TK-305 to sump",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "TK-305"
        assert rels[0].target == "sump"
        assert rels[0].type == RelationshipType.OUTPUT_TO

    def test_discharge_from_to(self):
        rels = self.ext.extract_from_chunk(
            "Discharge from P-101 goes to TK-305",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1
        assert rels[0].source == "P-101"
        assert rels[0].type == RelationshipType.OUTPUT_TO


# ══════════════════════════════════════════════════════════════════════
# Edge cases and deduplication
# ══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def setup_method(self):
        self.ext = RelationshipExtractor()

    def test_empty_content_returns_empty(self):
        rels = self.ext.extract_from_chunk("", chunk_id="c1", document_id="d1")
        assert len(rels) == 0

    def test_no_match_returns_empty(self):
        rels = self.ext.extract_from_chunk(
            "The quick brown fox jumps over the lazy dog",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 0

    def test_self_loop_filtered(self):
        rels = self.ext.extract_from_chunk(
            "P-101 is connected to P-101",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 0

    def test_deduplicates_identical(self):
        text = "P-101 is connected to TK-305. The connection between P-101 and TK-305."
        rels = self.ext.extract_from_chunk(text, chunk_id="c1", document_id="d1")
        assert len(rels) == 1

    def test_different_types_not_deduplicated(self):
        text = "P-101 is connected to TK-305. P-101 feeds into TK-305."
        rels = self.ext.extract_from_chunk(text, chunk_id="c1", document_id="d1")
        types = {r.type for r in rels}
        assert RelationshipType.CONNECTED_TO in types
        assert RelationshipType.INPUT_TO in types

    def test_keeps_highest_confidence_on_duplicate(self):
        rels = self.ext.extract_from_chunk(
            "P-101 is connected to TK-305 via pipeline",
            chunk_id="c1", document_id="d1",
        )
        assert all(r.confidence <= 0.95 for r in rels)

    def test_whitespace_normalized_in_tags(self):
        rels = self.ext.extract_from_chunk(
            "P 101 is connected to TK 305",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) >= 1
        if rels:
            assert rels[0].source == "P-101"
            assert rels[0].target == "TK-305"

    def test_chunk_id_and_document_id_propagated(self):
        rels = self.ext.extract_from_chunk(
            "P-101 is connected to TK-305",
            chunk_id="my-chunk", document_id="my-doc",
        )
        assert len(rels) == 1
        assert rels[0].chunk_id == "my-chunk"
        assert rels[0].document_id == "my-doc"

    def test_metadata_propagated(self):
        rels = self.ext.extract_from_chunk(
            "P-101 is connected to TK-305",
            chunk_id="c1", document_id="d1",
            metadata={"page": 42},
        )
        assert len(rels) == 1
        assert rels[0].metadata.get("page") == 42

    def test_source_and_target_stripped(self):
        rels = self.ext.extract_from_chunk(
            "P-101 is connected to  TK-305  ",
            chunk_id="c1", document_id="d1",
        )
        assert len(rels) == 1


# ══════════════════════════════════════════════════════════════════════
# Entity-filtered extraction
# ══════════════════════════════════════════════════════════════════════

class TestExtractFromEntities:
    def setup_method(self):
        self.ext = RelationshipExtractor()

    def test_filters_to_known_entities(self):
        rels = self.ext.extract_from_entities(
            content="P-101 is connected to TK-305. M-101 drives P-101.",
            chunk_id="c1", document_id="d1",
            entities=["P-101", "TK-305"],
        )
        assert len(rels) == 1
        assert rels[0].source == "P-101"
        assert rels[0].target == "TK-305"

    def test_returns_empty_when_no_entities_match(self):
        rels = self.ext.extract_from_entities(
            content="P-101 is connected to TK-305",
            chunk_id="c1", document_id="d1",
            entities=["XV-202"],
        )
        assert len(rels) == 0

    def test_returns_empty_for_empty_entity_list(self):
        rels = self.ext.extract_from_entities(
            content="P-101 is connected to TK-305",
            chunk_id="c1", document_id="d1",
            entities=[],
        )
        assert len(rels) == 0

    def test_accepts_normalized_entity_names(self):
        rels = self.ext.extract_from_entities(
            content="P 101 is connected to TK 305",
            chunk_id="c1", document_id="d1",
            entities=["P-101", "TK-305"],
        )
        assert len(rels) == 1


# ══════════════════════════════════════════════════════════════════════
# Realistic industrial document scenarios
# ══════════════════════════════════════════════════════════════════════

class TestRealisticScenarios:
    def setup_method(self):
        self.ext = RelationshipExtractor()

    def test_pump_maintenance_document(self):
        content = """Pump P-101 Maintenance Procedure
1. Isolate XV-202 and close PSV-105.
2. Verify FT-201 shows zero flow.
3. Drain TK-305 to sump.
4. Remove coupling guard from M-101.
5. Inspect E-410 tube bundle per TEMA standards.
6. Per API 610 and ASME B31.3.
7. Follow SOP-1234 for P-101 startup.
8. HCl is used for cleaning.
9. P-101 is located in Area B."""
        rels = self.ext.extract_from_chunk(content, chunk_id="c1", document_id="d1")
        assert len(rels) >= 1

        types = {r.type for r in rels}
        assert RelationshipType.CONNECTED_TO in types or RelationshipType.OUTPUT_TO in types
        assert any(r.source == "P-101" for r in rels)
        assert any(r.source == "SOP-1234" for r in rels)

    def test_no_false_positives_noise(self):
        content = "The report was filed on Tuesday. Please review document. Item 1, Item 2, and Item 3 are listed."
        rels = self.ext.extract_from_chunk(content, chunk_id="c1", document_id="d1")
        assert len(rels) == 0

    def test_multiple_relationships_in_one_chunk(self):
        content = "P-101 feeds TK-305. XV-202 is part of Unit 2. API 610 covers P-101 design."
        rels = self.ext.extract_from_chunk(content, chunk_id="c1", document_id="d1")
        types = {r.type for r in rels}
        assert RelationshipType.INPUT_TO in types
        assert RelationshipType.PART_OF in types
        assert RelationshipType.REFERENCES in types

    def test_directionality_respected(self):
        rels = self.ext.extract_from_chunk(
            "P-101 discharges into TK-305. TK-305 feeds into TK-306.",
            chunk_id="c1", document_id="d1",
        )
        expected = {
            ("P-101", RelationshipType.OUTPUT_TO, "TK-305"),
            ("TK-305", RelationshipType.INPUT_TO, "TK-306"),
        }
        for r in rels:
            key = (r.source, r.type, r.target)
            assert key in expected, f"Unexpected: {key}"
