import fitz
import pytest

from app.services.document_processing_exceptions import PdfTextExtractionError
from app.services.pdf_text_extraction import extract_pdf_text


def _build_text_pdf(*lines: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    y_position = 72
    for line in lines:
        page.insert_text((72, y_position), line)
        y_position += 24
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


def test_extract_pdf_text_reads_every_page() -> None:
    content = _build_text_pdf("Page one text", "Still page one")

    result = extract_pdf_text(content)

    assert result.page_count == 1
    assert result.requires_ocr is False
    assert "Page one text" in result.full_text
    assert len(result.pages) == 1
    assert result.pages[0].page_number == 1
    assert "Page one text" in result.pages[0].text


def test_extract_pdf_text_handles_multi_page_documents() -> None:
    document = fitz.open()
    first_page = document.new_page()
    first_page.insert_text((72, 72), "First page content")
    second_page = document.new_page()
    second_page.insert_text((72, 72), "Second page content")
    content = document.tobytes()
    document.close()

    result = extract_pdf_text(content)

    assert result.page_count == 2
    assert len(result.pages) == 2
    assert result.pages[0].text == "First page content"
    assert result.pages[1].text == "Second page content"
    assert "First page content" in result.full_text
    assert "Second page content" in result.full_text


def test_extract_pdf_text_flags_scanned_pdf_without_text_layer() -> None:
    content = _build_blank_pdf(page_count=2)

    result = extract_pdf_text(content)

    assert result.page_count == 2
    assert result.requires_ocr is True
    assert result.full_text == ""
    assert result.pages[0].text == ""
    assert result.pages[1].text == ""


def test_extract_pdf_text_rejects_empty_bytes() -> None:
    with pytest.raises(PdfTextExtractionError, match="empty"):
        extract_pdf_text(b"")


def test_extract_pdf_text_rejects_invalid_pdf_bytes() -> None:
    with pytest.raises(PdfTextExtractionError, match="Failed to open PDF"):
        extract_pdf_text(b"not-a-pdf")
