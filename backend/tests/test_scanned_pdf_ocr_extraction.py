from unittest.mock import patch

import fitz
import pytest

from app.services.document_processing_exceptions import ScannedPdfOcrExtractionError
from app.services.image_ocr_extraction import ImageOcrExtractionResult
from app.services.scanned_pdf_ocr_extraction import extract_scanned_pdf_text


def _build_text_pdf(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    content = document.tobytes()
    document.close()
    return content


def _build_blank_pdf(page_count: int = 1) -> bytes:
    document = fitz.open()
    for _ in range(page_count):
        document.new_page()
    content = document.tobytes()
    document.close()
    return content


def test_extract_scanned_pdf_text_skips_text_based_pdf() -> None:
    result = extract_scanned_pdf_text(_build_text_pdf("Selectable PDF text"))

    assert result is None


@patch("app.services.scanned_pdf_ocr_extraction.extract_image_text")
def test_extract_scanned_pdf_text_ocrs_and_merges_pages(mock_ocr) -> None:
    mock_ocr.side_effect = [
        ImageOcrExtractionResult(full_text="First page OCR", has_text=True),
        ImageOcrExtractionResult(full_text="Second page OCR", has_text=True),
    ]

    result = extract_scanned_pdf_text(_build_blank_pdf(page_count=2))

    assert result is not None
    assert result.page_count == 2
    assert result.has_text is True
    assert "First page OCR" in result.full_text
    assert "Second page OCR" in result.full_text
    assert result.pages[0].text == "First page OCR"
    assert result.pages[1].text == "Second page OCR"
    assert mock_ocr.call_count == 2


@patch(
    "app.services.scanned_pdf_ocr_extraction.extract_image_text",
    return_value=ImageOcrExtractionResult(full_text="", has_text=False),
)
def test_extract_scanned_pdf_text_handles_empty_ocr_result(_mock_ocr) -> None:
    result = extract_scanned_pdf_text(_build_blank_pdf())

    assert result is not None
    assert result.full_text == ""
    assert result.has_text is False


def test_extract_scanned_pdf_text_rejects_empty_bytes() -> None:
    with pytest.raises(ScannedPdfOcrExtractionError):
        extract_scanned_pdf_text(b"")
