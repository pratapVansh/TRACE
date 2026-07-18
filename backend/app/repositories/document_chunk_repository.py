import uuid
from collections.abc import Sequence

from sqlalchemy import case, delete, func, select, update as sa_update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_chunk import DocumentChunk


class DocumentChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_chunk(
        self,
        *,
        document_id: uuid.UUID,
        chunk_index: int,
        content: str,
        page_number: int | None = None,
        section_title: str | None = None,
        extra_metadata: dict | None = None,
        token_count: int = 0,
        embedding_status: str = "pending",
    ) -> DocumentChunk:
        chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=chunk_index,
            content=content,
            page_number=page_number,
            section_title=section_title,
            extra_metadata=extra_metadata or {},
            token_count=token_count,
            embedding_status=embedding_status,
        )
        self._session.add(chunk)
        await self._session.flush()
        await self._session.refresh(chunk)
        return chunk

    async def create_chunks_bulk(
        self,
        chunks: list[dict],
    ) -> list[DocumentChunk]:
        objects = [DocumentChunk(**data) for data in chunks]
        self._session.add_all(objects)
        await self._session.flush()
        return objects

    async def get_chunks_by_document(
        self,
        document_id: uuid.UUID,
        *,
        embedding_status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[DocumentChunk]:
        query = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .offset(skip)
            .limit(limit)
        )
        if embedding_status is not None:
            query = query.where(DocumentChunk.embedding_status == embedding_status)
        result = await self._session.execute(query)
        return result.scalars().all()

    async def count_chunks_by_document(
        self,
        document_id: uuid.UUID,
        *,
        embedding_status: str | None = None,
    ) -> int:
        query = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
        if embedding_status is not None:
            query = query.where(DocumentChunk.embedding_status == embedding_status)
        result = await self._session.execute(query)
        return result.scalar_one()

    async def delete_document_chunks(
        self,
        document_id: uuid.UUID,
    ) -> None:
        await self._session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id),
        )
        await self._session.flush()

    async def get_chunk_by_id(
        self,
        chunk_id: uuid.UUID,
    ) -> DocumentChunk | None:
        result = await self._session.execute(
            select(DocumentChunk).where(DocumentChunk.id == chunk_id),
        )
        return result.scalar_one_or_none()

    async def get_pending_embedding_chunks(
        self,
        document_id: uuid.UUID,
    ) -> Sequence[DocumentChunk]:
        result = await self._session.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.embedding_status == "pending",
            )
            .order_by(DocumentChunk.chunk_index),
        )
        return result.scalars().all()

    async def update_chunks_embedding_bulk(
        self,
        updates: list[dict],
    ) -> None:
        if not updates:
            return

        chunk_ids = [u["id"] for u in updates]
        embedding_case = case(
            *[
                (
                    DocumentChunk.id == u["id"],
                    func.cast(u.get("embedding"), JSONB),
                )
                for u in updates
            ],
            else_=DocumentChunk.embedding,
        )
        status_case = case(
            *[
                (DocumentChunk.id == u["id"], u.get("embedding_status", "completed"))
                for u in updates
            ],
            else_=DocumentChunk.embedding_status,
        )

        await self._session.execute(
            sa_update(DocumentChunk)
            .where(DocumentChunk.id.in_(chunk_ids))
            .values(
                embedding=embedding_case,
                embedding_status=status_case,
            ),
        )
        await self._session.flush()
