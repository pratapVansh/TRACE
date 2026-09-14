"""Stage 5 evaluation metrics."""

import pytest

from eval.metrics import (
    citation_precision_recall,
    cited_documents,
    doc_recall_at_k,
    fact_coverage,
    follow_up_resolved,
    is_refusal,
    passage_recall,
    percentile,
    reciprocal_rank,
    refusal_outcome,
)

DOCS = ["B.docx", "A.docx", "B.docx", "C.docx", "D.docx", "E.docx", "F.docx"]


class TestRetrieval:
    def test_doc_recall_counts_distinct_documents(self):
        assert doc_recall_at_k(DOCS, ["A.docx"], k=5) == 1.0
        assert doc_recall_at_k(DOCS, ["F.docx"], k=5) == 0.0
        assert doc_recall_at_k(DOCS, ["A.docx", "F.docx"], k=5) == 0.5
        assert doc_recall_at_k(DOCS, [], k=5) is None

    def test_reciprocal_rank(self):
        assert reciprocal_rank(DOCS, ["A.docx"]) == 0.5
        assert reciprocal_rank(DOCS, ["C.docx", "A.docx"]) == 0.5
        assert reciprocal_rank(DOCS, ["Z.docx"]) == 0.0
        assert reciprocal_rank(DOCS, []) is None

    def test_passage_recall_requires_the_right_document_and_rank(self):
        chunks = [("A.docx", "prose about grid B3"), ("B.docx", "A3 | North, bottom | 13.6 | 12.9")]
        evidence = [("B.docx", "A3 | North, bottom | 13.6 | 12.9")]
        assert passage_recall(chunks, evidence, k=1) == 0.0
        assert passage_recall(chunks, evidence, k=2) == 1.0
        assert passage_recall(chunks, [("A.docx", "A3 | North, bottom | 13.6 | 12.9")], k=None) == 0.0
        assert passage_recall(chunks, [], k=5) is None

    def test_follow_up_resolution(self):
        assert follow_up_resolved("What part fixed INC-002? V-220", ["V-220"]) is True
        assert follow_up_resolved("What part was used to fix it?", ["V-220"]) is False
        assert follow_up_resolved("anything", []) is None


class TestAnswers:
    FACTS = [
        {"fact": "44 barg", "any_of": ["44 barg"]},
        {"fact": "44.5 barg", "any_of": ["44.5 barg"]},
    ]

    def test_fact_coverage_uses_number_boundaries(self):
        coverage, hits = fact_coverage("Only one valve lifted, at 44.5 barg.", self.FACTS)
        assert hits == [False, True] and coverage == 0.5
        assert fact_coverage("anything", []) == (None, [])

    @pytest.mark.parametrize("answer", [
        "I could not find this information in the uploaded documents.",
        "The provided documents do not contain information about this.",
        "No supporting evidence found.",
        "There is no record of a K‑402 seal gas failure in the documents.",
        "The set pressure of PSV-3011 is not specified in the provided documents.",
    ])
    def test_refusals_detected(self, answer):
        assert is_refusal(answer)

    def test_premise_correction_is_a_refusal(self):
        answer = ("The internal inspection of boiler B‑101 was **deferred** to the next plant shutdown, "
                  "so no internal visual findings inside the steam drum were recorded.")
        assert is_refusal(answer)

    @pytest.mark.parametrize("verb", ["were", "was", "are", "is", "have been", "has been", "had been"])
    def test_premise_correction_is_tense_agnostic(self, verb):
        """Tense must not decide the label: the content is identical either way."""
        assert is_refusal(f"The inspection was deferred, so no findings {verb} recorded.")

    def test_n04_regression_both_phrasings_agree(self):
        """Eval N04: the same premise correction, written in two tenses.

        The past-tense wording scored ``correct_refusal`` and the present-tense
        wording ``missed_refusal``, which made the graph look responsible for a
        negative it had nothing to do with. Both must classify the same way.
        """
        past = ("The internal inspection of boiler B‑101 was **deferred** to the next plant shutdown, "
                "so no internal visual findings inside the steam drum were recorded.")
        present = ("The internal inspection of boiler **B‑101** was **deferred** to the next shutdown, "
                   "so no internal‑inspection findings are recorded.")
        assert is_refusal(past) == is_refusal(present) is True
        assert refusal_outcome(past, True, None) == refusal_outcome(present, True, None) == "correct_refusal"

    def test_plain_answer_is_not_a_refusal(self):
        assert not is_refusal("PSV-101 is set at 6.0 barg on the pump discharge (SCN-002).")
        assert not is_refusal("No leakage was observed; the pump ran for 1 hour at 4.5 barg.")

    def test_markdown_emphasis_does_not_split_phrases(self):
        coverage, _ = fact_coverage("- **Minimum required stock:** 2 pcs.", [
            {"fact": "min 2", "any_of": ["minimum required stock: 2"]},
        ])
        assert coverage == 1.0

    def test_refusal_outcomes(self):
        assert refusal_outcome("No supporting evidence found.", True, None) == "correct_refusal"
        assert refusal_outcome("It was set at 6.0 barg.", True, None) == "missed_refusal"
        assert refusal_outcome("No supporting evidence found.", False, 0.0) == "false_refusal"
        # A refused sub-part next to correct facts is still an answer.
        assert refusal_outcome("6.0 barg. No supporting evidence found for the date.", False, 0.5) == "answered"

    def test_citations(self):
        names = ["SOP-003_Boiler_Start-Up_Procedure.docx", "Equipment_Register.xlsx", "INC-001_X.docx"]
        cited = cited_documents("Evidence: SOP‑003; Equipment Register.", names)
        assert cited == {"SOP-003_Boiler_Start-Up_Procedure.docx", "Equipment_Register.xlsx"}
        precision, recall = citation_precision_recall(cited, ["SOP-003_Boiler_Start-Up_Procedure.docx"])
        assert precision == 0.5 and recall == 1.0
        assert citation_precision_recall(set(), ["A"]) == (None, 0.0)
        assert citation_precision_recall(cited, []) == (None, None)


def test_percentile():
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([10], 95) == 10
    assert percentile([], 50) is None
