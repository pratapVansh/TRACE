import hashlib
import mimetypes
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.storage.base import StorageBackend
from app.core.storage.exceptions import StorageError
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.repositories.document_repository import DocumentRepository
from app.schemas.auth import UserMeResponse
from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentFileContent,
    DocumentListItemResponse,
    DocumentListResponse,
    DocumentResponse,
    UpdateDocumentRequest,
    UploadDocumentRequest,
)
from app.services.document_exceptions import (
    DocumentNotFoundError,
    DocumentStorageError,
    DuplicateDocumentError,
    EmptyFileError,
    FileTooLargeError,
    InvalidDocumentStatusError,
    UnsupportedFileTypeError,
)

DOCUMENT_STATUS_QUEUED = "queued"
ALLOWED_DOCUMENT_STATUSES = frozenset(
    {"queued", "indexed", "processing", "review", "archived", "failed"},
)
INGESTION_JOB_STATUS_QUEUED = "queued"
INGESTION_JOB_STAGE_UPLOAD = "upload"
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
    ) -> None:
        self._session = session
        self._document_repository = document_repository
        self._storage = storage

    async def upload_document(
        self,
        actor: UserMeResponse,
        data: UploadDocumentRequest,
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

        document = await self._document_repository.create_document(
            title=title,
            original_filename=data.filename,
            doc_type=doc_type,
            status=DOCUMENT_STATUS_QUEUED,
            uploaded_by=actor.id,
            extra_metadata=extra_metadata,
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
                status=INGESTION_JOB_STATUS_QUEUED,
                stage=INGESTION_JOB_STAGE_UPLOAD,
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            self._storage.delete(stored_uri)
            raise

        return self._to_upload_response(document, document_version, ingestion_job.id)

    async def list_documents(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        doc_type: str | None = None,
        status: str | None = None,
        department: str | None = None,
    ) -> DocumentListResponse:
        documents = await self._document_repository.list_documents(
            skip=skip,
            limit=limit,
            search=search,
            doc_type=doc_type,
            status=status,
            department=department,
        )
        total = await self._document_repository.count_documents(
            search=search,
            doc_type=doc_type,
            status=status,
            department=department,
        )
        return DocumentListResponse(
            items=[self._to_list_item(document) for document in documents],
            total=total,
        )

    async def update_document(
        self,
        document_id: UUID,
        data: UpdateDocumentRequest,
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
        )
        if updated is None:
            raise DocumentNotFoundError()

        await self._session.commit()
        latest_version = self._get_latest_version(updated)
        return self._to_detail_response(updated, latest_version)

    async def get_document(self, document_id: UUID) -> DocumentDetailResponse:
        document = await self._document_repository.get_document_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError()

        latest_version = self._get_latest_version(document)
        return self._to_detail_response(document, latest_version)

    async def get_document_content(self, document_id: UUID) -> DocumentFileContent:
        document = await self._document_repository.get_document_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError()

        latest_version = self._get_latest_version(document)

        try:
            content = self._storage.read(latest_version.storage_uri)
        except StorageError as exc:
            raise DocumentStorageError("Failed to read stored document") from exc

        return DocumentFileContent(
            document_id=document.id,
            filename=document.original_filename,
            mime_type=latest_version.mime_type,
            content=content,
        )

    async def delete_document(self, document_id: UUID) -> None:
        document = await self._document_repository.get_document_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError()

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
        if "department" in updates:
            if updates["department"]:
                metadata["department"] = updates["department"]
            else:
                metadata.pop("department", None)
        return metadata

    @staticmethod
    def _get_latest_version(document: Document) -> DocumentVersion:
        for version in document.versions:
            if version.is_latest:
                return version

        if not document.versions:
            raise DocumentNotFoundError()

        return max(document.versions, key=lambda version: version.version_no)

    def _to_upload_response(
        self,
        document: Document,
        document_version: DocumentVersion,
        job_id: UUID,
    ) -> DocumentResponse:
        return DocumentResponse(
            id=document.id,
            title=document.title,
            original_filename=document.original_filename,
            doc_type=document.doc_type,
            status=document.status,
            mime_type=document_version.mime_type,
            file_extension=document_version.file_extension,
            file_size_bytes=document_version.file_size_bytes,
            uploaded_by=document.uploaded_by,
            job_id=job_id,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    def _to_list_item(self, document: Document) -> DocumentListItemResponse:
        latest_version = self._get_latest_version(document)
        uploaded_by_name = (
            document.uploaded_by_user.full_name if document.uploaded_by_user else None
        )

        return DocumentListItemResponse(
            id=document.id,
            title=document.title,
            original_filename=document.original_filename,
            doc_type=document.doc_type,
            status=document.status,
            mime_type=latest_version.mime_type,
            file_extension=latest_version.file_extension,
            file_size_bytes=latest_version.file_size_bytes,
            version_no=latest_version.version_no,
            uploaded_by=document.uploaded_by,
            uploaded_by_name=uploaded_by_name,
            metadata=document.extra_metadata,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    def _to_detail_response(
        self,
        document: Document,
        latest_version: DocumentVersion,
    ) -> DocumentDetailResponse:
        uploaded_by_name = (
            document.uploaded_by_user.full_name if document.uploaded_by_user else None
        )

        return DocumentDetailResponse(
            id=document.id,
            title=document.title,
            original_filename=document.original_filename,
            doc_type=document.doc_type,
            status=document.status,
            mime_type=latest_version.mime_type,
            file_extension=latest_version.file_extension,
            file_size_bytes=latest_version.file_size_bytes,
            version_no=latest_version.version_no,
            uploaded_by=document.uploaded_by,
            uploaded_by_name=uploaded_by_name,
            metadata=document.extra_metadata,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
