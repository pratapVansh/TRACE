import math
import re
from datetime import UTC, datetime

from app.core.config import settings
from app.core.logging import logger
from app.schemas.vector import RankingWeights
from app.services.vector_store import VectorStore, VectorStoreOperationError

# Lazy import for qdrant types
try:
    from qdrant_client.models import Filter  # noqa: PLC0415
    _QD_RANK_AVAILABLE = True
except ImportError:
    Filter = object  # type: ignore[assignment,misc]
    _QD_RANK_AVAILABLE = False


class RankingService:

    def __init__(self, vector_store: VectorStore) -> None:
        self._vector_store = vector_store

    async def ranked_search(
        self,
        query_vector: list[float],
        query_text: str,
        top_k: int = 10,
        query_filter: Filter | None = None,
        weights: RankingWeights | None = None,
    ) -> list[dict]:
        w = weights or RankingWeights()
        total = w.semantic + w.keyword + w.metadata_boost + w.freshness
        if total <= 0:
            total = 1.0

        w_sem = w.semantic / total
        w_key = w.keyword / total
        w_meta = w.metadata_boost / total
        w_fresh = w.freshness / total

        limit_factor = 3
        fetch_k = top_k * limit_factor

        candidates: dict[str, dict] = {}

        try:
            vector_results = await self._vector_store.search(
                query_vector, fetch_k, query_filter
            )
            for hit in vector_results:
                pid = hit["payload"].get("chunk_id", "")
                if not pid:
                    continue
                if pid not in candidates:
                    candidates[pid] = {
                        "payload": hit["payload"],
                        "vector_score": hit["score"],
                        "vector_rank": len(candidates),
                    }
                else:
                    candidates[pid]["vector_score"] = max(
                        candidates[pid]["vector_score"], hit["score"]
                    )
        except VectorStoreOperationError:
            pass

        try:
            text_results = await self._vector_store.fulltext_search(
                query_text, fetch_k, query_filter
            )
            for hit in text_results:
                pid = hit["payload"].get("chunk_id", "")
                if not pid:
                    continue
                if pid not in candidates:
                    candidates[pid] = {
                        "payload": hit["payload"],
                        "vector_score": 0.0,
                        "vector_rank": None,
                    }
        except VectorStoreOperationError:
            pass

        if not candidates:
            return []

        query_terms = self._tokenize(query_text)
        decay_days = settings.ranking_freshness_decay_days
        now_ts = datetime.now(UTC).timestamp()

        scored: list[tuple[str, dict, float]] = []

        for pid, cand in candidates.items():
            payload = cand["payload"]
            content = payload.get("content", "") or ""
            metadata = payload.get("metadata") or {}
            upload_date = payload.get("upload_date")

            sem_score = cand["vector_score"]

            key_score = self._compute_keyword_match(query_terms, content)

            meta_score = self._compute_metadata_boost(query_terms, metadata)

            fresh_score = self._compute_freshness(upload_date, now_ts, decay_days)

            final = w_sem * sem_score + w_key * key_score + w_meta * meta_score + w_fresh * fresh_score

            scored.append((pid, payload, final))

        scored.sort(key=lambda x: x[2], reverse=True)

        return [
            {"score": s, "payload": p}
            for _, p, s in scored[:top_k]
        ]

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-zA-Z0-9]+", text.lower())

    def _compute_keyword_match(
        self, query_terms: list[str], content: str
    ) -> float:
        if not query_terms or not content:
            return 0.0
        content_lower = content.lower()
        matched = sum(1 for t in query_terms if t in content_lower)
        return matched / len(query_terms)

    def _compute_metadata_boost(
        self, query_terms: list[str], metadata: dict
    ) -> float:
        if not query_terms or not metadata:
            return 0.0
        parts: list[str] = []
        for v in metadata.values():
            if isinstance(v, str):
                parts.append(v)
            elif isinstance(v, (list, tuple)):
                parts.extend(str(x) for x in v if x)
            elif v is not None:
                parts.append(str(v))
        text = " ".join(parts).lower()
        if not text:
            return 0.0
        matched = sum(1 for t in query_terms if t in text)
        return matched / len(query_terms)

    def _compute_freshness(
        self,
        upload_date: float | None,
        now_ts: float,
        decay_days: int,
    ) -> float:
        if upload_date is None:
            return 0.0
        seconds_since = now_ts - upload_date
        if seconds_since <= 0:
            return 1.0
        days_since = seconds_since / 86400.0
        return math.exp(-days_since / decay_days)
