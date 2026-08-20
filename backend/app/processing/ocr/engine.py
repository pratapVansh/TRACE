from __future__ import annotations

import time
from dataclasses import dataclass, field

import pytesseract
from PIL import Image

from app.core.config import settings
from app.core.logging import logger
from app.processing.ocr.preprocessing import PreprocessingPipeline

# Tesseract is a separate native binary. On Windows it installs outside PATH,
# so honour an explicit path from configuration before the first call.
if settings.tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


@dataclass
class OcrResult:
    text: str
    confidence: float | None = None
    language: str = "eng"
    processing_time: float = 0.0
    word_confidences: list[float] = field(default_factory=list)


class OcrEngine:
    SUPPORTED_LANGUAGES = frozenset({"eng", "fra", "deu", "spa", "ita", "por", "nld", "ara", "chi_sim", "jpn", "kor"})

    def __init__(self, lang: str | None = None, preprocessing: PreprocessingPipeline | None = None):
        self._lang = "eng"
        # Route through the setter so a bad value from configuration is
        # rejected here rather than surfacing as a Tesseract error per page.
        self.lang = lang if lang is not None else settings.ocr_language
        self._preprocessing = preprocessing or PreprocessingPipeline()
        self._available: bool | None = None

    @property
    def lang(self) -> str:
        return self._lang

    @lang.setter
    def lang(self, value: str) -> None:
        # "eng+deu" asks Tesseract to consider both; each part needs its own
        # traineddata, so every part is validated independently.
        parts = [p for p in str(value).split("+") if p]
        unsupported = [p for p in parts if p not in self.SUPPORTED_LANGUAGES]
        if not parts or unsupported:
            logger.warning(
                "Unsupported OCR language(s) %s, falling back to 'eng'",
                ", ".join(unsupported) or repr(value),
            )
            self._lang = "eng"
            return
        self._lang = "+".join(parts)

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            pytesseract.get_tesseract_version()
            self._available = True
        except Exception:
            self._available = False
            logger.warning(
                "Tesseract OCR is not available — install the binary and set "
                "TESSERACT_CMD if it is not on PATH. Scanned documents will "
                "yield no text until then."
            )
        return self._available

    def ocr_image(
        self, image: Image.Image, source_dpi: float | None = None
    ) -> OcrResult:
        if not self.is_available():
            logger.warning("Tesseract not available; returning empty OCR result")
            return OcrResult(text="", language=self._lang)

        start = time.monotonic()
        processed = self._preprocessing.process(image, source_dpi=source_dpi)
        ocr_data = pytesseract.image_to_data(
            processed,
            lang=self._lang,
            output_type=pytesseract.Output.DICT,
            config="--psm 3 --oem 3",
        )

        full_text, confidences = self._assemble(ocr_data)
        elapsed = time.monotonic() - start
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

    @staticmethod
    def _assemble(ocr_data: dict) -> tuple[str, list[float]]:
        """Rebuild page text from Tesseract's per-word rows.

        Words are grouped back into their original lines using the
        block/paragraph/line numbers Tesseract reports. Joining every word
        with a single space instead — as this did previously — collapses the
        whole page onto one line, which destroys the row structure of tables
        and spec sheets and leaves the chunker with no boundaries to split on.
        """
        words = ocr_data.get("text") or []
        confs = ocr_data.get("conf") or []

        lines: dict[tuple[int, int, int], list[str]] = {}
        order: list[tuple[int, int, int]] = []
        confidences: list[float] = []

        for i, raw in enumerate(words):
            word = (raw or "").strip()
            if not word:
                continue

            key = (
                _row(ocr_data, "block_num", i),
                _row(ocr_data, "par_num", i),
                _row(ocr_data, "line_num", i),
            )
            if key not in lines:
                lines[key] = []
                order.append(key)
            lines[key].append(word)

            try:
                conf = float(confs[i])
            except (ValueError, TypeError, IndexError):
                continue
            # Tesseract reports -1 for rows it assigns no confidence to.
            if conf >= 0:
                confidences.append(conf)

        rendered = [" ".join(lines[key]) for key in order]
        return "\n".join(rendered), confidences


def _row(ocr_data: dict, field_name: str, index: int) -> int:
    """Read one positional field, tolerating engines that omit it."""
    try:
        return int(ocr_data[field_name][index])
    except (KeyError, IndexError, ValueError, TypeError):
        return 0
