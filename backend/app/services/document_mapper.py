from uuid import UUID

from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentListItemResponse,
    DocumentResponse,
)
from app.services.document_exceptions import DocumentNotFoundError


def get_latest_version(document: Document) -> DocumentVersion:
    for version in document.versions:
        if version.is_latest:
            return version

    if not document.versions:
        raise DocumentNotFoundError()

    return max(document.versions, key=lambda version: version.version_no)


def try_decode_text(content: bytes, extension: str) -> str | None:
    if extension == "txt":
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return content.decode("latin-1")
            except UnicodeDecodeError:
                return None
    return None


def _document_base(document: Document) -> dict:
    return {
        "id": document.id,
        "title": document.title,
        "original_filename": document.original_filename,
        "doc_type": document.doc_type,
        "status": document.status,
        "uploaded_by": document.uploaded_by,
        "department": document.department,
        "document_category": document.document_category,
        "equipment_ids": document.equipment_ids,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def _version_fields(version: DocumentVersion) -> dict:
    return {
        "mime_type": version.mime_type,
        "file_extension": version.file_extension,
        "file_size_bytes": version.file_size_bytes,
    }


def to_upload_response(
    document: Document,
    document_version: DocumentVersion,
    job_id: UUID,
) -> DocumentResponse:
    return DocumentResponse(
        **_document_base(document),
        **_version_fields(document_version),
        job_id=job_id,
    )


def to_list_item(document: Document) -> DocumentListItemResponse:
    latest = get_latest_version(document)
    uploaded_by_name = (
        document.uploaded_by_user.full_name if document.uploaded_by_user else None
    )
    return DocumentListItemResponse(
        **_document_base(document),
        **_version_fields(latest),
        version_no=latest.version_no,
        uploaded_by_name=uploaded_by_name,
        metadata=document.extra_metadata,
    )


def to_detail_response(
    document: Document,
    latest_version: DocumentVersion,
) -> DocumentDetailResponse:
    uploaded_by_name = (
        document.uploaded_by_user.full_name if document.uploaded_by_user else None
    )
    return DocumentDetailResponse(
        **_document_base(document),
        **_version_fields(latest_version),
        version_no=latest_version.version_no,
        uploaded_by_name=uploaded_by_name,
        metadata=document.extra_metadata,
    )
