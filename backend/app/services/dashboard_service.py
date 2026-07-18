from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.graph.base import GraphStore
from app.processing.repository import ProcessingJobRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.dashboard import DashboardResponse, RecentUploadItem


class DashboardService:
    def __init__(
        self,
        session: AsyncSession,
        graph_store: GraphStore | None = None,
    ) -> None:
        self._session = session
        self._graph_store = graph_store
        self._doc_repo = DocumentRepository(session)
        self._conv_repo = ConversationRepository(session)
        self._job_repo = ProcessingJobRepository(session)

    async def get_dashboard(self) -> DashboardResponse:
        document_count = await self._doc_repo.count_documents()

        entity_count: int | None = None
        relationship_count: int | None = None
        neo4j_connected = False
        if self._graph_store is not None:
            try:
                result = await self._graph_store.execute_read(
                    "MATCH (n:Entity) RETURN count(n) AS cnt",
                )
                entity_count = result[0]["cnt"] if result else 0

                result = await self._graph_store.execute_read(
                    "MATCH ()-[r]->() RETURN count(r) AS cnt",
                )
                relationship_count = result[0]["cnt"] if result else 0
                neo4j_connected = True
            except Exception as exc:
                logger.warning("Dashboard graph query failed: %s", exc)

        conversation_count = await self._conv_repo.count_conversations()
        pending_jobs = await self._job_repo.count_pending_jobs()

        raw_docs = await self._doc_repo.list_documents(skip=0, limit=5)
        recent_uploads = [
            RecentUploadItem(
                id=str(d.id),
                title=d.title or d.original_filename,
                filename=d.original_filename,
                status=d.status,
                uploaded_at=(
                    d.created_at.isoformat() if isinstance(d.created_at, datetime)
                    else str(d.created_at)
                ),
            )
            for d in raw_docs
        ]

        return DashboardResponse(
            document_count=document_count,
            entity_count=entity_count,
            relationship_count=relationship_count,
            conversation_count=conversation_count,
            pending_jobs=pending_jobs,
            recent_uploads=recent_uploads,
            neo4j_connected=neo4j_connected,
        )
