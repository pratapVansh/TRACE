from app.ai.base import LLMProvider, LLMGenerationError
from app.core.logging import logger
from app.schemas.rag import Citation, RagQueryResponse
from app.schemas.retrieval import RetrievalFilter
from app.services.prompt_builder import PromptBuilder
from app.services.retriever_service import RetrieverService

INSUFFICIENT_CONTEXT_MESSAGE = (
    "I could not find this information in the uploaded documents."
)


class RagService:
    def __init__(
        self,
        retriever: RetrieverService,
        prompt_builder: PromptBuilder,
        llm: LLMProvider,
    ) -> None:
        self._retriever = retriever
        self._prompt_builder = prompt_builder
        self._llm = llm

    async def query(
        self,
        question: str,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
        filters: RetrievalFilter | None = None,
        history: list[dict] | None = None,
    ) -> RagQueryResponse:
        retrieval = await self._retriever.retrieve(
            query=question,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            filters=filters,
        )

        if not retrieval.results:
            logger.info(
                "No relevant chunks found for question — returning insufficient context response"
            )
            return RagQueryResponse(
                answer=INSUFFICIENT_CONTEXT_MESSAGE,
                citations=[],
                confidence=0.0,
            )

        prompt = self._prompt_builder.build_prompt(
            question, retrieval.results, history=history,
        )

        try:
            answer = await self._llm.generate(
                prompt=prompt.user_prompt,
                system_prompt=prompt.system_prompt,
                temperature=0.1,
                max_tokens=1024,
            )
        except LLMGenerationError as exc:
            logger.error("LLM generation failed during RAG query: %s", exc)
            raise

        citations = [
            Citation(
                document_name=chunk.document_name,
                page_number=chunk.page_number,
                chunk_content=chunk.content,
                score=chunk.score,
            )
            for chunk in retrieval.results
        ]

        confidence = retrieval.results[0].score

        logger.info(
            "RAG query answered with %d citations, confidence=%.3f",
            len(citations),
            confidence,
        )

        return RagQueryResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
        )
