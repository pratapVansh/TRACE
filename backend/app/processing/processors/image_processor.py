from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from time import monotonic

from PIL import Image

from app.core.config import settings
from app.core.logging import logger
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.processing.base import BaseProcessor
from app.processing.ocr.engine import OcrEngine
from app.processing.ocr.preprocessing import PreprocessingPipeline

SUPPORTED_IMAGE_FORMATS = frozenset({"png", "jpg", "jpeg", "tiff", "bmp"})
SUPPORTED_IMAGE_MIME = frozenset({
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
})

OCR_PAGE_SEPARATOR = "\n\n--- Page 1 ---\n\n"


class ImageProcessor(BaseProcessor):
    name = "image_processor"
    supported_extensions = SUPPORTED_IMAGE_FORMATS
    supported_mime_types = SUPPORTED_IMAGE_MIME

    def __init__(
        self,
        ocr_engine: OcrEngine | None = None,
        preprocessing: PreprocessingPipeline | None = None,
    ) -> None:
        self._ocr = ocr_engine or OcrEngine(lang="eng", preprocessing=preprocessing or PreprocessingPipeline())
        self._preprocessing = preprocessing or PreprocessingPipeline()

    async def extract_text(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> str:
        file_path = self._resolve_path(version)
        ext = version.file_extension.lower()
        logger.info("Opening image document_id=%s path=%s", document.id, file_path)

        if ext not in SUPPORTED_IMAGE_FORMATS:
            logger.warning("Unsupported image format '%s' document_id=%s", ext, document.id)
            return ""

        if not self._ocr.is_available():
            logger.warning("Tesseract not available; cannot OCR image document_id=%s", document.id)
            return ""

        img = None
        try:
            img = Image.open(file_path)
            img.load()
        except Exception as exc:
            logger.error("Failed to open image document_id=%s: %s", document.id, exc)
            return ""

        ocr_result = self._ocr.ocr_image(img)
        if ocr_result.text:
            return OCR_PAGE_SEPARATOR + ocr_result.text
        return ""

    async def _ocr_confidence(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> float | None:
        file_path = self._resolve_path(version)
        try:
            with Image.open(file_path) as img:
                img.load()
            result = self._ocr.ocr_image(img)
            return result.confidence
        except Exception:
            return None

    async def extract_metadata(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> dict:
        file_path = self._resolve_path(version)
        ext = version.file_extension.lower()
        result: dict = {
            "format": ext,
            "extension": ext,
            "mime_type": version.mime_type,
            "file_size": self._get_file_size(file_path),
            "ocr_engine": "tesseract",
            "ocr_language": self._ocr.lang,
            "requires_manual_review": False,
        }

        try:
            with Image.open(file_path) as img:
                result["width"] = img.width
                result["height"] = img.height
                result["image_count"] = 1
                dpi = img.info.get("dpi")
                if dpi and dpi[0] and dpi[0] > 0:
                    result["dpi"] = round(float(dpi[0]), 1)
                else:
                    result["dpi"] = None
                result["mode"] = img.mode
        except Exception as exc:
            logger.error("Failed to read image metadata document_id=%s: %s", document.id, exc)
            result["width"] = None
            result["height"] = None
            result["image_count"] = 0
            result["dpi"] = None
            result["mode"] = None

        logger.info(
            "Metadata extracted document_id=%s format=%s dimensions=%sx%s",
            document.id,
            ext,
            result.get("width"),
            result.get("height"),
        )
        return result

    async def validate(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> list[str]:
        warnings: list[str] = []
        file_path = self._resolve_path(version)
        ext = version.file_extension.lower()

        if ext not in SUPPORTED_IMAGE_FORMATS:
            warnings.append(f"Unsupported image format '.{ext}'")
            return warnings

        try:
            with Image.open(file_path) as img:
                img.load()
                if img.width == 0 or img.height == 0:
                    warnings.append("Image has zero dimensions")
                    return warnings
        except Exception as exc:
            warnings.append(f"Corrupted or invalid image file: {exc}")
            return warnings

        return warnings

    async def process(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> "ProcessingResult":
        from app.processing.models import ProcessingResult

        start = monotonic()
        warnings = await self.validate(document, version)
        metadata = await self.extract_metadata(document, version)
        text = await self.extract_text(document, version)

        is_ocr_available = self._ocr.is_available()
        if is_ocr_available:
            metadata["ocr_engine"] = "tesseract"
            metadata["ocr_language"] = self._ocr.lang
            ocr_conf = await self._ocr_confidence(document, version)
            if ocr_conf is not None:
                metadata["ocr_confidence"] = round(ocr_conf, 2)

        processing_time = monotonic() - start
        metadata["processing_time"] = round(processing_time, 3)
        metadata["page_count"] = 1

        dpi_val = metadata.get("dpi")
        low_quality = (
            dpi_val is not None
            and dpi_val > 1
            and dpi_val < 100
        )
        if low_quality:
            metadata["requires_manual_review"] = True
            warnings.append("Low-quality scan (DPI < 100), results may be unreliable")

        return ProcessingResult(
            success=not warnings,
            document_id=document.id,
            extracted_text=text,
            metadata=metadata,
            processing_time=timedelta(seconds=processing_time),
            warnings=warnings,
        )

    def _resolve_path(self, version: DocumentVersion) -> str:
        return str(settings.storage_root_path / version.storage_uri)

    @staticmethod
    def _get_file_size(file_path: str) -> int | None:
        try:
            return Path(file_path).stat().st_size
        except OSError:
            return None
