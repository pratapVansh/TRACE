"""Tests for evidence classification.

Ported with the classifier from the removed agent framework. The regression
these guard against is the original heuristic: a raw 3-word set overlap with
no stopword filter, which made FACT nearly constant.
"""

import pytest

from app.schemas.rag import Citation
from app.services.evidence_classification import (
    classify_statements,
    split_sentences,
    summarize_statements,
)


def _cite(content: str, name: str = "MAN-001_Pump_Manual.docx") -> Citation:
    return Citation(
        chunk_id="c1",
        document_name=name,
        page_number=1,
        chunk_content=content,
        score=0.9,
        similarity_score=0.9,
        highlighted_excerpt="",
    )


PUMP_CHUNK = (
    "Pump P-101 is a KBL Series-C horizontal centrifugal pump supplied by "
    "Kirloskar Brothers Ltd. Rated flow is 120 cubic metres per hour at a "
    "discharge head of 45 metres. The mechanical seal is a John Crane Type 21."
)


class TestGrounding:
    def test_supported_sentence_is_fact(self):
        answer = "Pump P-101 is a KBL Series-C horizontal centrifugal pump."
        [stmt] = classify_statements(answer, [_cite(PUMP_CHUNK)])
        assert stmt.classification == "FACT"
        assert stmt.evidence_refs == ["MAN-001_Pump_Manual.docx"]

    def test_unsupported_sentence_is_unknown(self):
        answer = "The turbine was replaced during the 2019 overhaul in Rotterdam."
        [stmt] = classify_statements(answer, [_cite(PUMP_CHUNK)])
        assert stmt.classification == "UNKNOWN"
        assert stmt.evidence_refs == []

    def test_no_citations_means_nothing_is_fact(self):
        answer = "Pump P-101 is a KBL Series-C horizontal centrifugal pump."
        [stmt] = classify_statements(answer, [])
        assert stmt.classification == "UNKNOWN"


class TestStopwordRegression:
    """The bug the port exists to fix.

    A sentence sharing only function words with a passage must not be FACT.
    Under the old raw-overlap rule these each matched on 3+ stopwords.
    """

    @pytest.mark.parametrize(
        "answer",
        [
            "It is one of the items that is at the site and is not a pump.",
            "There is a report on the shelf and it is the one that is used.",
        ],
    )
    def test_stopword_only_overlap_is_not_fact(self, answer: str):
        [stmt] = classify_statements(answer, [_cite(PUMP_CHUNK)])
        assert stmt.classification != "FACT"

    def test_long_sentence_cannot_accumulate_support(self):
        """Coverage is a fraction, so length does not buy grounding."""
        answer = (
            "Pump P-101 was mentioned in passing during a meeting about "
            "budgets, catering, parking arrangements, the annual survey, "
            "office relocation, printer contracts and holiday scheduling."
        )
        [stmt] = classify_statements(answer, [_cite(PUMP_CHUNK)])
        assert stmt.classification == "UNKNOWN"


class TestHedging:
    def test_hedged_sentence_is_hypothesis_even_when_supported(self):
        answer = "Pump P-101 may be a KBL Series-C centrifugal pump."
        [stmt] = classify_statements(answer, [_cite(PUMP_CHUNK)])
        assert stmt.classification == "HYPOTHESIS"

    def test_hedged_and_unsupported_is_hypothesis(self):
        answer = "The failure could possibly have originated in the gearbox."
        [stmt] = classify_statements(answer, [_cite(PUMP_CHUNK)])
        assert stmt.classification == "HYPOTHESIS"


class TestSentenceSplitting:
    def test_markdown_bullets_split_per_line(self):
        assert split_sentences("* first item\n* second item\n") == [
            "first item",
            "second item",
        ]

    def test_headings_carry_no_claim_and_are_dropped(self):
        assert classify_statements("### Findings\n", [_cite(PUMP_CHUNK)]) == []

    def test_equipment_tags_survive_tokenisation(self):
        answer = "The seal on P-101 is a John Crane Type 21 mechanical seal."
        [stmt] = classify_statements(answer, [_cite(PUMP_CHUNK)])
        assert stmt.classification == "FACT"

    def test_decimals_do_not_split_sentences(self):
        assert len(split_sentences("Flow is 120.5 cubic metres per hour.")) == 1


class TestSummary:
    def test_counts_each_classification(self):
        answer = (
            "Pump P-101 is a KBL Series-C horizontal centrifugal pump.\n"
            "The rated flow may be higher under test conditions.\n"
            "The turbine was replaced during the 2019 Rotterdam overhaul.\n"
        )
        summary = summarize_statements(classify_statements(answer, [_cite(PUMP_CHUNK)]))
        assert (summary.fact_count, summary.hypothesis_count, summary.unknown_count) == (1, 1, 1)
        assert summary.total == 3

    def test_empty_answer_yields_empty_summary(self):
        summary = summarize_statements(classify_statements("", [_cite(PUMP_CHUNK)]))
        assert summary.total == 0
