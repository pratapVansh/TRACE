from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.authorization import require_permission
from app.api.deps import _extract_ip, get_document_service
from app.core.authorization import PERMISSIONS
from app.processing.dependencies import get_processing_queue_service
from app.processing.models import ProcessingJob, ProcessingJobStatus
from app.processing.service import ProcessingQueueService
from app.schemas.auth import UserMeResponse
from app.schemas.processing import (
    ProcessingJobResponse,
    ProcessingJobStatusResponse,
    ProcessingRetryResponse,
)
from app.services.document_exceptions import DocumentNotFoundError
from app.services.document_mapper import get_latest_version
from app.services.document_service import DocumentService

router = APIRouter(prefix="/processing", tags=["processing"])


async def _job_to_response(job: ProcessingJob) -> ProcessingJobResponse:
    return ProcessingJobResponse(
        job_id=job.id,
        document_id=job.document_id,
        document_version_id=job.document_version_id,
        status=job.status,
        progress=job.progress,
        current_step=job.current_step,
        retries=job.retries,
        max_retries=job.max_retries,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        created_at=job.created_at,
    )


async def _job_to_status(job: ProcessingJob) -> ProcessingJobStatusResponse:
    return ProcessingJobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        current_step=job.current_step,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
    )


@router.get("/{job_id}", response_model=ProcessingJobResponse)
async def get_processing_job(
    job_id: UUID,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.DOCUMENTS_READ)),
    processing_service: ProcessingQueueService = Depends(get_processing_queue_service),
) -> ProcessingJobResponse:
    job = await processing_service.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing job not found",
        )
    return await _job_to_response(job)


@router.get("/{job_id}/status", response_model=ProcessingJobStatusResponse)
async def get_processing_job_status(
    job_id: UUID,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.DOCUMENTS_READ)),
    processing_service: ProcessingQueueService = Depends(get_processing_queue_service),
) -> ProcessingJobStatusResponse:
    job = await processing_service.get_status(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing job not found",
        )
    return await _job_to_status(job)


@router.post(
    "/{job_id}/retry",
    response_model=ProcessingRetryResponse,
    status_code=status.HTTP_200_OK,
)
async def retry_processing_job(
    job_id: UUID,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.DOCUMENTS_UPLOAD)),
    processing_service: ProcessingQueueService = Depends(get_processing_queue_service),
) -> ProcessingRetryResponse:
    job = await processing_service.retry(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing job not found",
        )
    return ProcessingRetryResponse(
        job_id=job.id,
        status=job.status,
        retries=job.retries,
        max_retries=job.max_retries,
        message=f"Retry scheduled (attempt {job.retries}/{job.max_retries})",
    )


@router.post(
    "/{job_id}/cancel",
    status_code=status.HTTP_200_OK,
)
async def cancel_processing_job(
    job_id: UUID,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.DOCUMENTS_UPLOAD)),
    processing_service: ProcessingQueueService = Depends(get_processing_queue_service),
) -> dict:
    job = await processing_service.cancel(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing job not found",
        )
    return {"job_id": str(job.id), "status": job.status, "message": "Job cancelled"}


@router.post(
    "/documents/{document_id}/process",
    status_code=status.HTTP_201_CREATED,
)
async def trigger_document_processing(
    request: Request,
    document_id: UUID,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.DOCUMENTS_UPLOAD)),
    document_service: DocumentService = Depends(get_document_service),
    processing_service: ProcessingQueueService = Depends(get_processing_queue_service),
) -> ProcessingJobResponse:
    document = await document_service._document_repository.get_document_by_id(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    latest_version = get_latest_version(document)
    job = await processing_service.enqueue(document_id, latest_version.id)
    return await _job_to_response(job)
