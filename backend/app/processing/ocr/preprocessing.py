from __future__ import annotations

from io import BytesIO

import cv2
import numpy as np
from PIL import Image

TARGET_DPI = 300

# Minimum glyph pixels before a skew estimate is trustworthy.
MIN_DESKEW_PIXELS = 10
# Rotations smaller than this are not worth the resampling blur.
MIN_DESKEW_ANGLE = 0.5
# Beyond this the estimate is almost certainly a bad fit, not a real skew.
MAX_DESKEW_ANGLE = 20.0
# Upscaling past this yields no OCR gain and costs time on every page.
MAX_UPSCALE_FACTOR = 2.0
# Ceiling on the longest side after resampling. The later filters use
# fixed kernel sizes, so an oversized image changes what they do to the
# glyphs rather than just costing memory.
MAX_IMAGE_DIMENSION = 4000


class PreprocessingPipeline:
    def __init__(self, target_dpi: int = TARGET_DPI):
        self.target_dpi = target_dpi

    def process(
        self, image: Image.Image, source_dpi: float | None = None
    ) -> Image.Image:
        """Prepare *image* for OCR.

        Pass ``source_dpi`` when the true resolution is known — a PDF page
        rendered at a chosen DPI, for instance. Embedded PNG metadata is not
        a reliable substitute; see ``_normalize_dpi``.
        """
        img = self._ensure_grayscale(image)
        img = self._normalize_dpi(img, source_dpi)
        img = self._denoise(img)
        img = self._adaptive_threshold(img)
        img = self._auto_rotate(img)
        return img

    def _ensure_grayscale(self, image: Image.Image) -> Image.Image:
        if image.mode != "L":
            image = image.convert("L")
        return image

    def _normalize_dpi(
        self, image: Image.Image, source_dpi: float | None = None
    ) -> Image.Image:
        """Resample *image* towards ``target_dpi``.

        Embedded DPI metadata routinely lies. PyMuPDF stamps 96 into every
        PNG it writes no matter what resolution the page was rendered at, so
        trusting it upscaled an already-300-DPI page by a further 3x — the
        result was large enough that adaptive thresholding smeared the
        glyphs and Tesseract returned almost nothing. An explicit
        ``source_dpi`` from the caller wins, and the scale factor is capped
        so a bad guess degrades the image slightly instead of destroying it.
        """
        if source_dpi and source_dpi > 0:
            current_dpi = float(source_dpi)
        else:
            dpi = image.info.get("dpi")
            current_dpi = dpi[0] if dpi and dpi[0] and dpi[0] > 0 else 72.0

        scale = self.target_dpi / current_dpi

        # Never enlarge past the point where OCR stops benefiting, and never
        # exceed a size that would make the later filters behave differently.
        scale = min(scale, MAX_UPSCALE_FACTOR)
        longest = max(image.width, image.height)
        if longest * scale > MAX_IMAGE_DIMENSION:
            scale = MAX_IMAGE_DIMENSION / longest

        if abs(scale - 1.0) <= 0.01:
            return image

        new_size = (max(int(image.width * scale), 1), max(int(image.height * scale), 1))
        image = image.resize(new_size, Image.LANCZOS)
        image.info["dpi"] = (self.target_dpi, self.target_dpi)
        return image

    def _denoise(self, image: Image.Image) -> Image.Image:
        arr = np.array(image)
        denoised = cv2.fastNlMeansDenoising(arr, None, 10, 7, 21)
        return Image.fromarray(denoised)

    def _adaptive_threshold(self, image: Image.Image) -> Image.Image:
        arr = np.array(image)
        thresholded = cv2.adaptiveThreshold(
            arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2,
        )
        return Image.fromarray(thresholded)

    def _auto_rotate(self, image: Image.Image) -> Image.Image:
        """Deskew the page by estimating the dominant text angle.

        ``_adaptive_threshold`` leaves text black (0) on a white (255)
        background, so ``findNonZero`` on the thresholded image selects the
        *background* — the resulting ``minAreaRect`` describes the page
        border, not the text, and the angle it yields is noise. The image is
        inverted first so the non-zero pixels are the glyphs themselves.
        """
        arr = np.array(image)
        # Glyphs become the non-zero (white) pixels.
        text_mask = cv2.bitwise_not(arr) if arr.mean() > 127 else arr

        coords = cv2.findNonZero(text_mask)
        if coords is None or len(coords) <= MIN_DESKEW_PIXELS:
            return image

        angle = self._normalize_skew_angle(cv2.minAreaRect(coords)[-1])
        if abs(angle) < MIN_DESKEW_ANGLE or abs(angle) > MAX_DESKEW_ANGLE:
            # Below the threshold rotation costs quality for no gain; above it
            # the estimate is far more likely to be a bad fit than a genuinely
            # sideways page, and rotating on it would wreck a good scan.
            return image

        h, w = arr.shape[:2]
        matrix = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        rotated = cv2.warpAffine(
            arr,
            matrix,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255,
        )
        return Image.fromarray(rotated)

    @staticmethod
    def _normalize_skew_angle(angle: float) -> float:
        """Map a ``minAreaRect`` angle onto the (-45, 45] deskew range.

        OpenCV changed this convention: <4.5 reports (-90, 0], >=4.5 reports
        (0, 90]. Folding both into (-45, 45] keeps the deskew correct on
        either version instead of rotating a straight page by 90 degrees.
        """
        angle = angle % 90.0
        if angle > 45.0:
            angle -= 90.0
        return angle
