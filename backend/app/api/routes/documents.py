from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response

from app.api.authorization import require_permission
from app.api.deps import _extract_ip, get_document_service
from app.core.authorization import PERMISSIONS
from app.core.config import settings
from app.middleware.rate_limit import RateLimiter

upload_rate_limiter = RateLimiter(
    max_requests=settings.upload_rate_limit_max,
    window_seconds=settings.upload_rate_limit_window_seconds,
)
from app.schemas.auth import UserMeResponse
from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentProcessingStatusResponse,
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
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


def _escape_quoted_filename(filename: str) -> str:
    return filename.replace("\\", "\\\\").replace('"', '\\"')


def _build_content_disposition_header(disposition: str, filename: str) -> str:
    """
    Build a Content-Disposition value that Starlette can encode as Latin-1.

    HTTP response headers must be Latin-1. Non-Latin-1 characters in the legacy
    filename= parameter cause UnicodeEncodeError at response time. RFC 5987
    filename*=UTF-8'' carries the full Unicode name for modern clients.
    """
    name = (filename or "").strip() or "download"
    escaped = _escape_quoted_filename(name)

    try:
        name.encode("latin-1")
    except UnicodeEncodeError:
        ascii_fallback = name.encode("ascii", "ignore").decode("ascii").strip() or "download"
        ascii_fallback = _escape_quoted_filename(ascii_fallback)
        encoded = quote(name, safe="")
        return f'{disposition}; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}'

    return f'{disposition}; filename="{escaped}"'


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    doc_type: str | None = Form(default=None),
    source: str | None = Form(default=None),
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.DOCUMENTS_UPLOAD)),
    document_service: DocumentService = Depends(get_document_service),
    _rate_limit: None = Depends(upload_rate_limiter),
) -> DocumentResponse:
    filename = file.filename or ""
    content = await file.read()

    try:
        payload = UploadDocumentRequest(
            filename=filename,
            content=content,
            title=title,
            doc_type=doc_type,
            source=source,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    try:
        return await document_service.upload_document(
            current_user, payload, ip_address=_extract_ip(request),
        )
    except EmptyFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        ) from exc
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type",
        ) from exc
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the maximum upload size",
        ) from exc
    except DuplicateDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A document with the same content already exists",
        ) from exc
    except DocumentStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store uploaded file",
        ) from exc


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    search: str | None = Query(default=None),
    doc_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    department: str | None = Query(default=None),
    document_category: str | None = Query(default=None),
    equipment_id: str | None = Query(default=None),
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.DOCUMENTS_READ)),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    return await document_service.list_documents(
        skip=skip,
        limit=limit,
        search=search,
        doc_type=doc_type,
        status=status_filter,
        department=department,
        document_category=document_category,
        equipment_id=equipment_id,
    )


@router.patch("/{document_id}", response_model=DocumentDetailResponse)
async def update_document(
    request: Request,
    document_id: UUID,
    payload: UpdateDocumentRequest,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.DOCUMENTS_UPLOAD)),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentDetailResponse:
    try:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="At least one field must be provided",
            )
        return await document_service.update_document(
            document_id, payload, actor=current_user, ip_address=_extract_ip(request),
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        ) from exc
    except InvalidDocumentStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document status",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get("/{document_id}/processing-status", response_model=DocumentProcessingStatusResponse)
async def get_document_processing_status(
    document_id: UUID,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.DOCUMENTS_READ)),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentProcessingStatusResponse:
    try:
        return await document_service.get_processing_status(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        ) from exc


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: UUID,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.DOCUMENTS_READ)),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentDetailResponse:
    try:
        return await document_service.get_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        ) from exc


@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    download: bool = Query(default=False),
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.DOCUMENTS_READ)),
    document_service: DocumentService = Depends(get_document_service),
) -> Response:
    try:
        file_content = await document_service.get_document_content(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        ) from exc
    except DocumentStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read stored document",
        ) from exc

    disposition = "attachment" if download else "inline"
    return Response(
        content=file_content.content,
        media_type=file_content.mime_type,
        headers={
            "Content-Disposition": _build_content_disposition_header(
                disposition,
                file_content.filename,
            ),
        },
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    request: Request,
    document_id: UUID,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.DOCUMENTS_UPLOAD)),
    document_service: DocumentService = Depends(get_document_service),
) -> None:
    try:
        await document_service.delete_document(
            document_id, actor=current_user, ip_address=_extract_ip(request),
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        ) from exc
    except DocumentProcessingActiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is currently being processed and cannot be deleted",
        ) from exc
    except DocumentStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete stored document files",
        ) from exc
