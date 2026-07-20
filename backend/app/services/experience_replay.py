"""Experience Replay — store, retrieve, and search past investigations."""

import logging
import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.investigation import InvestigationRecord
from app.schemas.investigation import (
    ConfidenceSnapshot,
    InvestigationCreate,
    InvestigationResponse,
    InvestigationSearchResult,
)
from app.services.embedding_service import _encode_batch_async

_SIMILARITY_TOP_K = 5


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(va * vb for va, vb in zip(a, b))
    na = math.sqrt(sum(v * v for v in a))
    nb = math.sqrt(sum(v * v for v in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class ExperienceReplayService:
    """Stores completed investigations and retrieves similar past cases."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Store ────────────────────────────────────────────────────

    async def store_investigation(
        self,
        payload: InvestigationCreate,
    ) -> InvestigationResponse:
        embedding = await self._generate_embedding(payload.problem)

        now = datetime.now(timezone.utc)
        record = InvestigationRecord(
            id=uuid.uuid4(),
            conversation_id=payload.conversation_id,
            user_id=uuid.UUID(payload.user_id) if payload.user_id else None,
            problem=payload.problem,
            root_cause=payload.root_cause,
            actions=payload.actions,
            evidence_summary=payload.evidence_summary,
            success=payload.success,
            failure_reason=payload.failure_reason,
            confidence=payload.confidence,
            confidence_evolution=[
                {"confidence": payload.confidence, "timestamp": now.isoformat()},
            ],
            citations=payload.citations,
            graph_citations=payload.graph_citations,
            tools_used=payload.tools_used,
            embedding=embedding,
            created_at=now,
            updated_at=now,
        )
        self._session.add(record)
        await self._session.flush()

        logger.info(
            "Investigation stored id=%s problem=%s… confidence=%.2f success=%s",
            record.id, payload.problem[:60], payload.confidence, payload.success,
        )
        return self._to_response(record)

    async def store_investigation_from_components(
        self,
        problem: str,
        root_cause: str,
        actions: str,
        evidence_summary: str,
        success: bool,
        failure_reason: str | None,
        confidence: float,
        citations: list[dict],
        graph_citations: list[dict],
        tools_used: list[str],
        conversation_id: str | None = None,
        user_id: str | None = None,
    ) -> InvestigationResponse:
        payload = InvestigationCreate(
            problem=problem,
            root_cause=root_cause,
            actions=actions,
            evidence_summary=evidence_summary,
            success=success,
            failure_reason=failure_reason,
            confidence=confidence,
            citations=citations,
            graph_citations=graph_citations,
            tools_used=tools_used,
            conversation_id=conversation_id,
            user_id=user_id,
        )
        return await self.store_investigation(payload)

    # ── Retrieve ─────────────────────────────────────────────────

    async def retrieve_similar(
        self,
        problem: str,
        top_k: int = _SIMILARITY_TOP_K,
    ) -> list[InvestigationSearchResult]:
        """Find past investigations semantically similar to *problem*."""
        query_embedding = await self._generate_embedding(problem)
        if query_embedding is None:
            return []

        result = await self._session.execute(
            select(InvestigationRecord)
            .where(InvestigationRecord.embedding.isnot(None))
            .order_by(InvestigationRecord.created_at.desc())
        )
        records: list[InvestigationRecord] = list(result.scalars().all())

        scored: list[tuple[float, InvestigationRecord]] = []
        for rec in records:
            if rec.embedding:
                sim = _cosine_similarity(query_embedding, rec.embedding)
                if sim > 0.3:
                    scored.append((sim, rec))

        scored.sort(key=lambda x: x[0], reverse=True)

        results: list[InvestigationSearchResult] = []
        for sim, rec in scored[:top_k]:
            results.append(InvestigationSearchResult(
                investigation_id=str(rec.id),
                problem=rec.problem[:200] if len(rec.problem) > 200 else rec.problem,
                root_cause=rec.root_cause[:300] if len(rec.root_cause) > 300 else rec.root_cause,
                actions=rec.actions[:200] if len(rec.actions) > 200 else rec.actions,
                success=rec.success,
                confidence=rec.confidence,
                similarity_score=round(sim, 4),
                created_at=rec.created_at,
            ))
            if rec.created_at:
                logger.debug(
                    "Similar case id=%s sim=%.4f problem=%s…",
                    rec.id, sim, rec.problem[:60],
                )

        logger.info(
            "retrieve_similar query=%s… found=%d top_score=%.4f",
            problem[:60], len(results), scored[0][0] if scored else 0,
        )
        return results

    async def get_by_id(
        self,
        investigation_id: str,
    ) -> InvestigationResponse | None:
        uid = uuid.UUID(investigation_id)
        result = await self._session.get(InvestigationRecord, uid)
        if result is None:
            return None
        return self._to_response(result)

    # ── Confidence evolution ─────────────────────────────────────

    async def update_confidence(
        self,
        investigation_id: str,
        new_confidence: float,
    ) -> InvestigationResponse | None:
        uid = uuid.UUID(investigation_id)
        record = await self._session.get(InvestigationRecord, uid)
        if record is None:
            return None

        record.confidence = new_confidence
        snapshot = {
            "confidence": new_confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        evolution: list[dict] = list(record.confidence_evolution or [])
        evolution.append(snapshot)
        record.confidence_evolution = evolution

        await self._session.flush()
        logger.info(
            "Confidence updated id=%s new=%.2f total_snapshots=%d",
            investigation_id, new_confidence, len(evolution),
        )
        return self._to_response(record)

    # ── Internal helpers ─────────────────────────────────────────

    async def _generate_embedding(self, text: str) -> list[float] | None:
        if not text.strip():
            return None
        try:
            results = await _encode_batch_async([text])
            return results[0] if results else None
        except Exception:
            logger.warning("Embedding generation failed for experience replay", exc_info=True)
            return None

    @staticmethod
    def _to_response(record: InvestigationRecord) -> InvestigationResponse:
        evolution_raw: list[dict] = list(record.confidence_evolution or [])
        evolution = [
            ConfidenceSnapshot(
                confidence=snap.get("confidence", 0.0),
                timestamp=snap.get("timestamp"),
            )
            for snap in evolution_raw
        ]
        return InvestigationResponse(
            investigation_id=str(record.id),
            problem=record.problem,
            root_cause=record.root_cause,
            actions=record.actions,
            evidence_summary=record.evidence_summary,
            success=record.success,
            failure_reason=record.failure_reason,
            confidence=record.confidence,
            confidence_evolution=evolution,
            citations=list(record.citations or []),
            graph_citations=list(record.graph_citations or []),
            tools_used=list(record.tools_used or []),
            conversation_id=record.conversation_id,
            user_id=str(record.user_id) if record.user_id else None,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
