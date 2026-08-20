"""Tests for the OCR preprocessing pipeline and engine text assembly.

Neither had test coverage, which is how the deskew step shipped estimating
its angle from the page background instead of the text.
"""

import numpy as np
import pytest
from PIL import Image

from app.processing.ocr.engine import OcrEngine, OcrResult
from app.processing.ocr.preprocessing import (
    MAX_IMAGE_DIMENSION,
    MAX_UPSCALE_FACTOR,
    PreprocessingPipeline,
)


def _page_with_text_lines(angle: float = 0.0) -> Image.Image:
    """A white page with a few solid black bars standing in for text lines."""
    arr = np.full((400, 600), 255, dtype=np.uint8)
    for top in (80, 140, 200, 260):
        arr[top : top + 18, 60:540] = 0
    image = Image.fromarray(arr)
    if angle:
        image = image.rotate(angle, resample=Image.BICUBIC, fillcolor=255)
    return image


class TestSkewAngleNormalization:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (0.0, 0.0),
            (3.0, 3.0),
            (-3.0, -3.0),
            # OpenCV >= 4.5 reports a near-straight page as ~90, older
            # versions as ~0. Both must normalize to "no rotation needed".
            (90.0, 0.0),
            (89.0, -1.0),
            (-89.0, 1.0),
        ],
    )
    def test_angles_fold_into_deskew_range(self, raw: float, expected: float) -> None:
        assert PreprocessingPipeline._normalize_skew_angle(raw) == pytest.approx(
            expected, abs=1e-6
        )

    def test_result_always_within_range(self) -> None:
        for raw in range(-180, 181):
            angle = PreprocessingPipeline._normalize_skew_angle(float(raw))
            assert -45.0 < angle <= 45.0


class TestAutoRotate:
    def test_straight_page_is_left_alone(self) -> None:
        """A straight page must not be rotated — resampling only blurs it."""
        pipeline = PreprocessingPipeline()
        page = _page_with_text_lines()

        rotated = pipeline._auto_rotate(page)

        assert np.array_equal(np.array(rotated), np.array(page))

    def test_skewed_page_is_straightened(self) -> None:
        """The corrected estimate must reduce skew, not introduce it."""
        pipeline = PreprocessingPipeline()
        skewed = _page_with_text_lines(angle=6.0)

        corrected = np.array(pipeline._auto_rotate(skewed))

        assert self._row_variance(corrected) > self._row_variance(np.array(skewed))

    @staticmethod
    def _row_variance(arr: np.ndarray) -> float:
        """Variance of per-row ink. Straight text lines concentrate ink into
        a few rows, so a deskewed page scores higher than a slanted one."""
        return float(np.var((arr < 128).sum(axis=1)))


class TestPipelineEndToEnd:
    def test_process_returns_binarized_image(self) -> None:
        result = PreprocessingPipeline().process(_page_with_text_lines())

        assert result.mode == "L"
        assert set(np.unique(np.array(result))) <= {0, 255}


class TestTextAssembly:
    def test_words_are_grouped_back_into_lines(self) -> None:
        ocr_data = {
            "text": ["Tag:", "P-101", "Service:", "Feed", "Pump"],
            "conf": ["96", "95", "90", "88", "92"],
            "block_num": [1, 1, 1, 1, 1],
            "par_num": [1, 1, 1, 1, 1],
            "line_num": [1, 1, 2, 2, 2],
        }

        text, confidences = OcrEngine._assemble(ocr_data)

        assert text == "Tag: P-101\nService: Feed Pump"
        assert confidences == [96, 95, 90, 88, 92]

    def test_blank_words_and_unscored_rows_are_dropped(self) -> None:
        ocr_data = {
            "text": ["", "   ", "P-101"],
            # -1 is Tesseract's "no confidence assigned" marker.
            "conf": ["-1", "-1", "94"],
            "block_num": [1, 1, 1],
            "par_num": [1, 1, 1],
            "line_num": [1, 1, 1],
        }

        text, confidences = OcrEngine._assemble(ocr_data)

        assert text == "P-101"
        assert confidences == [94]

    def test_missing_position_fields_do_not_crash(self) -> None:
        """Some Tesseract configs omit the positional columns."""
        text, _ = OcrEngine._assemble({"text": ["A", "B"], "conf": ["90", "90"]})

        assert text == "A B"

    def test_separate_blocks_become_separate_lines(self) -> None:
        ocr_data = {
            "text": ["Header", "Body"],
            "conf": ["90", "90"],
            "block_num": [1, 2],
            "par_num": [1, 1],
            "line_num": [1, 1],
        }

        text, _ = OcrEngine._assemble(ocr_data)

        assert text == "Header\nBody"


class TestLanguageValidation:
    def test_unsupported_language_falls_back_to_english(self) -> None:
        engine = OcrEngine(lang="klingon")

        assert engine.lang == "eng"

    def test_multi_language_string_is_accepted(self) -> None:
        engine = OcrEngine(lang="eng+deu")

        assert engine.lang == "eng+deu"

    def test_partially_invalid_multi_language_falls_back(self) -> None:
        engine = OcrEngine(lang="eng+klingon")

        assert engine.lang == "eng"

    def test_constructor_validates_like_the_setter(self) -> None:
        """The constructor used to bypass validation entirely."""
        assert OcrEngine(lang="").lang == "eng"


class TestUnavailableTesseract:
    def test_returns_empty_result_without_calling_tesseract(self) -> None:
        engine = OcrEngine()
        engine._available = False

        result = engine.ocr_image(_page_with_text_lines())

        assert isinstance(result, OcrResult)
        assert result.text == ""

class TestNormalizeDpi:
    """Resampling bounds.

    A page rendered at 300 DPI used to be upscaled a further 3x, because
    PyMuPDF stamps 96 into every PNG it writes regardless of the resolution
    the page was actually rendered at. The oversized image defeated adaptive
    thresholding and Tesseract returned almost nothing.
    """

    def test_explicit_source_dpi_beats_misleading_metadata(self) -> None:
        pipeline = PreprocessingPipeline(target_dpi=300)
        image = Image.new("L", (2584, 1042))
        image.info["dpi"] = (96.0, 96.0)

        result = pipeline._normalize_dpi(image, source_dpi=300)

        assert result.size == (2584, 1042)

    def test_metadata_is_used_when_no_source_dpi_given(self) -> None:
        pipeline = PreprocessingPipeline(target_dpi=300)
        image = Image.new("L", (600, 400))
        image.info["dpi"] = (150.0, 150.0)

        result = pipeline._normalize_dpi(image)

        assert result.width == 1200

    def test_upscaling_is_capped(self) -> None:
        """A 72-DPI claim would otherwise demand a 4.2x enlargement."""
        pipeline = PreprocessingPipeline(target_dpi=300)
        image = Image.new("L", (800, 600))
        image.info["dpi"] = (72.0, 72.0)

        result = pipeline._normalize_dpi(image)

        assert result.width <= 800 * MAX_UPSCALE_FACTOR

    def test_longest_side_is_bounded(self) -> None:
        pipeline = PreprocessingPipeline(target_dpi=300)
        image = Image.new("L", (3800, 1000))
        image.info["dpi"] = (72.0, 72.0)

        result = pipeline._normalize_dpi(image)

        assert max(result.size) <= MAX_IMAGE_DIMENSION

    def test_downscaling_is_not_capped(self) -> None:
        """Shrinking an oversized scan is always safe."""
        pipeline = PreprocessingPipeline(target_dpi=300)
        image = Image.new("L", (2000, 1000))
        image.info["dpi"] = (1200.0, 1200.0)

        result = pipeline._normalize_dpi(image, source_dpi=1200)

        assert result.width == 500

    def test_missing_metadata_does_not_crash(self) -> None:
        pipeline = PreprocessingPipeline(target_dpi=300)

        result = pipeline._normalize_dpi(Image.new("L", (600, 400)))

        assert result.width > 0

    def test_matching_dpi_returns_image_untouched(self) -> None:
        pipeline = PreprocessingPipeline(target_dpi=300)
        image = Image.new("L", (600, 400))

        result = pipeline._normalize_dpi(image, source_dpi=300)

        assert result is image
