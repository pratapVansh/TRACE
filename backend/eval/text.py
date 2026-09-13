"""Text normalisation and matching shared by the validator and the metrics.

Two strengths of normalisation:

- ``normalize_light`` for evidence snippets, which are copied verbatim from the
  indexed chunks: unicode-compatible forms, case and whitespace only.
- ``normalize`` for answer text and accepted phrasings, which also folds the
  spellings a model varies freely: unicode hyphens (live answers use U+2011),
  "per cent" / "percent", "deg C" / "degrees Celsius" / "°C", "m^3" / "m³".

``contains_phrase`` is number-boundary aware, so "44 barg" does not match inside
"44.5 barg" and "34" does not match inside "340".
"""

import re
import unicodedata

_DASHES = re.compile("[\u2010-\u2015\u2212]")
_PERCENT = re.compile(r"\bper\s*cent\b|\bpercent\b")
_CELSIUS = re.compile(r"\b(?:degrees?|deg)\.?\s*(?:celsius|c)\b|°\s*c\b")
_WHITESPACE = re.compile(r"\s+")
_NUMBER_UNIT_GAP = re.compile(r"(\d)\s+(%|°c|ω)")


def normalize_light(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return _WHITESPACE.sub(" ", text).strip()


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    # Markdown emphasis splits phrases in model answers ("**2 pcs**").
    text = text.replace("*", "").replace("`", "")
    text = _DASHES.sub("-", text)
    text = _PERCENT.sub("%", text)
    text = _CELSIUS.sub("°c", text)
    text = text.replace("m^3", "m3")
    text = _WHITESPACE.sub(" ", text).strip()
    return _NUMBER_UNIT_GAP.sub(r"\1\2", text)


def phrase_pattern(phrase: str) -> re.Pattern | None:
    """Compile an accepted phrasing into a boundary-aware pattern."""
    normalized = normalize(phrase)
    if not normalized:
        return None
    pattern = re.escape(normalized)
    if normalized[0].isdigit():
        pattern = r"(?<![\d.])" + pattern
    if normalized[-1].isdigit():
        pattern = pattern + r"(?![\d]|[.,]\d)"
    return re.compile(pattern)


def contains_phrase(normalized_text: str, phrase: str) -> bool:
    """True when *phrase* occurs in text already passed through ``normalize``."""
    pattern = phrase_pattern(phrase)
    return bool(pattern and pattern.search(normalized_text))


def contains_any(normalized_text: str, phrases: list[str]) -> bool:
    return any(contains_phrase(normalized_text, p) for p in phrases)


def contains_evidence(chunk_text: str, snippet: str) -> bool:
    return normalize_light(snippet) in normalize_light(chunk_text)


def is_bare_number(phrase: str) -> bool:
    return bool(re.fullmatch(r"[\d.,]+", normalize(phrase)))
