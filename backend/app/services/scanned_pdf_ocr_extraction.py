from dataclasses import dataclass

import fitz

from app.core.config import settings
from app.core.logging import logger
from app.services.document_processing_exceptions import (
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
    # Pages that raised during OCR and were skipped, 1-based. The rest of the
    # document is still returned; see ``extract_scanned_pdf_text``.
    failed_pages: tuple[int, ...] = ()
    # Pages past ``ocr_max_pages`` that were never attempted.
    skipped_pages: int = 0

    @property
    def is_low_confidence(self) -> bool:
        """True when the mean page confidence fell below the configured floor."""
        return (
            self.confidence is not None
            and self.confidence < settings.ocr_min_confidence
        )

    @property
    def is_partial(self) -> bool:
        """True when some of the document was not read.

        Callers flag this rather than treating the text as complete: a
        truncated or partly-failed extraction indexes cleanly and is otherwise
        indistinguishable from a whole one.
        """
        return bool(self.failed_pages) or self.skipped_pages > 0


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
        failed: list[int] = []

        # Bound the work one document may cost. OCR is the most expensive path
        # in ingestion and the queue drains serially, so an unbounded page
        # count lets one document stall every other. Measured on this hardware
        # at the configured 300 DPI: ~9.4 s per page end to end (~1.2 s of it
        # preprocessing, the rest Tesseract). See ``ocr_max_pages``.
        limit = max(settings.ocr_max_pages, 1)
        pages_to_read = min(document.page_count, limit)
        skipped = document.page_count - pages_to_read
        if skipped > 0:
            logger.warning(
                "Scanned PDF has %d pages; OCR limited to the first %d "
                "(ocr_max_pages). %d page(s) will not be indexed.",
                document.page_count, pages_to_read, skipped,
            )

        for page_index in range(pages_to_read):
            page = document[page_index]
            try:
                image_bytes = _render_page_to_png(page)
                # The page was rendered here, so the render DPI is known
                # exactly — PyMuPDF's PNG metadata reports 96 regardless.
                ocr_result = extract_image_text(image_bytes, source_dpi=RENDER_DPI)
            except Exception as exc:
                # One unreadable page used to abort the whole document, so a
                # 100-page scan with a single bad page yielded no text at all —
                # and the job then retried, repeating every expensive page
                # before failing permanently. Skip the page instead and keep
                # what the rest of the document says.
                logger.warning(
                    "OCR failed on scanned PDF page %d, skipping it: %s",
                    page_index + 1, exc,
                )
                failed.append(page_index + 1)
                pages.append(ExtractedPage(page_number=page_index + 1, text=""))
                continue

            if ocr_result.confidence is not None:
                confidences.append(ocr_result.confidence)

            pages.append(
                ExtractedPage(
                    page_number=page_index + 1,
                    text=ocr_result.full_text,
                ),
            )

        # Every attempted page failing is an outage, not a partial read: there
        # is nothing to index and the retry is worth taking.
        if failed and len(failed) == pages_to_read:
            raise ScannedPdfOcrExtractionError(
                f"OCR failed on all {pages_to_read} page(s) of the scanned PDF",
            )

        full_text = _join_page_text(pages)
        return ScannedPdfOcrResult(
            pages=tuple(pages),
            full_text=full_text,
            page_count=document.page_count,
            has_text=bool(full_text.strip()),
            confidence=(sum(confidences) / len(confidences)) if confidences else None,
            failed_pages=tuple(failed),
            skipped_pages=skipped,
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
