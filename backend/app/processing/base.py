from abc import ABC, abstractmethod
from uuid import UUID

from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.processing.models import ProcessingResult


class BaseProcessor(ABC):
    name: str
    supported_extensions: frozenset[str] = frozenset()
    supported_mime_types: frozenset[str] = frozenset()

    def supports(self, extension: str) -> bool:
        return extension.lower() in self.supported_extensions

    def supports_mime(self, mime_type: str) -> bool:
        return mime_type.lower() in self.supported_mime_types

    @abstractmethod
    async def extract_text(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> str:
        ...

    @abstractmethod
    async def extract_metadata(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> dict:
        ...

    async def validate(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> list[str]:
        return []

    async def process(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> ProcessingResult:
        warnings = await self.validate(document, version)
        metadata = await self.extract_metadata(document, version)
        text = await self.extract_text(document, version)
        return ProcessingResult(
            success=not warnings,
            document_id=document.id,
            extracted_text=text,
            metadata=metadata,
            warnings=warnings,
        )
