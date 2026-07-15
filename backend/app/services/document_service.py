from __future__ import annotations

import hashlib
import mimetypes
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.core.storage.base import StorageBackend
from app.core.storage.exceptions import StorageError
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.schemas.auth import UserMeResponse
from app.services.audit_service import AuditService
from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentFileContent,
    DocumentListResponse,
    DocumentResponse,
    UpdateDocumentRequest,
    UploadDocumentRequest,
)
from app.services.document_exceptions import (
    DocumentNotFoundError,
    DocumentProcessingActiveError,
    DocumentStorageError,
    DuplicateDocumentError,
    EmptyFileError,
    FileTooLargeError,
    InvalidDocumentStatusError,
    UnsupportedFileTypeError,
)
from app.services.document_classifier import classify_document
from app.schemas.pagination import build_pagination_metadata
from app.services.document_mapper import (
    get_latest_version,
    to_detail_response,
    to_list_item,
    to_upload_response,
    try_decode_text,
)
from app.services.processing_status import ProcessingStage, ProcessingStatus

from app.services.document_processing_queue import DocumentProcessingQueueService
from app.services.qdrant_indexing_service import QdrantIndexingService

DOCUMENT_STATUS_QUEUED = "queued"
ALLOWED_DOCUMENT_STATUSES = frozenset(
    {"queued", "indexed", "processing", "review", "archived", "failed"},
)
DEFAULT_DOC_TYPE = "unknown"
INITIAL_VERSION_NO = 1

EXTENSION_DOC_TYPES: dict[str, str] = {
    "pdf": "manual",
    "docx": "manual",
    "pptx": "manual",
    "xlsx": "spreadsheet",
    "txt": "document",
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
}

EXTENSION_MIME_TYPES: dict[str, frozenset[str]] = {
    "pdf": frozenset({"application/pdf"}),
    "docx": frozenset(
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ),
    "pptx": frozenset(
        {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    ),
    "xlsx": frozenset(
        {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ),
    "txt": frozenset({"text/plain"}),
    "png": frozenset({"image/png"}),
    "jpg": frozenset({"image/jpeg"}),
    "jpeg": frozenset({"image/jpeg"}),
}


class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        document_repository: DocumentRepository,
        storage: StorageBackend,
        audit_service: AuditService,
        processing_queue: DocumentProcessingQueueService | None = None,
        indexing_service: QdrantIndexingService | None = None,
    ) -> None:
        self._session = session
        self._document_repository = document_repository
        self._storage = storage
        self._audit_service = audit_service
        self._processing_queue = processing_queue
        self._indexing_service = indexing_service

    async def upload_document(
        self,
        actor: UserMeResponse,
        data: UploadDocumentRequest,
        ip_address: str | None = None,
    ) -> DocumentResponse:
        extension, mime_type = self._validate_upload(data.filename, data.content)

        checksum_sha256 = hashlib.sha256(data.content).hexdigest()
        existing_version = await self._document_repository.get_active_version_by_checksum(
            checksum_sha256,
        )
        if existing_version is not None:
            raise DuplicateDocumentError()

        title = data.title or Path(data.filename).stem or data.filename
        doc_type = data.doc_type or self._infer_doc_type(extension)
        extra_metadata = self._build_metadata(source=data.source)

        classification = classify_document(
            filename=data.filename,
            content_text=try_decode_text(data.content, extension),
        )

        document = await self._document_repository.create_document(
            title=title,
            original_filename=data.filename,
            doc_type=doc_type,
            status=DOCUMENT_STATUS_QUEUED,
            uploaded_by=actor.id,
            extra_metadata=extra_metadata,
            department=classification.department,
            document_category=classification.category,
            equipment_ids=classification.equipment_ids,
        )

        storage_uri = self._storage.build_document_path(
            document.id,
            INITIAL_VERSION_NO,
            data.filename,
        )

        try:
            stored_uri = self._storage.save(storage_uri, data.content)
        except StorageError as exc:
            await self._session.rollback()
            raise DocumentStorageError("Failed to store uploaded file") from exc

        try:
            document_version = await self._document_repository.create_document_version(
                document_id=document.id,
                version_no=INITIAL_VERSION_NO,
                storage_uri=stored_uri,
                checksum_sha256=checksum_sha256,
                mime_type=mime_type,
                file_extension=extension,
                file_size_bytes=len(data.content),
            )
            ingestion_job = await self._document_repository.create_ingestion_job(
                document_id=document.id,
                status=ProcessingStatus.PENDING.value,
                stage=ProcessingStage.UPLOAD.value,
                max_retries=settings.processing_queue_max_retries,
            )
            if self._processing_queue is not None:
                await self._processing_queue.enqueue(document.id, ingestion_job.id)
            response_job_id = ingestion_job.id
            response = to_upload_response(document, document_version, response_job_id)
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            self._storage.delete(stored_uri)
            raise

        await self._audit_service.log(
            user_id=actor.id,
            username=actor.full_name,
            action="document_uploaded",
            entity_type="document",
            entity_id=document.id,
            ip_address=ip_address,
        )
        await self._audit_service.flush()
        await self._session.commit()

        return response

    async def get_processing_status(self, document_id: UUID):
        if self._processing_queue is None:
            raise DocumentNotFoundError()
        return await self._processing_queue.get_processing_status(document_id)

    async def list_documents(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        doc_type: str | None = None,
        status: str | None = None,
        department: str | None = None,
        document_category: str | None = None,
        equipment_id: str | None = None,
    ) -> DocumentListResponse:
        documents = await self._document_repository.list_documents(
            skip=skip,
            limit=limit,
            search=search,
            doc_type=doc_type,
            status=status,
            department=department,
            document_category=document_category,
            equipment_id=equipment_id,
        )
        total = await self._document_repository.count_documents(
            search=search,
            doc_type=doc_type,
            status=status,
            department=department,
            document_category=document_category,
            equipment_id=equipment_id,
        )
        return DocumentListResponse(
            items=[to_list_item(document) for document in documents],
            **build_pagination_metadata(total=total, skip=skip, limit=limit),
        )

    async def update_document(
        self,
        document_id: UUID,
        data: UpdateDocumentRequest,
        actor: UserMeResponse | None = None,
        ip_address: str | None = None,
    ) -> DocumentDetailResponse:
        updates = data.model_dump(exclude_unset=True)
        document = await self._document_repository.get_document_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError()

        if "status" in updates and updates["status"] not in ALLOWED_DOCUMENT_STATUSES:
            raise InvalidDocumentStatusError()

        extra_metadata = None
        if "source" in updates or "department" in updates:
            extra_metadata = self._apply_metadata_updates(
                document.extra_metadata,
                updates,
            )

        updated = await self._document_repository.update_document(
            document_id,
            title=updates.get("title"),
            doc_type=updates.get("doc_type"),
            status=updates.get("status"),
            extra_metadata=extra_metadata,
            department=updates.get("department"),
            document_category=updates.get("document_category"),
            equipment_ids=updates.get("equipment_ids"),
        )
        if updated is None:
            raise DocumentNotFoundError()

        await self._session.commit()

        if updated.status == "indexed" and self._indexing_service is not None:
            qdrant_updates: dict = {}
            if "doc_type" in updates:
                qdrant_updates["document_type"] = updates["doc_type"]
            if "original_filename" in updates or "title" in updates:
                qdrant_updates["filename"] = updates.get("original_filename", updated.original_filename)
            if qdrant_updates:
                try:
                    await self._indexing_service._vector_store.update_document_payload(
                        document_id,
                        qdrant_updates,
                    )
                except Exception:
                    logger.warning(
                        "Failed to update Qdrant payload for document_id=%s",
                        document_id,
                    )

        if actor is not None:
            changed_fields = {k: v for k, v in updates.items() if v is not None}
            await self._audit_service.log(
                user_id=actor.id,
                username=actor.full_name,
                action="document_updated",
                entity_type="document",
                entity_id=document_id,
                ip_address=ip_address,
                error_message=str(changed_fields) if changed_fields else None,
            )
            await self._audit_service.flush()
            await self._session.commit()

        latest_version = get_latest_version(updated)
        return to_detail_response(updated, latest_version)

    async def get_document(self, document_id: UUID) -> DocumentDetailResponse:
        document = await self._document_repository.get_document_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError()

        latest_version = get_latest_version(document)

        await self._audit_service.log(
            user_id=None,
            username=None,
            action="document_viewed",
            entity_type="document",
            entity_id=document_id,
            ip_address=None,
        )
        await self._audit_service.flush()

        return to_detail_response(document, latest_version)

    async def get_document_content(self, document_id: UUID) -> DocumentFileContent:
        document = await self._document_repository.get_document_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError()

        latest_version = get_latest_version(document)

        try:
            content = self._storage.read(latest_version.storage_uri)
        except StorageError as exc:
            raise DocumentStorageError("Failed to read stored document") from exc

        await self._audit_service.log(
            user_id=None,
            username=None,
            action="document_downloaded",
            entity_type="document",
            entity_id=document_id,
            ip_address=None,
        )
        await self._audit_service.flush()

        return DocumentFileContent(
            document_id=document.id,
            filename=document.original_filename,
            mime_type=latest_version.mime_type,
            content=content,
        )

    async def delete_document(
        self,
        document_id: UUID,
        actor: UserMeResponse | None = None,
        ip_address: str | None = None,
    ) -> None:
        document = await self._document_repository.get_document_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError()

        latest_job = await self._document_repository.get_latest_ingestion_job_for_document(
            document_id,
        )
        if latest_job is not None and latest_job.status in {
            ProcessingStatus.PENDING.value,
            ProcessingStatus.PROCESSING.value,
        }:
            raise DocumentProcessingActiveError()

        storage_uris = [version.storage_uri for version in document.versions]

        try:
            for storage_uri in storage_uris:
                self._storage.delete(storage_uri)
        except StorageError as exc:
            raise DocumentStorageError("Failed to delete stored document files") from exc

        await self._document_repository.soft_delete_document(
            document_id=document_id,
            deleted_at=datetime.now(UTC),
        )
        await self._session.commit()

        if self._indexing_service is not None:
            try:
                await self._indexing_service.delete_document_vectors(document_id)
            except Exception:
                logger.warning(
                    "Failed to delete Qdrant vectors for document_id=%s",
                    document_id,
                )

        if actor is not None:
            await self._audit_service.log(
                user_id=actor.id,
                username=actor.full_name,
                action="document_deleted",
                entity_type="document",
                entity_id=document_id,
                ip_address=ip_address,
                error_message=document.original_filename,
            )
            await self._audit_service.flush()
            await self._session.commit()

    def _validate_upload(self, filename: str, content: bytes) -> tuple[str, str]:
        if not content:
            raise EmptyFileError()

        if len(content) > settings.max_upload_size_bytes:
            raise FileTooLargeError()

        extension = Path(filename).suffix.lower().lstrip(".")
        if not extension or extension not in settings.allowed_upload_extensions_set:
            raise UnsupportedFileTypeError()

        if not self._content_matches_extension(extension, content):
            raise UnsupportedFileTypeError()

        mime_type = self._resolve_mime_type(filename, extension)
        return extension, mime_type

    def _content_matches_extension(self, extension: str, content: bytes) -> bool:
        if extension == "pdf":
            return content.startswith(b"%PDF-")
        if extension in {"png"}:
            return content.startswith(b"\x89PNG\r\n\x1a\n")
        if extension in {"jpg", "jpeg"}:
            return content.startswith(b"\xff\xd8\xff")
        if extension in {"docx", "pptx", "xlsx"}:
            return content.startswith(b"PK\x03\x04")
        if extension == "txt":
            return True
        return False

    def _resolve_mime_type(self, filename: str, extension: str) -> str:
        guessed_type, _ = mimetypes.guess_type(filename)
        allowed_types = EXTENSION_MIME_TYPES.get(extension, frozenset())

        if guessed_type in allowed_types:
            return guessed_type

        if allowed_types:
            return next(iter(allowed_types))

        return guessed_type or "application/octet-stream"

    @staticmethod
    def _infer_doc_type(extension: str) -> str:
        return EXTENSION_DOC_TYPES.get(extension, DEFAULT_DOC_TYPE)

    @staticmethod
    def _build_metadata(*, source: str | None) -> dict:
        metadata: dict[str, str] = {}
        if source:
            metadata["source"] = source
        return metadata

    @staticmethod
    def _apply_metadata_updates(current: dict, updates: dict) -> dict:
        metadata = dict(current)
        if "source" in updates:
            if updates["source"]:
                metadata["source"] = updates["source"]
            else:
                metadata.pop("source", None)
        return metadata


