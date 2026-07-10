from unittest.mock import patch

import pytest
from langdetect import LangDetectException
from langdetect.language import Language

from app.services.language_detection import (
    DETECTED_LANGUAGE_KEY,
    UNKNOWN_LANGUAGE_CODE,
    detect_document_language,
)


def test_detect_document_language_identifies_english() -> None:
    text = (
        "This safety procedure describes the inspection steps for pressure relief "
        "valves and associated piping systems."
    )

    result = detect_document_language(text)

    assert result.code == "en"
    assert result.confidence is not None
    assert result.confidence > 0.5


def test_detect_document_language_returns_unknown_for_empty_text() -> None:
    result = detect_document_language("")

    assert result.code == UNKNOWN_LANGUAGE_CODE
    assert result.confidence is None


def test_detect_document_language_returns_unknown_for_short_text() -> None:
    result = detect_document_language("P-101")

    assert result.code == UNKNOWN_LANGUAGE_CODE
    assert result.confidence is None


def test_detect_document_language_returns_unknown_for_none() -> None:
    result = detect_document_language(None)

    assert result.code == UNKNOWN_LANGUAGE_CODE
    assert result.confidence is None


@patch(
    "app.services.language_detection.detect_langs",
    side_effect=LangDetectException("UNKNOWN", "No features in text."),
)
def test_detect_document_language_handles_detection_failure(_mock_detect) -> None:
    result = detect_document_language(
        "This is enough text to attempt detection but the engine failed.",
    )

    assert result.code == UNKNOWN_LANGUAGE_CODE
    assert result.confidence is None


@patch("app.services.language_detection.detect_langs", return_value=[])
def test_detect_document_language_handles_empty_detection_results(_mock_detect) -> None:
    result = detect_document_language(
        "This is enough text to attempt detection but no language was returned.",
    )

    assert result.code == UNKNOWN_LANGUAGE_CODE
    assert result.confidence is None


def test_detected_language_storage_shape() -> None:
    result = detect_document_language(None)

    stored = result.to_storage_dict()
    assert stored == {"code": UNKNOWN_LANGUAGE_CODE, "confidence": None}
    assert DETECTED_LANGUAGE_KEY == "detected_language"


@patch(
    "app.services.language_detection.detect_langs",
    return_value=[Language(lang="fr", prob=0.91)],
)
def test_detect_document_language_uses_best_detection(_mock_detect) -> None:
    result = detect_document_language(
        "Cette procedure de securite decrit les etapes d inspection des valves "
        "de surpression et des tuyauteries associees.",
    )

    assert result.code == "fr"
    assert result.confidence == 0.91
