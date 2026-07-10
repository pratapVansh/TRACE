from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw
from pytesseract import TesseractNotFoundError

from app.services.document_processing_exceptions import ImageOcrExtractionError
from app.services.image_ocr_extraction import (
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


@patch("app.services.image_ocr_extraction.pytesseract.image_to_string")
def test_extract_image_text_returns_ocr_text(mock_ocr) -> None:
    mock_ocr.return_value = "  Asset Tag P-101  "

    result = extract_image_text(_build_png_with_text_label())

    assert result.full_text == "Asset Tag P-101"
    assert result.has_text is True
    mock_ocr.assert_called_once()


@patch("app.services.image_ocr_extraction.pytesseract.image_to_string")
def test_extract_image_text_handles_empty_ocr_result(mock_ocr) -> None:
    mock_ocr.return_value = "   "

    result = extract_image_text(_build_png_with_text_label())

    assert result.full_text == ""
    assert result.has_text is False


def test_extract_image_text_rejects_empty_bytes() -> None:
    with pytest.raises(ImageOcrExtractionError, match="empty"):
        extract_image_text(b"")


def test_extract_image_text_rejects_invalid_bytes() -> None:
    with pytest.raises(ImageOcrExtractionError, match="Failed to open image"):
        extract_image_text(b"not-an-image")


@patch(
    "app.services.image_ocr_extraction.pytesseract.image_to_string",
    side_effect=TesseractNotFoundError,
)
def test_extract_image_text_reports_missing_tesseract(_mock_ocr) -> None:
    with pytest.raises(ImageOcrExtractionError, match="Tesseract OCR is not installed"):
        extract_image_text(_build_png_with_text_label())
