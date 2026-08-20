from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw
from pytesseract import TesseractNotFoundError

from app.services.document_processing_exceptions import ImageOcrExtractionError
from app.processing.ocr.engine import OcrResult
from app.services.image_ocr_extraction import (
    _engine,
    extract_image_text,
    is_supported_image_extension,
)


def _build_png_with_text_label() -> bytes:
    image = Image.new("RGB", (320, 120), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((10, 40), "P-101", fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_is_supported_image_extension() -> None:
    assert is_supported_image_extension("png") is True
    assert is_supported_image_extension("jpg") is True
    assert is_supported_image_extension("jpeg") is True
    assert is_supported_image_extension("pdf") is False


def _patch_engine(text: str, confidence: float | None = 0.9):
    """Stub the shared engine's OCR call, leaving preprocessing untouched."""
    return patch.object(
        _engine(),
        "ocr_image",
        return_value=OcrResult(text=text, confidence=confidence),
    )


def test_extract_image_text_returns_ocr_text() -> None:
    with _patch_engine("  Asset Tag P-101  ") as mock_ocr:
        result = extract_image_text(_build_png_with_text_label())

    assert result.full_text == "Asset Tag P-101"
    assert result.has_text is True
    assert result.confidence == 0.9
    mock_ocr.assert_called_once()


def test_extract_image_text_handles_empty_ocr_result() -> None:
    with _patch_engine("   "):
        result = extract_image_text(_build_png_with_text_label())

    assert result.full_text == ""
    assert result.has_text is False


def test_extract_image_text_preserves_line_structure() -> None:
    """Line breaks must survive: the chunker splits on them."""
    with _patch_engine("Tag: P-101" + chr(10) + "Service: Feed Pump"):
        result = extract_image_text(_build_png_with_text_label())

    assert result.full_text == "Tag: P-101" + chr(10) + "Service: Feed Pump"


def test_low_confidence_extraction_is_flagged() -> None:
    with _patch_engine("smudged text", confidence=0.2):
        result = extract_image_text(_build_png_with_text_label())

    assert result.is_low_confidence is True


def test_confident_extraction_is_not_flagged() -> None:
    with _patch_engine("clean text", confidence=0.95):
        result = extract_image_text(_build_png_with_text_label())

    assert result.is_low_confidence is False


def test_extract_image_text_rejects_empty_bytes() -> None:
    with pytest.raises(ImageOcrExtractionError, match="empty"):
        extract_image_text(b"")


def test_extract_image_text_rejects_invalid_bytes() -> None:
    with pytest.raises(ImageOcrExtractionError, match="Failed to open image"):
        extract_image_text(b"not-an-image")


def test_extract_image_text_reports_missing_tesseract() -> None:
    with patch.object(_engine(), "ocr_image", side_effect=TesseractNotFoundError):
        with pytest.raises(
            ImageOcrExtractionError, match="Tesseract OCR is not installed"
        ):
            extract_image_text(_build_png_with_text_label())
