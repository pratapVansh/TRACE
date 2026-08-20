from dataclasses import dataclass

import fitz

from app.core.config import settings
from app.services.document_processing_exceptions import (
    ImageOcrExtractionError,
    PdfTextExtractionError,
    ScannedPdfOcrExtractionError,
)
from app.services.image_ocr_extraction import extract_image_text
from app.services.pdf_text_extraction import ExtractedPage, extract_pdf_text


EXTRACTION_METHOD = "pymupdf+tesseract"
# Tesseract is trained on ~300 DPI scans; rendering below that measurably
# costs accuracy on small type, which is most of a spec sheet.
RENDER_DPI = settings.ocr_render_dpi


@dataclass(frozen=True, slots=True)
class ScannedPdfOcrResult:
    pages: tuple[ExtractedPage, ...]
    full_text: str
    page_count: int
    has_text: bool
    confidence: float | None = None

    @property
    def is_low_confidence(self) -> bool:
        """True when the mean page confidence fell below the configured floor."""
        return (
            self.confidence is not None
            and self.confidence < settings.ocr_min_confidence
        )


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
        confidences: list[float] = []
        for page_index in range(document.page_count):
            page = document[page_index]
            try:
                image_bytes = _render_page_to_png(page)
                # The page was rendered here, so the render DPI is known
                # exactly — PyMuPDF's PNG metadata reports 96 regardless.
                ocr_result = extract_image_text(image_bytes, source_dpi=RENDER_DPI)
            except ImageOcrExtractionError as exc:
                raise ScannedPdfOcrExtractionError(
                    f"Failed to OCR scanned PDF page {page_index + 1}",
                ) from exc

            if ocr_result.confidence is not None:
                confidences.append(ocr_result.confidence)

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
            confidence=(sum(confidences) / len(confidences)) if confidences else None,
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
