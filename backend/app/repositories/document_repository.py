import uuid
from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob


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
    ) -> int:
        query = select(func.count()).select_from(Document).where(
            *self._list_filters(
                search=search,
                doc_type=doc_type,
                status=status,
                department=department,
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
    ) -> Document:
        document = Document(
            title=title,
            original_filename=original_filename,
            doc_type=doc_type,
            status=status,
            uploaded_by=uploaded_by,
            extra_metadata=extra_metadata or {},
        )
        self._session.add(document)
        await self._session.flush()
        await self._session.refresh(document, attribute_names=["id", "created_at", "updated_at"])
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
        await self._session.refresh(document_version, attribute_names=["id", "created_at"])
        return document_version

    async def create_ingestion_job(
        self,
        *,
        document_id: uuid.UUID,
        status: str,
        stage: str,
    ) -> IngestionJob:
        ingestion_job = IngestionJob(
            document_id=document_id,
            status=status,
            stage=stage,
        )
        self._session.add(ingestion_job)
        await self._session.flush()
        await self._session.refresh(ingestion_job, attribute_names=["id", "created_at"])
        return ingestion_job

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
            filters.append(Document.extra_metadata["department"].as_string() == department)

        return filters
