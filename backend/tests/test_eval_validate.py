"""Stage 5 golden-set schema and validator."""

import copy

import pytest
from pydantic import ValidationError

from eval.corpus import chunk_fingerprint
from eval.schema import CorpusManifest, GoldenItem, GoldenSet, load_golden_set, load_manifest
from eval.text import contains_phrase, normalize
from eval.validate import ValidationReport, validate_against_corpus, validate_structure

REVIEW = {"status": "approved", "reviewed_by": "tester", "reviewed_on": "2026-09-13", "notes": ""}


def _item(**overrides) -> dict:
    item = {
        "id": "S01",
        "type": "single_hop",
        "source": "new",
        "question": "What torque is the drain plug tightened to?",
        "history": [],
        "expected_docs": ["DOC-001_A.docx"],
        "expected_evidence": [{"doc": "DOC-001_A.docx", "contains": "tightened to 35 Nm"}],
        "expected_facts": [{"fact": "35 Nm", "any_of": ["35 Nm"]}],
        "must_refuse": False,
        "tags": [],
        "review": dict(REVIEW),
    }
    item.update(overrides)
    return item


def _manifest(chunks: dict[str, list[str]]) -> CorpusManifest:
    return CorpusManifest.model_validate({
        "manifest_version": 1,
        "frozen_at": "2026-09-13",
        "pipeline_at_freeze": {},
        "totals": {},
        "documents": [
            {
                "filename": name,
                "source_path": f"demo_dataset/{name}",
                "sha256": "0" * 64,
                "doc_type": "manual",
                "extraction_method": "python-docx",
                "chunk_count": len(contents),
                "extracted_chars": 1,
                "chunk_fingerprint": chunk_fingerprint(contents),
            }
            for name, contents in chunks.items()
        ],
    })


def _golden(items: list[dict]) -> GoldenSet:
    return GoldenSet.model_validate({
        "golden_set_version": 1,
        "corpus_manifest": "corpus_manifest.yaml",
        "drafted_by": "test",
        "drafted_on": "2026-09-13",
        "review_status": "reviewed",
        "items": items,
    })


class TestSchema:
    def test_valid_item_parses(self):
        assert GoldenItem.model_validate(_item()).id == "S01"

    def test_negative_must_refuse_and_have_no_expectations(self):
        with pytest.raises(ValidationError, match="must_refuse"):
            GoldenItem.model_validate(_item(id="N01", type="negative"))

    def test_multi_hop_needs_two_documents(self):
        with pytest.raises(ValidationError, match="at least two"):
            GoldenItem.model_validate(_item(id="M01", type="multi_hop"))

    def test_follow_up_needs_history_and_resolution(self):
        with pytest.raises(ValidationError, match="history and expected_resolution"):
            GoldenItem.model_validate(_item(id="F01", type="follow_up"))

    def test_history_must_alternate(self):
        history = [{"role": "user", "content": "a"}, {"role": "user", "content": "b"}]
        with pytest.raises(ValidationError, match="alternate"):
            GoldenItem.model_validate(
                _item(id="F01", type="follow_up", history=history, expected_resolution=["X"])
            )

    def test_evidence_must_come_from_an_expected_document(self):
        evidence = [{"doc": "OTHER.docx", "contains": "tightened to 35 Nm"}]
        with pytest.raises(ValidationError, match="not in expected_docs"):
            GoldenItem.model_validate(_item(expected_evidence=evidence))

    def test_unknown_fields_are_rejected(self):
        with pytest.raises(ValidationError):
            GoldenItem.model_validate(_item(expected_answer="35 Nm"))

    def test_duplicate_ids_rejected(self):
        with pytest.raises(ValidationError, match="duplicate"):
            _golden([_item(), _item()])


class TestCorpusValidation:
    CHUNKS = {"DOC-001_A.docx": ["Drain plug found loose -- tightened to 35 Nm.", "Oil replenished."]}

    def test_passes_when_evidence_and_facts_are_in_the_corpus(self):
        report = ValidationReport()
        validate_against_corpus(_golden([_item()]), _manifest(self.CHUNKS), self.CHUNKS, report)
        assert report.ok, report.errors

    def test_missing_evidence_is_an_error(self):
        item = _item(expected_evidence=[{"doc": "DOC-001_A.docx", "contains": "tightened to 40 Nm"}])
        report = ValidationReport()
        validate_against_corpus(_golden([item]), _manifest(self.CHUNKS), self.CHUNKS, report)
        assert any("evidence not found" in e for e in report.errors)

    def test_ungrounded_fact_is_an_error_unless_marked(self):
        facts = [{"fact": "Yes, same", "any_of": ["identical"]}]
        report = ValidationReport()
        validate_against_corpus(_golden([_item(expected_facts=facts)]), _manifest(self.CHUNKS), self.CHUNKS, report)
        assert any("no accepted phrasing" in e for e in report.errors)

        facts[0]["in_source"] = False
        report = ValidationReport()
        validate_against_corpus(_golden([_item(expected_facts=facts)]), _manifest(self.CHUNKS), self.CHUNKS, report)
        assert report.ok, report.errors

    def test_chunk_drift_is_an_error(self):
        manifest = _manifest(self.CHUNKS)
        changed = copy.deepcopy(self.CHUNKS)
        changed["DOC-001_A.docx"][1] = "Oil replenished to level."
        report = ValidationReport()
        validate_against_corpus(_golden([_item()]), manifest, changed, report)
        assert any("fingerprint drift" in e for e in report.errors)

    def test_structure_flags_unknown_docs_unreviewed_and_split(self):
        item = _item(expected_docs=["NOPE.docx"], expected_evidence=[{"doc": "NOPE.docx", "contains": "abc"}])
        item["review"] = {"status": "needs_review"}
        report = validate_structure(_golden([item]), _manifest(self.CHUNKS))
        text = " ".join(report.errors)
        assert "not reviewed" in text and "not in the manifest" in text and "type split" in text


class TestMatching:
    def test_number_boundaries(self):
        assert contains_phrase(normalize("tested at 44 barg and 44.5 barg"), "44 barg")
        assert not contains_phrase(normalize("lifted at 44.5 barg"), "44 barg")
        assert not contains_phrase(normalize("chloride at 340 ppm"), "34")

    def test_unit_and_symbol_folding(self):
        text = normalize("Pump P‑101 at −40 Deg C, 5 per cent, 2.3 Ω and 180 m³/hr")
        for phrase in ["P-101", "-40 °C", "5%", "2.3 Ω", "180 m3/hr"]:
            assert contains_phrase(text, phrase), phrase


def test_committed_golden_set_and_manifest_are_structurally_valid():
    """The real files parse, are fully reviewed and keep the 20/10/5/5 split."""
    report = validate_structure(load_golden_set(), load_manifest())
    assert report.ok, report.errors
