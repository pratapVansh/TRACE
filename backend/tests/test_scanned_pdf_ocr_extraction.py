from unittest.mock import patch

import fitz
import pytest

from app.core.config import settings
from app.services.document_processing_exceptions import (
    ImageOcrExtractionError,
    ScannedPdfOcrExtractionError,
)
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


class TestOneBadPageDoesNotLoseTheDocument:
    """A single unreadable page used to discard the whole extraction.

    The page loop raised ``ScannedPdfOcrExtractionError`` on the first failure,
    so a long scan with one corrupt page yielded no text at all — and because
    the ingestion job then retried, every expensive page was re-run twice more
    before the document failed permanently. At the measured ~9.4 s per page
    that is a costly way to produce nothing.
    """

    @patch("app.services.scanned_pdf_ocr_extraction.extract_image_text")
    def test_keeps_the_pages_that_did_read(self, mock_ocr) -> None:
        mock_ocr.side_effect = [
            ImageOcrExtractionResult(full_text="First page OCR", has_text=True),
            ImageOcrExtractionError("tesseract blew up on page 2"),
            ImageOcrExtractionResult(full_text="Third page OCR", has_text=True),
        ]

        result = extract_scanned_pdf_text(_build_blank_pdf(page_count=3))

        assert result is not None
        assert result.has_text is True
        assert "First page OCR" in result.full_text
        assert "Third page OCR" in result.full_text
        assert result.failed_pages == (2,)
        assert result.is_partial is True
        # The failed page keeps its slot so page numbering stays truthful.
        assert [p.page_number for p in result.pages] == [1, 2, 3]
        assert result.pages[1].text == ""

    @patch("app.services.scanned_pdf_ocr_extraction.extract_image_text")
    def test_confidence_ignores_the_failed_page(self, mock_ocr) -> None:
        mock_ocr.side_effect = [
            ImageOcrExtractionResult(full_text="ok", has_text=True, confidence=0.9),
            ImageOcrExtractionError("boom"),
        ]

        result = extract_scanned_pdf_text(_build_blank_pdf(page_count=2))

        assert result.confidence == pytest.approx(0.9)

    @patch("app.services.scanned_pdf_ocr_extraction.extract_image_text")
    def test_every_page_failing_is_still_an_error(self, mock_ocr) -> None:
        """Nothing to index is an outage, and the retry is worth taking."""
        mock_ocr.side_effect = ImageOcrExtractionError("tesseract missing")

        with pytest.raises(ScannedPdfOcrExtractionError):
            extract_scanned_pdf_text(_build_blank_pdf(page_count=3))


class TestPageCap:
    """OCR cost per document must be bounded.

    Measured at ~9.4 s per page at 300 DPI, and the ingestion queue drains
    serially on one worker, so an unbounded page count lets a single scan stall
    every other document behind it.
    """

    @patch("app.services.scanned_pdf_ocr_extraction.extract_image_text")
    def test_stops_at_the_configured_page_limit(self, mock_ocr, monkeypatch) -> None:
        monkeypatch.setattr(settings, "ocr_max_pages", 2)
        mock_ocr.return_value = ImageOcrExtractionResult(full_text="page", has_text=True)

        result = extract_scanned_pdf_text(_build_blank_pdf(page_count=5))

        assert mock_ocr.call_count == 2, "pages past the cap must not be OCR'd"
        assert result.skipped_pages == 3
        assert result.is_partial is True
        # page_count still reports the real document, not what was read.
        assert result.page_count == 5
        assert len(result.pages) == 2

    @patch("app.services.scanned_pdf_ocr_extraction.extract_image_text")
    def test_documents_within_the_cap_are_untouched(self, mock_ocr, monkeypatch) -> None:
        monkeypatch.setattr(settings, "ocr_max_pages", 100)
        mock_ocr.return_value = ImageOcrExtractionResult(full_text="page", has_text=True)

        result = extract_scanned_pdf_text(_build_blank_pdf(page_count=3))

        assert mock_ocr.call_count == 3
        assert result.skipped_pages == 0
        assert result.is_partial is False

    @patch("app.services.scanned_pdf_ocr_extraction.extract_image_text")
    def test_a_zero_or_negative_cap_still_reads_one_page(self, mock_ocr, monkeypatch) -> None:
        """A misconfigured ceiling must not silently disable OCR entirely."""
        monkeypatch.setattr(settings, "ocr_max_pages", 0)
        mock_ocr.return_value = ImageOcrExtractionResult(full_text="page", has_text=True)

        result = extract_scanned_pdf_text(_build_blank_pdf(page_count=3))

        assert mock_ocr.call_count == 1
        assert result.skipped_pages == 2
