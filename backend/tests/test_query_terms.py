"""Tests for keyword-query term extraction and coverage scoring.

These back the keyword arm of hybrid retrieval. Its whole purpose is to catch
the exact identifiers dense embeddings blur together — asset tags, error
codes, part numbers — so identifier handling is the core of what is asserted
here.
"""

import pytest

from app.services.vector_store import (
    MAX_QUERY_TERMS,
    MIN_QUERY_TERM_LEN,
    _extract_query_terms,
    _term_coverage,
    _term_rank,
)


class TestExtractQueryTerms:
    def test_keeps_identifiers_intact(self) -> None:
        """Splitting "P-101" into "P" and "101" would defeat the entire arm."""
        assert "P-101" in _extract_query_terms("Why did pump P-101 fail?")

    def test_keeps_dotted_identifiers(self) -> None:
        assert "v1.2" in _extract_query_terms("changes in v1.2 release")

    def test_drops_stopwords(self) -> None:
        terms = {t.casefold() for t in _extract_query_terms("Why did the pump fail?")}

        assert "why" not in terms
        assert "the" not in terms
        assert "pump" in terms

    def test_all_stopwords_yields_nothing(self) -> None:
        """Must return empty, not a filter that ORs common words over the corpus."""
        assert _extract_query_terms("what is the of and") == []

    def test_empty_and_none_input(self) -> None:
        assert _extract_query_terms("") == []
        assert _extract_query_terms(None) == []

    def test_drops_terms_below_index_min_length(self) -> None:
        """The content index stores no token shorter than its min_token_len."""
        for term in _extract_query_terms("a b pump"):
            assert len(term) >= MIN_QUERY_TERM_LEN

    def test_deduplicates_case_insensitively(self) -> None:
        terms = _extract_query_terms("Pump pump PUMP")

        assert len(terms) == 1

    def test_identifiers_survive_the_term_cap(self) -> None:
        """When the cap bites, the identifier is the term worth keeping."""
        filler = " ".join(f"word{i}" for i in range(40))
        terms = _extract_query_terms(f"{filler} TK-305")

        assert len(terms) <= MAX_QUERY_TERMS
        assert "TK-305" in terms

    def test_digit_alone_does_not_make_a_term_an_identifier(self) -> None:
        """"word10" and "2026" have digits without being identifiers."""
        assert _term_rank("P-101") < _term_rank("word10")
        assert _term_rank("TK-305") < _term_rank("2026")

    def test_plain_words_rank_last(self) -> None:
        assert _term_rank("pump") > _term_rank("P-101")

    def test_respects_the_term_cap(self) -> None:
        many = " ".join(f"distinct{i}" for i in range(50))

        assert len(_extract_query_terms(many)) <= MAX_QUERY_TERMS

    def test_strips_trailing_punctuation(self) -> None:
        assert "pump" in _extract_query_terms("the pump.")

    def test_punctuation_only_query(self) -> None:
        assert _extract_query_terms("??? !!! ...") == []


class TestTermCoverage:
    def test_full_coverage(self) -> None:
        score = _term_coverage(["pump", "P-101"], "Pump P-101 tripped.")

        assert score == pytest.approx(1.0)

    def test_partial_coverage(self) -> None:
        score = _term_coverage(["pump", "P-101", "seal"], "Pump P-101 tripped.")

        assert score == pytest.approx(2 / 3)

    def test_no_coverage(self) -> None:
        assert _term_coverage(["zebra"], "Pump P-101 tripped.") == 0.0

    def test_is_case_insensitive(self) -> None:
        assert _term_coverage(["PUMP"], "pump running") == pytest.approx(1.0)

    def test_more_matching_terms_scores_higher(self) -> None:
        """This ordering is the only ranking signal the keyword arm has.

        Qdrant assigns every hit of a filter-only query the same score, so
        without this the fusion step would order keyword hits arbitrarily.
        """
        terms = ["pump", "P-101", "seal"]
        better = _term_coverage(terms, "Pump P-101 failed on the seal.")
        worse = _term_coverage(terms, "Pump P-102 was serviced.")

        assert better > worse

    def test_empty_terms_or_content(self) -> None:
        assert _term_coverage([], "anything") == 0.0
        assert _term_coverage(["pump"], "") == 0.0
        assert _term_coverage(["pump"], None) == 0.0
