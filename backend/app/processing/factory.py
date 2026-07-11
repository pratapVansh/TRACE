from app.processing.base import BaseProcessor
from app.processing.exceptions import ProcessorNotFoundError
from app.processing.processors import (
    DocxProcessor,
    ExcelProcessor,
    ImageProcessor,
    PdfProcessor,
    PptxProcessor,
)

_BUILTIN_PROCESSORS: list[BaseProcessor] = [
    PdfProcessor(),
    DocxProcessor(),
    PptxProcessor(),
    ExcelProcessor(),
    ImageProcessor(),
]


class ProcessingFactory:
    _processors: list[BaseProcessor] = list(_BUILTIN_PROCESSORS)

    @classmethod
    def register_processor(cls, processor: BaseProcessor) -> None:
        cls._processors.append(processor)

    @classmethod
    def get_processor(cls, extension: str) -> BaseProcessor:
        for processor in cls._processors:
            if processor.supports(extension):
                return processor
        raise ProcessorNotFoundError(
            f"No processor registered for extension '{extension}'",
        )

    @classmethod
    def get_processor_for_mime(cls, mime_type: str) -> BaseProcessor:
        for processor in cls._processors:
            if processor.supports_mime(mime_type):
                return processor
        raise ProcessorNotFoundError(
            f"No processor registered for MIME type '{mime_type}'",
        )

    @classmethod
    def supports_extension(cls, extension: str) -> bool:
        return any(p.supports(extension) for p in cls._processors)

    @classmethod
    def supported_extensions(cls) -> frozenset[str]:
        result: set[str] = set()
        for p in cls._processors:
            result.update(p.supported_extensions)
        return frozenset(result)

    @classmethod
    def clear(cls) -> None:
        cls._processors.clear()
