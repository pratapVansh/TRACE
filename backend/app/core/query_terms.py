"""Reduction of a natural-language query to searchable keyword terms.

Shared by keyword search over the Qdrant ``content`` index and by entity
lookup in the knowledge graph. Both match stored text against a query, and
both return nothing for a whole question unless it is first broken into
terms, so they tokenize it the same way rather than each inventing its own
rules.
"""

import re

# Matches the ``min_token_len`` of the content text index, so the query is
# not built from terms the index never stored.
MIN_QUERY_TERM_LEN = 2
# Cap on OR clauses in a keyword filter — a long question would otherwise
# build a filter with a clause per word, most of them noise.
MAX_QUERY_TERMS = 12
# Common words carry no discriminating power but match nearly every chunk,
# so including them in an OR filter returns the whole collection.
_STOPWORDS = frozenset(
    """
    a an and are as at be by did do does for from had has have how i if in is
    it its me my of on or our so than that the their them then there these
    they this to was we were what when where which who why will with would
    you your
    """.split()
)

# Keeps hyphens and dots inside tokens so identifiers survive intact:
# "P-101" and "E-4412" must not be split into meaningless fragments.
_TERM_RE = re.compile(r"[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*")


def _extract_query_terms(query_text: str) -> list[str]:
    """Reduce a natural-language query to searchable keyword terms."""
    terms: list[str] = []
    seen: set[str] = set()

    for raw in _TERM_RE.findall(query_text or ""):
        term = raw.strip("-.")
        if len(term) < MIN_QUERY_TERM_LEN:
            continue
        lowered = term.casefold()
        if lowered in _STOPWORDS or lowered in seen:
            continue
        seen.add(lowered)
        terms.append(term)

    if not terms:
        return []

    # Identifiers ("P-101", "E-4412") are the terms keyword search exists to
    # catch, so they are kept ahead of ordinary words when the cap applies.
    terms.sort(key=lambda t: (_term_rank(t), -len(t)))
    return terms[:MAX_QUERY_TERMS]


def _term_rank(term: str) -> int:
    """Order terms by how discriminating they are, lowest first.

    A digit alone is too weak a signal — "word10" and "2026" have one without
    being identifiers. What distinguishes an asset tag or error code is a
    digit *and* a separator ("P-101", "E-4412", "v1.2"), so that pattern
    ranks highest.
    """
    has_digit = any(ch.isdigit() for ch in term)
    has_separator = "-" in term or "." in term
    if has_digit and has_separator:
        return 0
    if has_digit:
        return 1
    return 2
