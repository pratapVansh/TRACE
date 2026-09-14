"""Build TRACE's real retrieval / answer pipeline for one evaluation config.

Mirrors ``app.main`` construction and ``GraphRagService.query`` parameters,
but never touches ChatService: nothing is written to conversations, long-term
memory, the user graph or any datastore.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.core.config import settings

# GraphRagService.query defaults - the path ChatService uses for Copilot.
VECTOR_TOP_K = 10
GRAPH_TOP_K = 5


@dataclass(frozen=True)
class EvalConfig:
    name: str
    rerank: bool = True
    graph: bool = True
    collection: str | None = None
    rerank_timeout_seconds: float | None = None
    prefer_domain_entities: bool = False
    description: str = ""


CONFIGS: dict[str, EvalConfig] = {
    "baseline": EvalConfig("baseline", description="Current pipeline: hybrid search + reranker + graph, chunk 256"),
    "rerank_off": EvalConfig("rerank_off", rerank=False, description="Reranker disabled (RRF order)"),
    "graph_off": EvalConfig("graph_off", graph=False, description="Graph retriever disabled (vector only)"),
    "chunk512": EvalConfig(
        "chunk512",
        collection="eval_chunks_512",
        # At 512 tokens a 40-candidate scoring batch exceeds the production
        # 10 s timeout on CPU, which silently disables reranking for the whole
        # process. Raised here so the ablation measures reranked 512 chunks;
        # the latency cost is reported instead of hidden.
        rerank_timeout_seconds=60.0,
        description="Same pipeline on a separate Qdrant collection chunked at 512/64 (reranker timeout 60 s)",
    ),
    "graph_v2": EvalConfig(
        "graph_v2",
        prefer_domain_entities=True,
        description="Baseline plus the reworked graph arm: entities ranked by term "
                    "density rather than raw count, documents ranked below domain "
                    "entities, and only relationship facts counted in the merge boost",
    ),
}


def apply_config(config: EvalConfig) -> None:
    """Point the process-wide settings at *config*. One config per process."""
    from app.core.cache import cache_manager

    settings.rerank_enabled = config.rerank
    if config.collection:
        settings.qdrant_collection_name = config.collection
    if config.rerank_timeout_seconds is not None:
        settings.rerank_timeout_seconds = config.rerank_timeout_seconds
    settings.graph_prefer_domain_entities = config.prefer_domain_entities
    # QdrantVectorStore.search caches on the query vector without the
    # collection name, so a stale entry would leak across collections.
    cache_manager._local_cache.cache.clear()


def settings_snapshot(config: EvalConfig) -> dict:
    return {
        **asdict(config),
        "qdrant_collection": settings.qdrant_collection_name,
        "rerank_enabled": settings.rerank_enabled,
        "rerank_model": settings.rerank_model_name,
        "embedding_model": settings.embedding_model_name,
        "retrieval_top_k": settings.retrieval_top_k,
        "vector_top_k": VECTOR_TOP_K,
        "graph_top_k": GRAPH_TOP_K,
        "dedup_documents": settings.retrieval_dedup_documents,
        "graph_prefer_domain_entities": settings.graph_prefer_domain_entities,
        "llm_model": settings.groq_model,
    }


class Pipeline:
    def __init__(self, config: EvalConfig) -> None:
        self.config = config
        self.vector_store = None
        self.graph_store = None
        self.hybrid = None
        self.graph_enabled = False

    async def start(self) -> None:
        from app.graph.graph_query import GraphQueryService
        from app.graph.neo4j_graph_store import Neo4jGraphStore
        from app.services import reranker_service
        from app.services.embedding_service import _encode_batch_async
        from app.services.hybrid_retriever import (
            ContextMerger,
            GraphRetriever,
            HybridRetriever,
            VectorRetriever,
        )
        from app.services.vector_store import QdrantVectorStore

        apply_config(self.config)
        self.vector_store = QdrantVectorStore()
        await self.vector_store.connect()

        graph_retriever = None
        if self.config.graph:
            self.graph_store = Neo4jGraphStore()
            await self.graph_store.connect()
            graph_retriever = GraphRetriever(graph_query_service=GraphQueryService(graph_store=self.graph_store))
            self.graph_enabled = True

        self.hybrid = HybridRetriever(
            vector_retriever=VectorRetriever(vector_store=self.vector_store),
            graph_retriever=graph_retriever,
            context_merger=ContextMerger(),
        )

        # Warm every lazy component before anything is timed: the reranker (a
        # cold load once silently disabled reranking for the whole probe), the
        # embedding model, and the Qdrant / Neo4j connections.
        if self.config.rerank:
            if not await reranker_service.warmup():
                raise RuntimeError("reranker failed to warm up - refusing to measure a degraded pipeline")
        await _encode_batch_async(["warm up"])
        await self.hybrid.retrieve("pump bearing temperature", top_k=settings.retrieval_top_k,
                                   vector_top_k=VECTOR_TOP_K, graph_top_k=GRAPH_TOP_K)

    async def retrieve(self, search_query: str):
        unified = await self.hybrid.retrieve(
            query=search_query,
            top_k=settings.retrieval_top_k,
            vector_top_k=VECTOR_TOP_K,
            graph_top_k=GRAPH_TOP_K,
        )
        self.assert_not_degraded()
        return unified

    def assert_not_degraded(self) -> None:
        """Abort rather than record results from a silently degraded pipeline."""
        from app.services import reranker_service

        if self.config.rerank and reranker_service._DISABLED:
            raise RuntimeError(
                f"reranker disabled itself mid-run ({reranker_service._DISABLED_REASON}); "
                "results would be unreranked - aborting"
            )

    async def rag_service(self, cache_dir: Path, cache_only: bool = False):
        from app.ai.groq_provider import GroqProvider
        from app.services.prompt_builder import PromptBuilder
        from app.services.rag_service import GraphRagService
        from app.services.retriever_service import RetrieverService

        provider = None
        if not cache_only:
            provider = GroqProvider()
            await provider.initialize()
        self.llm = CachingLLM(provider, cache_dir, cache_only=cache_only)
        return GraphRagService(
            hybrid_retriever=self.hybrid,
            retriever=RetrieverService(self.vector_store),
            prompt_builder=PromptBuilder(),
            llm=self.llm,
        )

    async def close(self) -> None:
        if self.graph_store is not None:
            await self.graph_store.close()


class CacheMiss(Exception):
    """Raised in cache-only mode when a request has never been answered."""


class CachingLLM:
    """Wraps the LLM provider; identical requests are answered from disk.

    The key covers the model and the complete request (system prompt, user
    prompt with its retrieved context, history, sampling parameters), so a
    retrieval change produces a new prompt and therefore a fresh call.
    """

    RATE_LIMIT_BACKOFF_SECONDS = (20, 45, 90)

    def __init__(self, inner, cache_dir: Path, cache_only: bool = False) -> None:
        self._inner = inner
        self._cache_only = cache_only
        self._dir = cache_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0
        self.last: dict = {}

    async def generate(self, prompt: str, system_prompt: str | None = None,
                       history: list[dict] | None = None, **kwargs) -> str:
        import asyncio
        import time

        from app.ai.base import LLMGenerationError

        request = {
            "model": settings.groq_model,
            "system_prompt": system_prompt,
            "prompt": prompt,
            "history": history,
            "kwargs": kwargs,
        }
        key = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        path = self._dir / f"{key}.json"
        if path.exists():
            self.hits += 1
            self.last = {"cached": True, "llm_ms": None, "cache_key": key}
            return json.loads(path.read_text(encoding="utf-8"))["response"]
        if self._cache_only:
            raise CacheMiss(key)

        for attempt in range(len(self.RATE_LIMIT_BACKOFF_SECONDS) + 1):
            started = time.perf_counter()
            try:
                response = await self._inner.generate(prompt, system_prompt=system_prompt,
                                                      history=history, **dict(kwargs))
                break
            except LLMGenerationError as exc:
                if "rate limit" not in str(exc).lower() or attempt == len(self.RATE_LIMIT_BACKOFF_SECONDS):
                    raise
                await asyncio.sleep(self.RATE_LIMIT_BACKOFF_SECONDS[attempt])
        llm_ms = (time.perf_counter() - started) * 1000

        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({**request, "response": response}, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
        self.misses += 1
        self.last = {"cached": False, "llm_ms": llm_ms, "cache_key": key}
        return response
