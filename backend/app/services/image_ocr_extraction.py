from dataclasses import dataclass
from io import BytesIO

import pytesseract
from PIL import Image, UnidentifiedImageError
from pytesseract import TesseractNotFoundError

from app.services.document_processing_exceptions import ImageOcrExtractionError

EXTRACTION_METHOD = "tesseract"
SUPPORTED_IMAGE_EXTENSIONS = frozenset({"png", "jpg", "jpeg"})
MIN_MEANINGFUL_TEXT_CHARS = 1


@dataclass(frozen=True, slots=True)
class ImageOcrExtractionResult:
    full_text: str
    has_text: bool


def extract_image_text(content: bytes) -> ImageOcrExtractionResult:
    """Extract readable text from a PNG or JPG image using Tesseract OCR."""
    if not content:
        raise ImageOcrExtractionError("Image file is empty")

    try:
        image = Image.open(BytesIO(content))
    except UnidentifiedImageError as exc:
        raise ImageOcrExtractionError("Failed to open image for OCR") from exc
    except Exception as exc:
        raise ImageOcrExtractionError("Failed to read image bytes for OCR") from exc

    try:
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        text = pytesseract.image_to_string(image).strip()
    except TesseractNotFoundError as exc:
        raise ImageOcrExtractionError(
            "Tesseract OCR is not installed or not available on PATH",
        ) from exc
    except Exception as exc:
        raise ImageOcrExtractionError("Failed to perform OCR on image") from exc
    finally:
        image.close()

    has_text = len(text) >= MIN_MEANINGFUL_TEXT_CHARS
    return ImageOcrExtractionResult(full_text=text, has_text=has_text)


def is_supported_image_extension(extension: str) -> bool:
    return extension.lower().lstrip(".") in SUPPORTED_IMAGE_EXTENSIONS
