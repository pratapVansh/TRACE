from __future__ import annotations

from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from time import monotonic

import fitz
from PIL import Image

from app.core.config import settings
from app.core.logging import logger
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.processing.base import BaseProcessor
from app.processing.ocr.engine import OcrEngine
from app.processing.ocr.preprocessing import PreprocessingPipeline

SCANNED_PAGE_TEXT_THRESHOLD = 20
PAGE_SEPARATOR = "\n\n--- Page {page} ---\n\n"


class PdfProcessor(BaseProcessor):
    name = "pdf_processor"
    supported_extensions = frozenset({"pdf"})
    supported_mime_types = frozenset({"application/pdf"})

    def __init__(
        self,
        ocr_engine: OcrEngine | None = None,
        preprocessing: PreprocessingPipeline | None = None,
    ) -> None:
        self._ocr = ocr_engine or OcrEngine(lang="eng", preprocessing=preprocessing or PreprocessingPipeline())
        self._ocr_confidences: list[float] = []

    async def extract_text(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> str:
        file_path = self._resolve_path(version)
        logger.info("Opening PDF document_id=%s path=%s", document.id, file_path)

        try:
            doc = fitz.open(file_path)
        except Exception as exc:
            logger.error("Failed to open PDF document_id=%s: %s", document.id, exc)
            return ""

        try:
            if doc.is_encrypted or doc.needs_pass:
                logger.warning("Encrypted PDF, cannot extract text document_id=%s", document.id)
                return ""

            total_pages = doc.page_count
            scanned = self._is_scanned(doc)
            pages_text: list[str] = []

            for page_num in range(total_pages):
                try:
                    page = doc.load_page(page_num)
                    text = page.get_text().strip()
                    if scanned or not text:
                        ocr_text = self._ocr_pdf_page(page, page_num + 1, document.id)
                        if ocr_text:
                            pages_text.append(ocr_text)
                    elif text:
                        pages_text.append(PAGE_SEPARATOR.format(page=page_num + 1) + text)
                except ValueError:
                    logger.warning("Could not load page %d document_id=%s", page_num + 1, document.id)
                    continue

            return "".join(pages_text)
        finally:
            doc.close()

    async def extract_metadata(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> dict:
        file_path = self._resolve_path(version)

        try:
            doc = fitz.open(file_path)
        except Exception as exc:
            logger.error("Failed to open PDF for metadata document_id=%s: %s", document.id, exc)
            return self._fallback_metadata(document, version, file_path)

        try:
            total_pages = doc.page_count
            metadata = doc.metadata or {}
            pdf_version = self._get_pdf_version(doc)
            is_encrypted = doc.is_encrypted
            needs_ocr = False
            extracted_pages = 0
            empty_pages = 0

            if not is_encrypted and total_pages > 0:
                for page_num in range(total_pages):
                    try:
                        page = doc.load_page(page_num)
                        text = page.get_text().strip()
                        if text:
                            extracted_pages += 1
                        else:
                            empty_pages += 1
                    except ValueError:
                        pass

            if total_pages == 0:
                needs_ocr = True
            elif is_encrypted:
                extracted_pages = 0
                empty_pages = total_pages
            elif extracted_pages == 0:
                needs_ocr = True
            else:
                significant_pages = 0
                for page_num in range(total_pages):
                    try:
                        page = doc.load_page(page_num)
                        text = page.get_text().strip()
                        if len(text) >= SCANNED_PAGE_TEXT_THRESHOLD:
                            significant_pages += 1
                    except ValueError:
                        pass
                if significant_pages == 0:
                    needs_ocr = True

            result = {
                "page_count": total_pages,
                "title": metadata.get("title") or document.title,
                "author": metadata.get("author"),
                "subject": metadata.get("subject"),
                "creator": metadata.get("creator"),
                "producer": metadata.get("producer"),
                "creation_date": self._parse_pdf_date(metadata.get("creationDate")),
                "modification_date": self._parse_pdf_date(metadata.get("modDate")),
                "pdf_version": pdf_version,
                "encrypted": is_encrypted,
                "file_size": self._get_file_size(file_path),
                "extension": "pdf",
                "mime_type": version.mime_type,
                "extracted_pages": extracted_pages,
                "empty_pages": empty_pages,
            }

            if needs_ocr:
                result["requires_ocr"] = True
                logger.info("Scanned PDF detected document_id=%s", document.id)

            logger.info(
                "Metadata extracted document_id=%s pages=%d extracted=%d empty=%d",
                document.id,
                total_pages,
                extracted_pages,
                empty_pages,
            )
            return result
        finally:
            doc.close()

    async def validate(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> list[str]:
        warnings: list[str] = []
        file_path = self._resolve_path(version)

        try:
            doc = fitz.open(file_path)
        except fitz.FileDataError:
            warnings.append("Corrupted or invalid PDF file")
            return warnings
        except Exception as exc:
            warnings.append(f"Cannot open PDF: {exc}")
            return warnings

        try:
            if doc.is_encrypted:
                warnings.append("PDF is encrypted and cannot be processed")
                return warnings

            if doc.page_count == 0:
                warnings.append("PDF contains no pages")
                return warnings

            if doc.needs_pass:
                warnings.append("PDF requires a password")
                return warnings
        finally:
            doc.close()

        return warnings

    async def process(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> "ProcessingResult":
        from app.processing.models import ProcessingResult

        start = monotonic()
        warnings = await self.validate(document, version)
        if warnings:
            metadata = await self.extract_metadata(document, version)
            return ProcessingResult(
                success=True,
                document_id=document.id,
                extracted_text="",
                metadata=metadata,
                processing_time=timedelta(seconds=round(monotonic() - start, 3)),
                warnings=warnings,
            )

        metadata = await self.extract_metadata(document, version)
        text = await self.extract_text(document, version)

        needs_ocr = metadata.get("requires_ocr", False)
        processing_time = round(monotonic() - start, 3)
        metadata["processing_time"] = processing_time

        if needs_ocr:
            metadata["ocr_engine"] = "tesseract"
            metadata["ocr_language"] = self._ocr.lang
            if self._ocr_confidences:
                metadata["ocr_confidence"] = round(
                    sum(self._ocr_confidences) / len(self._ocr_confidences), 2
                )
            self._ocr_confidences.clear()
            warnings.append("OCR applied to scanned PDF")

        return ProcessingResult(
            success=True,
            document_id=document.id,
            extracted_text=text,
            metadata=metadata,
            processing_time=timedelta(seconds=processing_time),
            warnings=warnings,
        )

    def _is_scanned(self, doc: fitz.Document) -> bool:
        if doc.page_count == 0:
            return True
        significant = 0
        for i in range(doc.page_count):
            try:
                text = doc.load_page(i).get_text().strip()
                if len(text) >= SCANNED_PAGE_TEXT_THRESHOLD:
                    significant += 1
            except ValueError:
                pass
        return significant == 0

    def _ocr_pdf_page(
        self,
        page: fitz.Page,
        page_num: int,
        doc_id: object,
    ) -> str:
        if not self._ocr.is_available():
            return ""

        try:
            pix = page.get_pixmap(dpi=300, colorspace=fitz.csRGB)
            img_bytes = pix.tobytes("png")
            img = Image.open(BytesIO(img_bytes))
            result = self._ocr.ocr_image(img)
            if result.confidence is not None:
                self._ocr_confidences.append(result.confidence)
            if result.text.strip():
                return PAGE_SEPARATOR.format(page=page_num) + result.text
        except Exception as exc:
            logger.warning(
                "OCR failed for page %d document_id=%s: %s",
                page_num, doc_id, exc,
            )
        return ""
    def _get_pdf_version(doc: fitz.Document) -> str | None:
        try:
            pdf_version = doc.pdf_version
            return f"{pdf_version / 10:.1f}" if pdf_version else None
        except Exception:
            return None

    @staticmethod
    def _parse_pdf_date(date_str: str | None) -> str | None:
        if not date_str:
            return None
        try:
            if date_str == "D:now" or date_str == "now":
                from datetime import UTC
                return datetime.now(UTC).isoformat()
            clean = date_str[2:] if date_str.startswith("D:") else date_str
            parsed = datetime.strptime(clean[:14], "%Y%m%d%H%M%S")
            return parsed.isoformat()
        except (ValueError, TypeError):
            return date_str

    @staticmethod
    def _get_file_size(file_path: str) -> int | None:
        try:
            return Path(file_path).stat().st_size
        except OSError:
            return None

    @staticmethod
    def _fallback_metadata(
        document: Document,
        version: DocumentVersion,
        file_path: str,
    ) -> dict:
        return {
            "page_count": None,
            "title": document.title,
            "author": None,
            "extension": "pdf",
            "mime_type": version.mime_type,
            "file_size": PdfProcessor._get_file_size(file_path),
        }
