"""Query understanding for conversational RAG.

Retrieval runs on the literal question, so a follow-up like "what caused it?"
searches for the word "it".  The pronoun carries no signal for the embedding
and is a stopword to the keyword index, so the turn retrieves near-noise while
the conversation's actual subject — "P-101" — never reaches the retriever at
all.  Conversation history was only ever handed to the LLM, which meant the
model was asked to answer from context that retrieval had already failed to
find.

This module sits between the chat turn and retrieval.  It decides whether a
question stands on its own and, when it does not, rewrites it using the
entities and topic of recent turns.

Two properties keep the rewrite safe:

- The original question is always preserved and is what the LLM answers.
  Only the *search* query changes, so a bad rewrite costs retrieval quality
  rather than silently answering a different question.
- A question that stands on its own is never rewritten.  Injecting prior
  entities into a self-contained query is how conversational RAG drifts back
  to a stale topic, so the detector must opt in before anything is added.

Everything here is deterministic — regexes over the transcript, no LLM
round-trip added to the request path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.logging import logger
from app.core.query_terms import _extract_query_terms
from app.services.entity_memory_service import EntityMemoryService

# How far back to look for the subject of a follow-up.  Two turns covers
# "what caused it?" → "and the bearings?" chains; going further mostly
# resurrects topics the user has moved on from.
_HISTORY_LOOKBACK_MESSAGES = 6
_MAX_CARRIED_ENTITIES = 2
_MAX_TOPIC_TERMS = 4

# Conversation-history window defaults.  History used to be passed whole, so
# a long conversation grew the prompt without bound until it displaced the
# retrieved context it was supposed to support.
_MAX_HISTORY_MESSAGES = 12
_MAX_HISTORY_MESSAGE_CHARS = 1500
_MAX_HISTORY_TOTAL_CHARS = 8000

# Pronouns safe to substitute: each one stands in for a thing, so swapping in
# the carried entity yields a sensible query.  "this"/"that" are deliberately
# absent — they are just as often relative pronouns ("the pump that failed"),
# where substitution would corrupt the query.  They still count as evidence
# of context-dependence below; they just get context appended instead.
_SUBSTITUTABLE_PRONOUNS = re.compile(
    r"(?<!\w)(it|its|it's|they|them|their|theirs)(?!\w)",
    re.IGNORECASE,
)

# Any of these signal that the question leans on earlier turns.
_REFERENCE_MARKERS = re.compile(
    r"(?<!\w)(it|its|it's|this|that|these|those|they|them|their|"
    r"the\s+same|the\s+one|the\s+former|the\s+latter|above|previous)(?!\w)",
    re.IGNORECASE,
)

# Openers that continue a previous question rather than starting a new one.
_ELLIPTICAL_OPENERS = (
    "what about", "how about", "and what", "and how", "and why", "and the",
    "what else", "anything else", "any others", "tell me more", "more on",
    "elaborate", "go on", "continue", "same for", "the same for",
    "compare", "compared to", "versus", "vs",
    "why", "why not", "how so", "such as", "for example", "and", "also",
)

# A question this short has nothing for retrieval to match on unless the
# conversation supplies the subject.
_MIN_STANDALONE_TERMS = 3

# A follow-up that contributes this much of its own subject matter needs the
# earlier *subject*, not the earlier *topic*: "what about the bearings?" is
# asking about bearings, and padding it with the previous question's terms
# would pull retrieval back toward the question it was moving on from.
_MIN_OWN_CONTENT_TERMS = 2


@dataclass(frozen=True)
class ResolvedQuery:
    """A user question paired with the query that should be retrieved on."""

    original: str
    """Exactly what the user typed.  Always what the LLM is asked to answer."""

    search_query: str
    """What retrieval should run on — rewritten only for follow-ups."""

    is_followup: bool
    """Whether the question was judged to depend on earlier turns."""

    resolution: str
    """Why the layer decided what it did, for logs and debugging."""

    carried_entities: tuple[str, ...] = ()
    """Entity tags pulled forward from earlier turns (e.g. ``("P-101",)``)."""

    topic_terms: tuple[str, ...] = ()
    """Salient non-entity terms pulled forward (e.g. ``("vibration",)``)."""

    @property
    def was_rewritten(self) -> bool:
        return self.search_query != self.original


@dataclass
class _PriorContext:
    """The subject matter recent turns can lend to an under-specified query."""

    entities: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.entities or self.terms)


class QueryUnderstanding:
    """Resolves a question against conversation history before retrieval."""

    def __init__(self, entity_service: EntityMemoryService | None = None) -> None:
        # Only the stateless extractor is used; per-conversation storage lives
        # with the caller, so instances are cheap and share no state.
        self._entities = entity_service or EntityMemoryService()

    # ── Public API ──────────────────────────────────────────────

    def resolve(
        self,
        question: str,
        history: list[dict] | None = None,
    ) -> ResolvedQuery:
        """Return *question* alongside the query retrieval should use.

        ``history`` is the conversation so far as ``{"role", "content"}``
        dicts, oldest first — the same shape the LLM providers take.
        """
        text = (question or "").strip()
        if not text:
            return ResolvedQuery(
                original=question or "",
                search_query=question or "",
                is_followup=False,
                resolution="empty question",
            )

        own_entities = self._entity_names(text)

        if not self._is_context_dependent(text, own_entities):
            return ResolvedQuery(
                original=text,
                search_query=text,
                is_followup=False,
                resolution="self-contained question",
            )

        prior = self._prior_context(text, own_entities, history)
        if not prior:
            # The question needs context that the conversation cannot supply —
            # retrieving on it verbatim is the honest fallback.
            return ResolvedQuery(
                original=text,
                search_query=text,
                is_followup=True,
                resolution="follow-up detected but no prior context available",
            )

        search_query = self._rewrite(text, prior)

        resolved = ResolvedQuery(
            original=text,
            search_query=search_query,
            is_followup=True,
            resolution="follow-up resolved against conversation history",
            carried_entities=tuple(prior.entities),
            topic_terms=tuple(prior.terms),
        )
        logger.info(
            "Query understanding: follow-up %r resolved to %r (entities=%s, terms=%s)",
            text, search_query, prior.entities, prior.terms,
        )
        return resolved

    # ── Detection ───────────────────────────────────────────────

    def _is_context_dependent(self, question: str, own_entities: list[str]) -> bool:
        """Whether *question* needs earlier turns to be retrievable.

        Ordered so the cheapest, most decisive signal wins: a question naming
        its own equipment is answerable on its own terms, whatever else it
        contains.
        """
        lowered = question.casefold()
        term_count = len(_extract_query_terms(question))

        # Names its own subject and says enough about it — nothing to carry.
        if own_entities and term_count >= _MIN_STANDALONE_TERMS:
            return False

        if _REFERENCE_MARKERS.search(lowered) and not own_entities:
            return True

        stripped = lowered.lstrip("\"'( ")
        if any(
            stripped == opener or stripped.startswith(opener + " ")
            for opener in _ELLIPTICAL_OPENERS
        ):
            return True

        # Too little to retrieve on: "the bearings?", "next steps?"
        if term_count < _MIN_STANDALONE_TERMS and not own_entities:
            return True

        return False

    # ── Context gathering ───────────────────────────────────────

    def _prior_context(
        self,
        question: str,
        own_entities: list[str],
        history: list[dict] | None,
    ) -> _PriorContext:
        """Collect entities and topic terms from the most recent turns."""
        prior = _PriorContext()
        if not history:
            return prior

        present = {e.casefold() for e in own_entities}
        own_terms = _extract_query_terms(question)
        question_terms = {t.casefold() for t in own_terms}
        wants_topic = len(own_terms) < _MIN_OWN_CONTENT_TERMS

        # Most recent first: the newest mention of a subject wins.
        for message in reversed(history[-_HISTORY_LOOKBACK_MESSAGES:]):
            content = (message or {}).get("content") or ""
            if not content:
                continue

            for name in self._entity_names(content):
                key = name.casefold()
                if key in present:
                    continue
                present.add(key)
                prior.entities.append(name)

            # Topic terms come from what the user asked, not from the
            # assistant's prose — an answer's vocabulary is mostly its own
            # phrasing and would swamp the query with generic words.
            if wants_topic and (message or {}).get("role") == "user":
                for term in _extract_query_terms(content):
                    key = term.casefold()
                    if key in question_terms or key in present:
                        continue
                    present.add(key)
                    prior.terms.append(term)

            enough_entities = len(prior.entities) >= _MAX_CARRIED_ENTITIES
            enough_terms = not wants_topic or len(prior.terms) >= _MAX_TOPIC_TERMS
            if enough_entities and enough_terms:
                break

        del prior.entities[_MAX_CARRIED_ENTITIES:]
        del prior.terms[_MAX_TOPIC_TERMS:]
        return prior

    def _entity_names(self, text: str) -> list[str]:
        return [e["name"] for e in self._entities.extract_entities_from_text(text)]

    # ── Rewriting ───────────────────────────────────────────────

    @staticmethod
    def _rewrite(question: str, prior: _PriorContext) -> str:
        """Build the retrieval query from *question* plus carried context."""
        rewritten = question
        subject = prior.entities[0] if prior.entities else None

        if subject:
            rewritten = _SUBSTITUTABLE_PRONOUNS.sub(subject, rewritten)

        # Whatever substitution did not place — the second entity, the carried
        # topic terms — is appended.  Retrieval is bag-of-words enough that
        # trailing context still lands, and appending cannot mangle the
        # question the way an over-eager substitution can.
        appended = [
            item for item in (*prior.entities, *prior.terms)
            if not re.search(rf"(?<!\w){re.escape(item)}(?!\w)", rewritten, re.IGNORECASE)
        ]
        if appended:
            rewritten = f"{rewritten} {' '.join(appended)}"

        return rewritten.strip()


def build_history_window(
    history: list[dict] | None,
    *,
    max_messages: int = _MAX_HISTORY_MESSAGES,
    max_chars_per_message: int = _MAX_HISTORY_MESSAGE_CHARS,
    max_total_chars: int = _MAX_HISTORY_TOTAL_CHARS,
) -> list[dict]:
    """Trim *history* to the most recent turns that fit a fixed budget.

    The full transcript used to be sent on every turn, so a long conversation
    grew the prompt without bound — eventually crowding out the retrieved
    context the answer is supposed to be grounded in, and paying for the
    privilege.  Recency is what a follow-up needs, so the window keeps the
    newest messages and drops the oldest.

    Returns messages oldest-first, the order the providers expect.
    """
    if not history:
        return []

    kept: list[dict] = []
    total = 0

    for message in reversed(history):
        if len(kept) >= max_messages:
            break

        content = (message or {}).get("content") or ""
        if len(content) > max_chars_per_message:
            content = content[:max_chars_per_message].rstrip() + " …[truncated]"

        if total + len(content) > max_total_chars and kept:
            break

        kept.append({**message, "content": content})
        total += len(content)

    kept.reverse()

    # An assistant message whose question was trimmed away reads as an answer
    # to nothing, so the window starts on a user turn.
    if kept and kept[0].get("role") == "assistant":
        kept = kept[1:]

    if len(kept) < len(history):
        logger.debug(
            "History windowed: %d of %d messages kept (%d chars)",
            len(kept), len(history), total,
        )
    return kept


def build_interpretation_note(resolved: ResolvedQuery) -> str:
    """Describe a rewrite for the system prompt, so the model can disown it.

    The user asked their question in their own words; retrieval answered a
    different one.  Stating the interpretation lets the model flag a bad
    resolution instead of confidently answering the wrong question.
    """
    if not resolved.is_followup or not resolved.was_rewritten:
        return ""

    return (
        "Query Interpretation:\n"
        "------------------\n"
        f"The question is a follow-up. It was interpreted in context as: "
        f'"{resolved.search_query}", and the retrieved context below was '
        "fetched for that interpretation. Answer the user's original question. "
        "If the retrieved context shows the interpretation was wrong, say so "
        "instead of answering the wrong question."
    )
