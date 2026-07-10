from dataclasses import dataclass

from langdetect import DetectorFactory, LangDetectException, detect_langs

DetectorFactory.seed = 0

DETECTED_LANGUAGE_KEY = "detected_language"
UNKNOWN_LANGUAGE_CODE = "unknown"
MIN_TEXT_LENGTH = 20


@dataclass(frozen=True, slots=True)
class LanguageDetectionResult:
    code: str
    confidence: float | None

    def to_storage_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "confidence": self.confidence,
        }


def detect_document_language(text: str | None) -> LanguageDetectionResult:
    """Detect the language of extracted document text."""
    if text is None:
        return _unknown_language()

    stripped = text.strip()
    if len(stripped) < MIN_TEXT_LENGTH:
        return _unknown_language()

    try:
        detections = detect_langs(stripped)
    except LangDetectException:
        return _unknown_language()

    if not detections:
        return _unknown_language()

    best = detections[0]
    if not best.lang:
        return _unknown_language()

    return LanguageDetectionResult(
        code=best.lang,
        confidence=round(float(best.prob), 4),
    )


def _unknown_language() -> LanguageDetectionResult:
    return LanguageDetectionResult(
        code=UNKNOWN_LANGUAGE_CODE,
        confidence=None,
    )
