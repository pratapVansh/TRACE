"""Tests for the conversational query-understanding layer.

The behaviour that matters is asymmetric: a follow-up must gain the
conversation's subject before it reaches retrieval, and a self-contained
question must gain nothing at all.  The second half is what keeps a
conversation from drifting back to a topic the user has left.
"""

import pytest

from app.services.query_understanding import (
    QueryUnderstanding,
    build_history_window,
    build_interpretation_note,
)


def _history(*turns: tuple[str, str]) -> list[dict]:
    return [{"role": role, "content": content} for role, content in turns]


@pytest.fixture
def qu() -> QueryUnderstanding:
    return QueryUnderstanding()


class TestSelfContainedQueries:
    """Questions that stand alone must reach retrieval untouched."""

    @pytest.mark.parametrize("question", [
        "What caused the pump P-101 vibration failure?",
        "How do I calibrate the flow transmitter on the discharge line?",
        "List the maintenance history for compressor C-201",
    ])
    def test_not_rewritten(self, qu: QueryUnderstanding, question: str) -> None:
        history = _history(("user", "Tell me about tank TK-305"), ("assistant", "TK-305 is a tank."))

        resolved = qu.resolve(question, history=history)

        assert resolved.is_followup is False
        assert resolved.search_query == question
        assert resolved.was_rewritten is False

    def test_prior_topic_does_not_leak_into_new_question(self, qu: QueryUnderstanding) -> None:
        """A new self-contained topic must not inherit the old subject."""
        history = _history(
            ("user", "Why did pump P-101 fail?"),
            ("assistant", "Bearing wear on P-101."),
        )

        resolved = qu.resolve("What is the calibration procedure for TK-305?", history=history)

        assert "P-101" not in resolved.search_query

    def test_empty_question(self, qu: QueryUnderstanding) -> None:
        resolved = qu.resolve("", history=_history(("user", "pump P-101")))

        assert resolved.search_query == ""
        assert resolved.is_followup is False


class TestFollowUpResolution:
    def test_pronoun_gains_the_conversation_subject(self, qu: QueryUnderstanding) -> None:
        """"What caused it?" retrieves on "it" unless the subject is restored."""
        history = _history(
            ("user", "Show me the vibration alarms on pump P-101"),
            ("assistant", "P-101 tripped three times this week."),
        )

        resolved = qu.resolve("What caused it?", history=history)

        assert resolved.is_followup is True
        assert "P-101" in resolved.search_query
        assert "P-101" in resolved.carried_entities

    def test_possessive_pronoun_is_substituted(self, qu: QueryUnderstanding) -> None:
        history = _history(("user", "Tell me about compressor C-201"))

        resolved = qu.resolve("What is its rated capacity?", history=history)

        assert "C-201" in resolved.search_query
        assert " its " not in f" {resolved.search_query} "

    def test_elliptical_opener_is_treated_as_follow_up(self, qu: QueryUnderstanding) -> None:
        history = _history(("user", "Why did pump P-101 trip on high vibration?"))

        resolved = qu.resolve("What about the bearings?", history=history)

        assert resolved.is_followup is True
        assert "P-101" in resolved.search_query
        assert "bearings" in resolved.search_query

    def test_bare_fragment_is_treated_as_follow_up(self, qu: QueryUnderstanding) -> None:
        history = _history(("user", "Summarise the P-101 inspection report"))

        resolved = qu.resolve("Why?", history=history)

        assert resolved.is_followup is True
        assert "P-101" in resolved.search_query

    def test_topic_terms_carry_from_user_turns(self, qu: QueryUnderstanding) -> None:
        history = _history(("user", "What is the cavitation threshold?"))

        resolved = qu.resolve("And the mitigation?", history=history)

        assert "cavitation" in resolved.search_query.casefold()

    def test_own_content_terms_suppress_topic_carry(self, qu: QueryUnderstanding) -> None:
        """A follow-up with its own subject matter needs the subject, not the topic."""
        history = _history(("user", "Why did pump P-101 trip on high vibration?"))

        resolved = qu.resolve("What about the bearings?", history=history)

        assert "P-101" in resolved.search_query
        assert "vibration" not in resolved.search_query.casefold()
        assert "trip" not in resolved.search_query.casefold()

    def test_assistant_prose_does_not_supply_topic_terms(self, qu: QueryUnderstanding) -> None:
        """An answer's vocabulary would swamp the query with its own phrasing."""
        history = _history(
            ("user", "Status of P-101?"),
            ("assistant", "The centrifugal impeller assembly requires quarterly lubrication."),
        )

        resolved = qu.resolve("Why?", history=history)

        assert "lubrication" not in resolved.search_query.casefold()
        assert "P-101" in resolved.search_query

    def test_original_question_is_always_preserved(self, qu: QueryUnderstanding) -> None:
        history = _history(("user", "Tell me about pump P-101"))

        resolved = qu.resolve("What caused it?", history=history)

        assert resolved.original == "What caused it?"

    def test_follow_up_without_history_is_left_alone(self, qu: QueryUnderstanding) -> None:
        """Nothing to resolve against — retrieve verbatim rather than guess."""
        resolved = qu.resolve("What caused it?", history=None)

        assert resolved.is_followup is True
        assert resolved.was_rewritten is False
        assert "no prior context" in resolved.resolution

    def test_relative_that_is_not_substituted(self, qu: QueryUnderstanding) -> None:
        """"the one that failed" must not become "the one P-101 failed"."""
        history = _history(("user", "List the pumps in unit 4, including P-101"))

        resolved = qu.resolve("Which is the one that failed?", history=history)

        assert "that failed" in resolved.search_query

    def test_entity_is_not_duplicated_when_already_present(self, qu: QueryUnderstanding) -> None:
        history = _history(("user", "Tell me about pump P-101"))

        resolved = qu.resolve("P-101?", history=history)

        assert resolved.search_query.count("P-101") == 1


class TestHistoryWindow:
    def test_keeps_most_recent_messages(self) -> None:
        history = _history(*[("user" if i % 2 == 0 else "assistant", f"msg {i}") for i in range(40)])

        window = build_history_window(history, max_messages=6)

        assert len(window) <= 6
        assert window[-1]["content"] == "msg 39"

    def test_preserves_chronological_order(self) -> None:
        history = _history(*[("user" if i % 2 == 0 else "assistant", f"msg {i}") for i in range(10)])

        window = build_history_window(history, max_messages=4)

        assert [m["content"] for m in window] == sorted(
            (m["content"] for m in window), key=lambda c: int(c.split()[1])
        )

    def test_truncates_oversized_messages(self) -> None:
        history = _history(("user", "x" * 5000))

        window = build_history_window(history, max_chars_per_message=100)

        assert len(window[0]["content"]) < 200
        assert "truncated" in window[0]["content"]

    def test_respects_total_char_budget(self) -> None:
        history = _history(*[("user", "y" * 400) for _ in range(50)])

        window = build_history_window(history, max_total_chars=1000, max_chars_per_message=400)

        assert sum(len(m["content"]) for m in window) <= 1400

    def test_window_does_not_start_on_a_dangling_answer(self) -> None:
        history = _history(
            ("user", "q1"), ("assistant", "a1"),
            ("user", "q2"), ("assistant", "a2"),
        )

        window = build_history_window(history, max_messages=3)

        assert window[0]["role"] == "user"

    def test_empty_history(self) -> None:
        assert build_history_window(None) == []
        assert build_history_window([]) == []

    def test_short_history_passes_through(self) -> None:
        history = _history(("user", "q1"), ("assistant", "a1"))

        assert build_history_window(history) == history


class TestInterpretationNote:
    def test_note_is_emitted_for_a_rewrite(self) -> None:
        qu = QueryUnderstanding()
        resolved = qu.resolve("What caused it?", history=_history(("user", "pump P-101 status")))

        note = build_interpretation_note(resolved)

        assert "P-101" in note
        assert "follow-up" in note

    def test_no_note_for_a_self_contained_question(self) -> None:
        qu = QueryUnderstanding()
        resolved = qu.resolve("What caused the P-101 failure?", history=None)

        assert build_interpretation_note(resolved) == ""
