from dataclasses import dataclass

import fitz

from app.services.document_processing_exceptions import (
    ImageOcrExtractionError,
    PdfTextExtractionError,
    ScannedPdfOcrExtractionError,
)
from app.services.image_ocr_extraction import extract_image_text
from app.services.pdf_text_extraction import ExtractedPage, extract_pdf_text


EXTRACTION_METHOD = "pymupdf+tesseract"
RENDER_DPI = 200


@dataclass(frozen=True, slots=True)
class ScannedPdfOcrResult:
    pages: tuple[ExtractedPage, ...]
    full_text: str
    page_count: int
    has_text: bool


def extract_scanned_pdf_text(content: bytes) -> ScannedPdfOcrResult | None:
    """
    OCR a scanned PDF by rendering each page to an image and reusing image OCR.

    Returns ``None`` when the PDF already has selectable text.
    """
    try:
        pdf_result = extract_pdf_text(content)
    except PdfTextExtractionError as exc:
        raise ScannedPdfOcrExtractionError(str(exc)) from exc

    if not pdf_result.requires_ocr:
        return None

    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        raise ScannedPdfOcrExtractionError("Failed to open scanned PDF for OCR") from exc

    try:
        pages: list[ExtractedPage] = []
        for page_index in range(document.page_count):
            page = document[page_index]
            try:
                image_bytes = _render_page_to_png(page)
                ocr_result = extract_image_text(image_bytes)
            except ImageOcrExtractionError as exc:
                raise ScannedPdfOcrExtractionError(
                    f"Failed to OCR scanned PDF page {page_index + 1}",
                ) from exc

            pages.append(
                ExtractedPage(
                    page_number=page_index + 1,
                    text=ocr_result.full_text,
                ),
            )

        full_text = _join_page_text(pages)
        return ScannedPdfOcrResult(
            pages=tuple(pages),
            full_text=full_text,
            page_count=document.page_count,
            has_text=bool(full_text.strip()),
        )
    finally:
        document.close()


def _join_page_text(pages: list[ExtractedPage]) -> str:
    return "\n\n".join(page.text for page in pages if page.text)


def _render_page_to_png(page: fitz.Page) -> bytes:
    zoom = RENDER_DPI / 72
    matrix = fitz.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    return pixmap.tobytes("png")
