"""Unit tests for GraphProcessor."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.extraction.relationship import Relationship, RelationshipType
from app.extraction.types import EntityType
from app.graph.graph_builder import GraphBuildResult
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.services.document_processing_exceptions import GraphExtractionError
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext
from app.services.processors.graph_processor import GraphProcessor


@pytest.fixture
def document_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def chunk_id_1() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def chunk_id_2() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_document(document_id: uuid.UUID) -> Document:
    doc = Document(
        id=document_id,
        title="Test Manual",
        original_filename="manual.pdf",
        doc_type="manual",
        status="processing",
        extra_metadata={},
    )
    doc.created_at = datetime.now(UTC)
    doc.updated_at = datetime.now(UTC)
    return doc


@pytest.fixture
def sample_version(document_id: uuid.UUID) -> DocumentVersion:
    version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=document_id,
        version_no=1,
        storage_uri="manual.pdf",
        checksum_sha256="abc123",
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=100,
        is_latest=True,
    )
    version.created_at = datetime.now(UTC)
    return version


@pytest.fixture
def sample_job(document_id: uuid.UUID) -> IngestionJob:
    job = IngestionJob(
        id=uuid.uuid4(),
        document_id=document_id,
        status="processing",
        stage="chunking",
    )
    job.created_at = datetime.now(UTC)
    return job


@pytest.fixture
def context(
    sample_document: Document,
    sample_version: DocumentVersion,
    sample_job: IngestionJob,
) -> ProcessingContext:
    return ProcessingContext(
        document=sample_document,
        version=sample_version,
        job=sample_job,
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_document_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_chunk_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_graph_store() -> AsyncMock:
    store = AsyncMock()
    store.execute_write.return_value = []
    mock_tx = AsyncMock()
    mock_tx.run.return_value = AsyncMock()
    mock_tx.closed = False
    store.begin_transaction = AsyncMock(return_value=mock_tx)
    return store


def make_chunk(
    chunk_id: uuid.UUID,
    document_id: uuid.UUID,
    content: str,
    chunk_index: int = 0,
) -> DocumentChunk:
    chunk = DocumentChunk(
        id=chunk_id,
        document_id=document_id,
        chunk_index=chunk_index,
        content=content,
        extra_metadata={},
        token_count=len(content.split()),
        embedding=None,
        embedding_status="pending",
    )
    chunk.created_at = datetime.now(UTC)
    chunk.updated_at = datetime.now(UTC)
    return chunk


class TestGraphProcessor:
    @pytest.mark.asyncio
    async def test_processor_name(self) -> None:
        processor = GraphProcessor(
            session=AsyncMock(),
            document_repository=AsyncMock(),
            document_chunk_repository=AsyncMock(),
            graph_store=AsyncMock(),
        )
        assert processor.name == "graph_extraction"

    @pytest.mark.asyncio
    async def test_process_skips_when_no_graph_store(
        self,
        mock_session: AsyncMock,
        mock_document_repo: AsyncMock,
        mock_chunk_repo: AsyncMock,
        context: ProcessingContext,
    ) -> None:
        processor = GraphProcessor(
            session=mock_session,
            document_repository=mock_document_repo,
            document_chunk_repository=mock_chunk_repo,
            graph_store=None,
        )

        await processor.process(context)

        mock_document_repo.update_ingestion_job.assert_awaited_with(
            context.job.id,
            stage=ProcessingStage.GRAPH_EXTRACTION.value,
        )
        mock_chunk_repo.get_chunks_by_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_skips_when_no_chunks(
        self,
        mock_session: AsyncMock,
        mock_document_repo: AsyncMock,
        mock_chunk_repo: AsyncMock,
        mock_graph_store: AsyncMock,
        context: ProcessingContext,
    ) -> None:
        mock_chunk_repo.get_chunks_by_document.return_value = []

        processor = GraphProcessor(
            session=mock_session,
            document_repository=mock_document_repo,
            document_chunk_repository=mock_chunk_repo,
            graph_store=mock_graph_store,
        )

        await processor.process(context)

        mock_chunk_repo.get_chunks_by_document.assert_awaited_with(
            context.document.id,
        )
        mock_graph_store.execute_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_extracts_and_persists(
        self,
        mock_session: AsyncMock,
        mock_document_repo: AsyncMock,
        mock_chunk_repo: AsyncMock,
        mock_graph_store: AsyncMock,
        context: ProcessingContext,
        document_id: uuid.UUID,
        chunk_id_1: uuid.UUID,
    ) -> None:
        chunk = make_chunk(
            chunk_id=chunk_id_1,
            document_id=document_id,
            # "is connected to ... via piping" reads like a relationship but
            # matches no pattern, so this content exercises the entity branch
            # only. See test_process_persists_relationships for the other half.
            content="Pump P-101 is connected to Tank TK-305 via piping.",
            chunk_index=0,
        )
        mock_chunk_repo.get_chunks_by_document.return_value = [chunk]

        processor = GraphProcessor(
            session=mock_session,
            document_repository=mock_document_repo,
            document_chunk_repository=mock_chunk_repo,
            graph_store=mock_graph_store,
        )

        await processor.process(context)

        mock_document_repo.update_ingestion_job.assert_awaited_with(
            context.job.id,
            stage=ProcessingStage.GRAPH_EXTRACTION.value,
        )
        mock_chunk_repo.get_chunks_by_document.assert_awaited_with(document_id)

        mock_tx = mock_graph_store.begin_transaction.return_value
        assert mock_graph_store.begin_transaction.await_count == 1
        assert mock_tx.run.call_count >= 1
        mock_tx.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_propagates_extraction_error(
        self,
        mock_session: AsyncMock,
        mock_document_repo: AsyncMock,
        mock_chunk_repo: AsyncMock,
        mock_graph_store: AsyncMock,
        context: ProcessingContext,
        document_id: uuid.UUID,
        chunk_id_1: uuid.UUID,
    ) -> None:
        chunk = make_chunk(
            chunk_id=chunk_id_1,
            document_id=document_id,
            content="Some content.",
            chunk_index=0,
        )
        mock_chunk_repo.get_chunks_by_document.return_value = [chunk]
        mock_tx = mock_graph_store.begin_transaction.return_value
        mock_tx.run.side_effect = RuntimeError("Neo4j write failed")

        processor = GraphProcessor(
            session=mock_session,
            document_repository=mock_document_repo,
            document_chunk_repository=mock_chunk_repo,
            graph_store=mock_graph_store,
        )

        with pytest.raises(GraphExtractionError, match="Neo4j write failed"):
            await processor.process(context)

    @pytest.mark.asyncio
    async def test_process_multiple_chunks(
        self,
        mock_session: AsyncMock,
        mock_document_repo: AsyncMock,
        mock_chunk_repo: AsyncMock,
        mock_graph_store: AsyncMock,
        context: ProcessingContext,
        document_id: uuid.UUID,
        chunk_id_1: uuid.UUID,
        chunk_id_2: uuid.UUID,
    ) -> None:
        chunks = [
            make_chunk(
                chunk_id=chunk_id_1,
                document_id=document_id,
                content="Pump P-101 is connected to Tank TK-305.",
                chunk_index=0,
            ),
            make_chunk(
                chunk_id=chunk_id_2,
                document_id=document_id,
                content="Valve V-202 maintains pressure for Pump P-101.",
                chunk_index=1,
            ),
        ]
        mock_chunk_repo.get_chunks_by_document.return_value = chunks

        processor = GraphProcessor(
            session=mock_session,
            document_repository=mock_document_repo,
            document_chunk_repository=mock_chunk_repo,
            graph_store=mock_graph_store,
        )

        await processor.process(context)

        mock_chunk_repo.get_chunks_by_document.assert_awaited_once_with(document_id)
        mock_tx = mock_graph_store.begin_transaction.return_value
        assert mock_graph_store.begin_transaction.await_count == 1
        assert mock_tx.run.call_count >= 1

    @pytest.mark.asyncio
    async def test_process_handles_graph_builder_failure(
        self,
        mock_session: AsyncMock,
        mock_document_repo: AsyncMock,
        mock_chunk_repo: AsyncMock,
        mock_graph_store: AsyncMock,
        context: ProcessingContext,
        document_id: uuid.UUID,
        chunk_id_1: uuid.UUID,
    ) -> None:
        chunk = make_chunk(
            chunk_id=chunk_id_1,
            document_id=document_id,
            content="Pump P-101 is part of System SYS-001.",
            chunk_index=0,
        )
        mock_chunk_repo.get_chunks_by_document.return_value = [chunk]

        processor = GraphProcessor(
            session=mock_session,
            document_repository=mock_document_repo,
            document_chunk_repository=mock_chunk_repo,
            graph_store=mock_graph_store,
        )

        await processor.process(context)
        mock_graph_store.begin_transaction.assert_awaited_once()


class TestGraphProcessorRelationships:
    """The relationship branch of GraphProcessor.process.

    Regression cover for a NameError: the branch constructed ``Relationship``
    without importing it, so any chunk yielding at least one relationship
    raised ``GraphExtractionError``. Because GraphProcessor runs ahead of the
    embedding and indexing processors, that failed the whole ingestion job and
    the document never reached Qdrant.

    The bug survived because every existing fixture sentence extracted zero
    relationships, leaving the branch unexecuted. These tests use content that
    provably yields one.
    """

    @pytest.mark.asyncio
    async def test_process_persists_relationships(
        self,
        mock_session: AsyncMock,
        mock_document_repo: AsyncMock,
        mock_chunk_repo: AsyncMock,
        mock_graph_store: AsyncMock,
        context: ProcessingContext,
        document_id: uuid.UUID,
        chunk_id_1: uuid.UUID,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A chunk yielding a relationship reaches the builder, typed on both ends."""
        captured: dict[str, list] = {}

        class RecordingBuilder:
            def __init__(self, graph_store: object) -> None:
                self._graph_store = graph_store

            async def process_document(
                self,
                document_id: str,
                entities: list,
                relationships: list,
                source_document: str = "",
            ) -> GraphBuildResult:
                captured["entities"] = entities
                captured["relationships"] = relationships
                return GraphBuildResult(
                    nodes_merged=len(entities),
                    relationships_merged=len(relationships),
                    successful=True,
                )

        monkeypatch.setattr(
            "app.services.processors.graph_processor.GraphBuilderService",
            RecordingBuilder,
        )

        chunk = make_chunk(
            chunk_id=chunk_id_1,
            document_id=document_id,
            content="P-101 connects to TK-305.",
            chunk_index=0,
        )
        mock_chunk_repo.get_chunks_by_document.return_value = [chunk]

        processor = GraphProcessor(
            session=mock_session,
            document_repository=mock_document_repo,
            document_chunk_repository=mock_chunk_repo,
            graph_store=mock_graph_store,
        )

        await processor.process(context)

        relationships = captured["relationships"]
        assert relationships, (
            "content with a matching relationship pattern produced none - the "
            "branch this test exists to cover did not run"
        )

        rel = next(
            r for r in relationships
            if r.source == "P-101" and r.target == "TK-305"
        )
        assert isinstance(rel, Relationship)
        assert rel.type is RelationshipType.CONNECTED_TO
        # The branch rebuilds each relationship purely to attach the entity
        # types, so an untyped end means the rebuild silently did nothing.
        assert rel.source_type is EntityType.PUMP
        assert rel.target_type is EntityType.TANK
        assert rel.document_id == str(document_id)
        assert rel.chunk_id == str(chunk_id_1)

    @pytest.mark.asyncio
    async def test_process_does_not_raise_on_relationship_content(
        self,
        mock_session: AsyncMock,
        mock_document_repo: AsyncMock,
        mock_chunk_repo: AsyncMock,
        mock_graph_store: AsyncMock,
        context: ProcessingContext,
        document_id: uuid.UUID,
        chunk_id_1: uuid.UUID,
    ) -> None:
        """The failure as ingestion saw it: GraphExtractionError, job marked FAILED."""
        chunk = make_chunk(
            chunk_id=chunk_id_1,
            document_id=document_id,
            content="P-101 feeds TK-305.",
            chunk_index=0,
        )
        mock_chunk_repo.get_chunks_by_document.return_value = [chunk]

        processor = GraphProcessor(
            session=mock_session,
            document_repository=mock_document_repo,
            document_chunk_repository=mock_chunk_repo,
            graph_store=mock_graph_store,
        )

        await processor.process(context)

        mock_tx = mock_graph_store.begin_transaction.return_value
        mock_tx.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_relationship_branch_types_both_ends_across_chunks(
        self,
        mock_session: AsyncMock,
        mock_document_repo: AsyncMock,
        mock_chunk_repo: AsyncMock,
        mock_graph_store: AsyncMock,
        context: ProcessingContext,
        document_id: uuid.UUID,
        chunk_id_1: uuid.UUID,
        chunk_id_2: uuid.UUID,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Entity types are merged across all chunks before relationships are typed.

        The type map is built from the merged entity set, so a relationship in
        one chunk can be typed from an entity introduced by another.
        """
        captured: dict[str, list] = {}

        class RecordingBuilder:
            def __init__(self, graph_store: object) -> None:
                self._graph_store = graph_store

            async def process_document(
                self,
                document_id: str,
                entities: list,
                relationships: list,
                source_document: str = "",
            ) -> GraphBuildResult:
                captured["relationships"] = relationships
                return GraphBuildResult(successful=True)

        monkeypatch.setattr(
            "app.services.processors.graph_processor.GraphBuilderService",
            RecordingBuilder,
        )

        mock_chunk_repo.get_chunks_by_document.return_value = [
            make_chunk(
                chunk_id=chunk_id_1,
                document_id=document_id,
                content="Tank TK-305 stores intermediate product.",
                chunk_index=0,
            ),
            make_chunk(
                chunk_id=chunk_id_2,
                document_id=document_id,
                content="P-101 feeds TK-305.",
                chunk_index=1,
            ),
        ]

        processor = GraphProcessor(
            session=mock_session,
            document_repository=mock_document_repo,
            document_chunk_repository=mock_chunk_repo,
            graph_store=mock_graph_store,
        )

        await processor.process(context)

        relationships = captured["relationships"]
        assert relationships
        rel = next(
            r for r in relationships
            if r.source == "P-101" and r.target == "TK-305"
        )
        assert rel.type is RelationshipType.INPUT_TO
        assert rel.source_type is EntityType.PUMP
        assert rel.target_type is EntityType.TANK
