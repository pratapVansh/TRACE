import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document
from app.models.document_extracted_text import DocumentExtractedText
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.services.processing_status import ProcessingStage, ProcessingStatus


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_document_by_id(self, document_id: uuid.UUID) -> Document | None:
        result = await self._session.execute(
            select(Document)
            .options(
                selectinload(Document.uploaded_by_user),
                selectinload(Document.versions),
            )
            .where(
                Document.id == document_id,
                Document.deleted_at.is_(None),
            ),
        )
        return result.scalar_one_or_none()

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
    ) -> list[Document]:
        query = (
            select(Document)
            .options(
                selectinload(Document.uploaded_by_user),
                selectinload(Document.versions),
            )
            .where(
                *self._list_filters(
                    search=search,
                    doc_type=doc_type,
                    status=status,
                    department=department,
                    document_category=document_category,
                    equipment_id=equipment_id,
                ),
            )
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count_documents(
        self,
        *,
        search: str | None = None,
        doc_type: str | None = None,
        status: str | None = None,
        department: str | None = None,
        document_category: str | None = None,
        equipment_id: str | None = None,
    ) -> int:
        query = select(func.count()).select_from(Document).where(
            *self._list_filters(
                search=search,
                doc_type=doc_type,
                status=status,
                department=department,
                document_category=document_category,
                equipment_id=equipment_id,
            ),
        )
        result = await self._session.execute(query)
        return result.scalar_one()

    async def get_active_version_by_checksum(
        self,
        checksum_sha256: str,
    ) -> DocumentVersion | None:
        result = await self._session.execute(
            select(DocumentVersion)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                DocumentVersion.checksum_sha256 == checksum_sha256,
                Document.deleted_at.is_(None),
            ),
        )
        return result.scalar_one_or_none()

    async def create_document(
        self,
        *,
        title: str,
        original_filename: str,
        doc_type: str,
        status: str,
        uploaded_by: uuid.UUID | None,
        extra_metadata: dict | None = None,
        department: str | None = None,
        document_category: str | None = None,
        equipment_ids: list[str] | None = None,
    ) -> Document:
        document = Document(
            title=title,
            original_filename=original_filename,
            doc_type=doc_type,
            status=status,
            uploaded_by=uploaded_by,
            extra_metadata=extra_metadata or {},
            department=department,
            document_category=document_category,
            equipment_ids=equipment_ids,
        )
        self._session.add(document)
        await self._session.flush()
        await self._session.refresh(document)
        return document

    async def create_document_version(
        self,
        *,
        document_id: uuid.UUID,
        version_no: int,
        storage_uri: str,
        checksum_sha256: str,
        mime_type: str,
        file_extension: str,
        file_size_bytes: int,
        page_count: int | None = None,
        is_latest: bool = True,
    ) -> DocumentVersion:
        document_version = DocumentVersion(
            document_id=document_id,
            version_no=version_no,
            storage_uri=storage_uri,
            checksum_sha256=checksum_sha256,
            mime_type=mime_type,
            file_extension=file_extension,
            file_size_bytes=file_size_bytes,
            page_count=page_count,
            is_latest=is_latest,
        )
        self._session.add(document_version)
        await self._session.flush()
        await self._session.refresh(document_version)
        return document_version

    async def get_document_version_by_id(
        self,
        version_id: uuid.UUID,
    ) -> DocumentVersion | None:
        result = await self._session.execute(
            select(DocumentVersion).where(DocumentVersion.id == version_id),
        )
        return result.scalar_one_or_none()

    async def update_document_version(
        self,
        version_id: uuid.UUID,
        *,
        page_count: int | None = None,
    ) -> DocumentVersion | None:
        version = await self.get_document_version_by_id(version_id)
        if version is None:
            return None

        if page_count is not None:
            version.page_count = page_count

        await self._session.flush()
        await self._session.refresh(version)
        return version

    async def upsert_extracted_text(
        self,
        *,
        document_version_id: uuid.UUID,
        full_text: str,
        pages: list[dict],
        extraction_method: str,
        requires_ocr: bool,
    ) -> DocumentExtractedText:
        result = await self._session.execute(
            select(DocumentExtractedText).where(
                DocumentExtractedText.document_version_id == document_version_id,
            ),
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            extracted = DocumentExtractedText(
                document_version_id=document_version_id,
                full_text=full_text,
                pages=pages,
                extraction_method=extraction_method,
                requires_ocr=requires_ocr,
            )
            self._session.add(extracted)
            await self._session.flush()
            await self._session.refresh(extracted)
            return extracted

        existing.full_text = full_text
        existing.pages = pages
        existing.extraction_method = extraction_method
        existing.requires_ocr = requires_ocr
        await self._session.flush()
        await self._session.refresh(existing)
        return existing

    async def get_extracted_text_by_version_id(
        self,
        document_version_id: uuid.UUID,
    ) -> DocumentExtractedText | None:
        result = await self._session.execute(
            select(DocumentExtractedText).where(
                DocumentExtractedText.document_version_id == document_version_id,
            ),
        )
        return result.scalar_one_or_none()

    async def create_ingestion_job(
        self,
        *,
        document_id: uuid.UUID,
        status: str,
        stage: str,
        max_retries: int | None = None,
    ) -> IngestionJob:
        ingestion_job = IngestionJob(
            document_id=document_id,
            status=status,
            stage=stage,
            max_retries=max_retries if max_retries is not None else 3,
        )
        self._session.add(ingestion_job)
        await self._session.flush()
        await self._session.refresh(ingestion_job)
        return ingestion_job

    async def get_ingestion_job_by_id(self, job_id: uuid.UUID) -> IngestionJob | None:
        result = await self._session.execute(
            select(IngestionJob).where(IngestionJob.id == job_id),
        )
        return result.scalar_one_or_none()

    async def get_latest_ingestion_job_for_document(
        self,
        document_id: uuid.UUID,
    ) -> IngestionJob | None:
        result = await self._session.execute(
            select(IngestionJob)
            .where(IngestionJob.document_id == document_id)
            .order_by(IngestionJob.created_at.desc())
            .limit(1),
        )
        return result.scalar_one_or_none()

    async def list_pending_ingestion_jobs(
        self,
        *,
        limit: int = 100,
    ) -> list[IngestionJob]:
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(IngestionJob)
            .where(
                IngestionJob.status == ProcessingStatus.PENDING.value,
                or_(
                    IngestionJob.next_retry_at.is_(None),
                    IngestionJob.next_retry_at <= now,
                ),
            )
            .order_by(IngestionJob.created_at.asc())
            .limit(limit),
        )
        return list(result.scalars().all())

    async def update_ingestion_job(
        self,
        job_id: uuid.UUID,
        *,
        status: str | None = None,
        stage: str | None = None,
        error: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> IngestionJob | None:
        job = await self.get_ingestion_job_by_id(job_id)
        if job is None:
            return None

        if status is not None:
            job.status = status
        if stage is not None:
            job.stage = stage
        if error is not None:
            job.error = error
        if started_at is not None:
            job.started_at = started_at
        if finished_at is not None:
            job.finished_at = finished_at

        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def schedule_ingestion_job_retry(
        self,
        job_id: uuid.UUID,
        *,
        retry_count: int,
        next_retry_at: datetime,
        error: str,
    ) -> IngestionJob | None:
        job = await self.get_ingestion_job_by_id(job_id)
        if job is None:
            return None

        job.status = ProcessingStatus.PENDING.value
        job.stage = ProcessingStage.QUEUED.value
        job.retry_count = retry_count
        job.next_retry_at = next_retry_at
        job.error = error
        job.started_at = None
        job.finished_at = None

        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def soft_delete_document(
        self,
        document_id: uuid.UUID,
        deleted_at: datetime,
    ) -> None:
        await self._session.execute(
            update(Document)
            .where(
                Document.id == document_id,
                Document.deleted_at.is_(None),
            )
            .values(deleted_at=deleted_at),
        )
        await self._session.flush()

    async def update_document(
        self,
        document_id: uuid.UUID,
        *,
        title: str | None = None,
        doc_type: str | None = None,
        status: str | None = None,
        extra_metadata: dict | None = None,
        department: str | None = None,
        document_category: str | None = None,
        equipment_ids: list[str] | None = None,
    ) -> Document | None:
        document = await self.get_document_by_id(document_id)
        if document is None:
            return None

        if title is not None:
            document.title = title
        if doc_type is not None:
            document.doc_type = doc_type
        if status is not None:
            document.status = status
        if extra_metadata is not None:
            document.extra_metadata = extra_metadata
        if department is not None:
            document.department = department
        if document_category is not None:
            document.document_category = document_category
        if equipment_ids is not None:
            document.equipment_ids = equipment_ids

        await self._session.flush()
        await self._session.refresh(document)
        return document

    def _list_filters(
        self,
        *,
        search: str | None,
        doc_type: str | None,
        status: str | None,
        department: str | None,
        document_category: str | None = None,
        equipment_id: str | None = None,
    ) -> list:
        filters = [Document.deleted_at.is_(None)]

        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(
                    Document.title.ilike(term),
                    Document.original_filename.ilike(term),
                ),
            )

        if doc_type:
            filters.append(Document.doc_type == doc_type)

        if status:
            filters.append(Document.status == status)

        if department:
            filters.append(Document.department == department)

        if document_category:
            filters.append(Document.document_category == document_category)

        if equipment_id:
            filters.append(Document.equipment_ids.any(equipment_id))

        return filters
