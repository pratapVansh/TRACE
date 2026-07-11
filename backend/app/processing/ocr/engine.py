from __future__ import annotations

import time
from dataclasses import dataclass, field

import pytesseract
from PIL import Image

from app.core.logging import logger
from app.processing.ocr.preprocessing import PreprocessingPipeline


@dataclass
class OcrResult:
    text: str
    confidence: float | None = None
    language: str = "eng"
    processing_time: float = 0.0
    word_confidences: list[float] = field(default_factory=list)


class OcrEngine:
    SUPPORTED_LANGUAGES = frozenset({"eng", "fra", "deu", "spa", "ita", "por", "nld", "ara", "chi_sim", "jpn", "kor"})

    def __init__(self, lang: str = "eng", preprocessing: PreprocessingPipeline | None = None):
        self._lang = lang
        self._preprocessing = preprocessing or PreprocessingPipeline()
        self._available: bool | None = None

    @property
    def lang(self) -> str:
        return self._lang

    @lang.setter
    def lang(self, value: str) -> None:
        if value not in self.SUPPORTED_LANGUAGES:
            logger.warning("Unsupported language '%s', falling back to 'eng'", value)
            value = "eng"
        self._lang = value

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            pytesseract.get_tesseract_version()
            self._available = True
        except Exception:
            self._available = False
            logger.warning("Tesseract OCR is not available")
        return self._available

    def ocr_image(self, image: Image.Image) -> OcrResult:
        if not self.is_available():
            logger.warning("Tesseract not available; returning empty OCR result")
            return OcrResult(text="")

        start = time.monotonic()
        processed = self._preprocessing.process(image)
        ocr_data = pytesseract.image_to_data(
            processed,
            lang=self._lang,
            output_type=pytesseract.Output.DICT,
            config="--psm 3 --oem 3",
        )

        text_parts: list[str] = []
        confidences: list[float] = []
        for i, text in enumerate(ocr_data["text"]):
            text = text.strip()
            if text:
                text_parts.append(text)
                try:
                    conf = int(ocr_data["conf"][i])
                    if conf >= 0:
                        confidences.append(conf)
                except (ValueError, IndexError):
                    pass

        elapsed = time.monotonic() - start
        full_text = " ".join(text_parts)
        avg_confidence = (sum(confidences) / len(confidences)) / 100.0 if confidences else None

        logger.info(
            "OCR completed lang=%s chars=%d conf=%s time=%.2fs",
            self._lang,
            len(full_text),
            f"{avg_confidence:.2%}" if avg_confidence is not None else "N/A",
            elapsed,
        )

        return OcrResult(
            text=full_text,
            confidence=avg_confidence,
            language=self._lang,
            processing_time=elapsed,
            word_confidences=confidences,
        )
