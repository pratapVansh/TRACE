from dataclasses import dataclass

import fitz

from app.services.document_processing_exceptions import PdfTextExtractionError

EXTRACTION_METHOD = "pymupdf"
MIN_MEANINGFUL_TEXT_CHARS = 10


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class PdfTextExtractionResult:
    pages: tuple[ExtractedPage, ...]
    full_text: str
    page_count: int
    requires_ocr: bool


def extract_pdf_text(content: bytes) -> PdfTextExtractionResult:
    """
    Extract text from every page of a PDF using PyMuPDF.

    Scanned PDFs without a text layer return empty page text and ``requires_ocr=True``.
    """
    if not content:
        raise PdfTextExtractionError("PDF file is empty")

    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        raise PdfTextExtractionError("Failed to open PDF for text extraction") from exc

    try:
        if document.page_count == 0:
            raise PdfTextExtractionError("PDF contains no pages")

        pages: list[ExtractedPage] = []
        for page_index in range(document.page_count):
            page = document[page_index]
            try:
                text = page.get_text("text").strip()
            except Exception as exc:
                raise PdfTextExtractionError(
                    f"Failed to extract text from page {page_index + 1}",
                ) from exc

            pages.append(
                ExtractedPage(
                    page_number=page_index + 1,
                    text=text,
                ),
            )

        full_text = _join_page_text(pages)
        meaningful_chars = len(full_text.strip())
        requires_ocr = meaningful_chars < MIN_MEANINGFUL_TEXT_CHARS

        return PdfTextExtractionResult(
            pages=tuple(pages),
            full_text=full_text,
            page_count=document.page_count,
            requires_ocr=requires_ocr,
        )
    finally:
        document.close()


def _join_page_text(pages: list[ExtractedPage]) -> str:
    return "\n\n".join(page.text for page in pages if page.text)
