from __future__ import annotations

from io import BytesIO

import cv2
import numpy as np
from PIL import Image

TARGET_DPI = 300


class PreprocessingPipeline:
    def __init__(self, target_dpi: int = TARGET_DPI):
        self.target_dpi = target_dpi

    def process(self, image: Image.Image) -> Image.Image:
        img = self._ensure_grayscale(image)
        img = self._normalize_dpi(img)
        img = self._denoise(img)
        img = self._adaptive_threshold(img)
        img = self._auto_rotate(img)
        return img

    def _ensure_grayscale(self, image: Image.Image) -> Image.Image:
        if image.mode != "L":
            image = image.convert("L")
        return image

    def _normalize_dpi(self, image: Image.Image) -> Image.Image:
        dpi = image.info.get("dpi", (72.0, 72.0))
        current_dpi = dpi[0] if dpi and dpi[0] and dpi[0] > 0 else 72.0
        scale = self.target_dpi / current_dpi
        if abs(scale - 1.0) > 0.01:
            new_size = (int(image.width * scale), int(image.height * scale))
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
        arr = np.array(image)
        coords = cv2.findNonZero(arr)
        if coords is not None and len(coords) > 10:
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = 90 + angle
            if abs(angle) > 0.5:
                (h, w) = arr.shape[:2]
                center = (w // 2, h // 2)
                matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(
                    arr, matrix, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE,
                )
                return Image.fromarray(rotated)
        return image
