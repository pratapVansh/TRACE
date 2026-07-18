from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.extraction.entity_extractor import EntityExtractor
from app.extraction.normalizer import merge_entities
from app.extraction.relationship_extractor import RelationshipExtractor
from app.graph.base import GraphStore
from app.graph.graph_builder import GraphBuilderService
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.document_processing_exceptions import GraphExtractionError
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext


class GraphProcessor:
    """Extract entities and relationships from chunks and persist to Neo4j."""

    name = "graph_extraction"

    def __init__(
        self,
        session: AsyncSession,
        document_repository: DocumentRepository,
        document_chunk_repository: DocumentChunkRepository,
        graph_store: GraphStore | None = None,
    ) -> None:
        self._session = session
        self._document_repository = document_repository
        self._chunk_repository = document_chunk_repository
        self._entity_extractor = EntityExtractor()
        self._relationship_extractor = RelationshipExtractor()
        self._graph_store = graph_store

    async def process(self, context: ProcessingContext) -> None:
        await self._document_repository.update_ingestion_job(
            context.job.id,
            stage=ProcessingStage.GRAPH_EXTRACTION.value,
        )
        await self._session.flush()

        if self._graph_store is None:
            logger.info(
                "Graph store not available; skipping graph extraction document_id=%s",
                context.document.id,
            )
            return

        logger.info(
            "Graph extraction started document_id=%s version_id=%s",
            context.document.id,
            context.version.id,
        )

        try:
            chunks = await self._chunk_repository.get_chunks_by_document(
                context.document.id,
            )
            if not chunks:
                logger.info(
                    "No chunks to process for graph extraction document_id=%s",
                    context.document.id,
                )
                return

            all_entities = []
            all_relationships = []
            doc_title = context.document.title or ""
            doc_type = context.document.doc_type or ""
            doc_id_str = str(context.document.id)

            for chunk in chunks:
                entities = self._entity_extractor.extract_from_chunk(
                    content=chunk.content,
                    chunk_id=str(chunk.id),
                    document_id=doc_id_str,
                    metadata=chunk.extra_metadata,
                    document_title=doc_title,
                    document_type=doc_type,
                )
                all_entities.extend(entities)

            all_entities = merge_entities(all_entities)

            entity_names = [e.name for e in all_entities]
            entity_type_map = {e.name: e.type for e in all_entities}

            for chunk in chunks:
                relationships = self._relationship_extractor.extract_from_entities(
                    content=chunk.content,
                    chunk_id=str(chunk.id),
                    document_id=doc_id_str,
                    entities=entity_names,
                    metadata=chunk.extra_metadata,
                )
                for rel in relationships:
                    rel = Relationship(
                        source=rel.source,
                        target=rel.target,
                        type=rel.type,
                        confidence=rel.confidence,
                        chunk_id=rel.chunk_id,
                        document_id=rel.document_id,
                        metadata=rel.metadata,
                        source_type=entity_type_map.get(rel.source),
                        target_type=entity_type_map.get(rel.target),
                    )
                    all_relationships.append(rel)

            builder = GraphBuilderService(graph_store=self._graph_store)
            result = await builder.process_document(
                document_id=doc_id_str,
                entities=all_entities,
                relationships=all_relationships,
                source_document=context.document.original_filename or doc_title,
            )

            if not result.successful:
                raise GraphExtractionError(
                    f"Graph persistence failed: {result.error}",
                )

            logger.info(
                "Graph extraction completed document_id=%s entities=%d relationships=%d",
                context.document.id,
                result.nodes_merged,
                result.relationships_merged,
            )
        except GraphExtractionError:
            raise
        except Exception as exc:
            raise GraphExtractionError(f"Graph extraction failed: {exc}") from exc
