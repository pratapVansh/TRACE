from __future__ import annotations

from app.core.storage import create_storage_service
from app.core.storage.base import StorageBackend
from app.processing.base import BaseProcessor
from app.processing.exceptions import ProcessorNotFoundError
from app.processing.processors import (
    DocxProcessor,
    ExcelProcessor,
    ImageProcessor,
    PdfProcessor,
    PptxProcessor,
)

_BUILTIN_PROCESSORS: list[BaseProcessor] = []


def _init_processors(storage: StorageBackend | None = None) -> list[BaseProcessor]:
    return [
        PdfProcessor(storage=storage),
        DocxProcessor(storage=storage),
        PptxProcessor(storage=storage),
        ExcelProcessor(storage=storage),
        ImageProcessor(storage=storage),
    ]


class ProcessingFactory:
    _processors: list[BaseProcessor] = []

    def __init__(self, storage: StorageBackend | None = None) -> None:
        if not self._processors:
            self._processors = _init_processors(storage)

    @classmethod
    def register_processor(cls, processor: BaseProcessor) -> None:
        cls._processors.append(processor)

    def get_processor(self, extension: str) -> BaseProcessor:
        for processor in self._processors:
            if processor.supports(extension):
                return processor
        raise ProcessorNotFoundError(
            f"No processor registered for extension '{extension}'",
        )

    def get_processor_for_mime(self, mime_type: str) -> BaseProcessor:
        for processor in self._processors:
            if processor.supports_mime(mime_type):
                return processor
        raise ProcessorNotFoundError(
            f"No processor registered for MIME type '{mime_type}'",
        )

    def supports_extension(self, extension: str) -> bool:
        return any(p.supports(extension) for p in self._processors)

    def supported_extensions(self) -> frozenset[str]:
        result: set[str] = set()
        for p in self._processors:
            result.update(p.supported_extensions)
        return frozenset(result)

    def clear(self) -> None:
        self._processors.clear()
