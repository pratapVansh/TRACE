from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError
from pytesseract import TesseractNotFoundError

from app.core.config import settings
from app.processing.ocr.engine import OcrEngine
from app.services.document_processing_exceptions import ImageOcrExtractionError

EXTRACTION_METHOD = "tesseract"
SUPPORTED_IMAGE_EXTENSIONS = frozenset({"png", "jpg", "jpeg"})
MIN_MEANINGFUL_TEXT_CHARS = 1

# Building the engine costs a Tesseract version probe and a preprocessing
# pipeline, so it is shared across pages rather than rebuilt per call.
_ENGINE: OcrEngine | None = None


def _engine() -> OcrEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = OcrEngine()
    return _ENGINE


@dataclass(frozen=True, slots=True)
class ImageOcrExtractionResult:
    full_text: str
    has_text: bool
    confidence: float | None = None
    language: str = "eng"

    @property
    def is_low_confidence(self) -> bool:
        """True when Tesseract scored this extraction below the configured floor.

        Text can come back well-formed but wrong on a poor scan, so callers
        flag the document for review instead of treating it as clean.
        """
        return self.confidence is not None and self.confidence < settings.ocr_min_confidence


def extract_image_text(
    content: bytes, source_dpi: float | None = None
) -> ImageOcrExtractionResult:
    """Extract readable text from a PNG or JPG image using Tesseract OCR.

    Runs through ``OcrEngine`` so the image is deskewed, denoised and
    resampled to 300 DPI first, and so per-word confidence comes back with
    the text. Calling Tesseract directly on the raw upload — as this did
    previously — skips all of that and measurably loses accuracy on scans.

    ``source_dpi`` lets a caller that rendered the image itself state the
    real resolution, which is more trustworthy than the file's metadata.
    """
    if not content:
        raise ImageOcrExtractionError("Image file is empty")

    try:
        image = Image.open(BytesIO(content))
    except UnidentifiedImageError as exc:
        raise ImageOcrExtractionError("Failed to open image for OCR") from exc
    except Exception as exc:
        raise ImageOcrExtractionError("Failed to read image bytes for OCR") from exc

    try:
        result = _engine().ocr_image(image, source_dpi=source_dpi)
    except TesseractNotFoundError as exc:
        raise ImageOcrExtractionError(
            "Tesseract OCR is not installed or not available on PATH",
        ) from exc
    except Exception as exc:
        raise ImageOcrExtractionError("Failed to perform OCR on image") from exc
    finally:
        image.close()

    text = result.text.strip()
    return ImageOcrExtractionResult(
        full_text=text,
        has_text=len(text) >= MIN_MEANINGFUL_TEXT_CHARS,
        confidence=result.confidence,
        language=result.language,
    )


def is_supported_image_extension(extension: str) -> bool:
    return extension.lower().lstrip(".") in SUPPORTED_IMAGE_EXTENSIONS
