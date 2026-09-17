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

    @pytest.mark.parametrize("participle", [
        "recorded", "found", "documented", "reported", "made", "given",
        "available", "provided", "listed",
    ])
    def test_premise_correction_accepts_every_synonym(self, participle):
        """Vocabulary must not decide the label either, for the same reason.

        A model writes this one premise correction as "are recorded", "are
        available", "are provided" or "are listed" interchangeably; all of them
        say the documents hold no such record.
        """
        assert is_refusal(f"The inspection was deferred, so no findings are {participle}.")

    def test_n04_regression_chunk512_available_phrasing(self):
        """Eval N04, chunk512: "are available" where the baseline said "were recorded".

        The 512-token run answered the false premise correctly - the internal
        inspection had not happened, so there is nothing to report - but the
        classifier accepted only the "recorded" wording and scored it
        ``missed_refusal``, which read as a chunk-size regression on negatives
        that had not occurred. Both phrasings must classify the same way.
        """
        baseline = ("The internal inspection of boiler B‑101 was **deferred** to the next plant shutdown, "
                    "so no internal visual findings inside the steam drum were recorded.")
        chunk512 = ("The internal inspection of boiler B‑101 has not been completed; therefore no "
                    "findings inside the steam drum are available.")
        assert is_refusal(baseline) == is_refusal(chunk512) is True
        assert refusal_outcome(baseline, True, None) == refusal_outcome(chunk512, True, None) == "correct_refusal"

    def test_n04_regression_graph_v2_contains_no_phrasing(self):
        """Eval N04, graph_v2: the verb in front of the noun.

        A third wording of the one premise correction, and it was scoring a
        third way. "The documents contain no findings from inside the steam
        drum" says exactly what the baseline's "no findings were recorded"
        says - the verb simply precedes the noun, so the pattern built around
        a trailing participle could not see it, and the reworked graph arm
        appeared to lose a negative it had nothing to do with.
        """
        baseline = ("The internal inspection of boiler B‑101 was **deferred** to the next plant shutdown, "
                    "so no internal visual findings inside the steam drum were recorded.")
        graph_v2 = ("The internal inspection of boiler B‑101 was deferred to the next shutdown; therefore "
                    "the documents contain no findings from inside the steam drum. Only external "
                    "ultrasonic thickness measurements of the drum shell are reported.")
        assert is_refusal(baseline) == is_refusal(graph_v2) is True
        assert refusal_outcome(baseline, True, None) == refusal_outcome(graph_v2, True, None) == "correct_refusal"

    @pytest.mark.parametrize("answer", [
        "The retrieved context contains no data on that valve.",
        "The provided sources list no readings for the 2018 survey.",
        "The supplied documents include no details of the repair.",
    ])
    def test_corpus_contains_no_record_is_a_refusal(self, answer):
        """Same absence, stated subject-verb-object rather than passively."""
        assert is_refusal(answer)

    @pytest.mark.parametrize("answer", [
        "No defects were noted during the internal inspection of the drum.",
        "No anomalies were found during the walkdown; the unit ran normally.",
        "No corrosion was found on the drum internals during the 2024 inspection.",
        "The inspection report contains no defects.",
        "The turnaround report documents no cracking on the shell.",
    ])
    def test_inspection_that_found_nothing_is_not_a_refusal(self, answer):
        """The guard on the widened vocabulary.

        "No defects were noted" is a substantive finding - the inspection
        happened and saw nothing wrong - not a statement that the documents are
        silent. The noun list is what separates the two, so it must keep
        excluding defects, anomalies and corrosion.
        """
        assert not is_refusal(answer)

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
