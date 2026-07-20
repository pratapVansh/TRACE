"""Self-critique — verifies evidence, checks confidence, detects hallucinations,
and revises answers below confidence threshold."""

import json
import logging
from dataclasses import dataclass, field

from app.ai.base import LLMProvider
from app.schemas.rag import Citation, GraphCitation

logger = logging.getLogger(__name__)

_CONFIDENCE_REVISION_THRESHOLD = 0.5

_CRITIQUE_SYSTEM_PROMPT = """You are a quality assurance agent. Your job is to critique an AI-generated analysis answer for evidence quality, contradictions, and hallucinations.

Evaluate the answer against the provided evidence citations. Be strict: flag any claim that lacks support.

Return a JSON object with exactly these keys:
{
  "confidence_adjustment": <float -0.3 to 0.3>,
  "issues": ["list of specific quality issues"],
  "hallucinations": ["list of unsupported claims not backed by evidence"],
  "missing_evidence": ["types of evidence that would strengthen the answer"],
  "revised_answer": "<corrected answer text, or empty string if no revision needed>",
  "reasoning_report": "<detailed multi-paragraph internal analysis covering evidence verification, contradiction check, hallucination detection, and confidence assessment>"
}

Rules:
- confidence_adjustment: negative if overconfident for the available evidence, positive if underconfident
- revised_answer: only provide if the answer has significant issues (hallucinations, contradictions, or confidence < 0.5); otherwise return empty string
- reasoning_report: write in first person as an internal trace, include specific evidence citations referenced
- Do NOT fabricate evidence — only reference what is listed in the citations"""


@dataclass
class CritiqueResult:
    confidence_adjustment: float = 0.0
    issues: list[str] = field(default_factory=list)
    hallucinations: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    revised_answer: str = ""
    reasoning_report: str = ""


class SelfCritique:
    """Critiques an AgentResponse and optionally revises it."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def critique(
        self,
        question: str,
        answer: str,
        citations: list[Citation],
        graph_citations: list[GraphCitation],
        confidence: float,
        confidence_explanation: str,
        tools_used: list[str],
    ) -> CritiqueResult:
        if not answer.strip():
            return CritiqueResult()

        citations_text = "\n".join(
            f"- [{c.document_name}] (score={c.score or c.similarity_score}): "
            f"{c.chunk_content or c.highlighted_excerpt or '(no excerpt)'}"
            for c in (citations or [])
        ) or "(none)"

        graph_text = "\n".join(
            f"- [{gc.entity_name}] --{gc.relationship_type}--> [{gc.related_entity}] "
            f"(confidence={gc.confidence})"
            for gc in (graph_citations or [])
        ) or "(none)"

        tools_text = ", ".join(tools_used) or "(none)"

        prompt = f"""Question: {question}

Answer: {answer}

Evidence Citations:
{citations_text}

Graph Evidence:
{graph_text}

Tools Used: {tools_text}

Stated Confidence: {confidence}
Confidence Explanation: {confidence_explanation}"""

        raw = await self._llm.generate(
            prompt=prompt,
            system_prompt=_CRITIQUE_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=2048,
        )

        result = self._parse(raw)

        result.confidence_adjustment = max(-0.3, min(0.3, result.confidence_adjustment))

        if result.hallucinations or result.issues:
            logger.info(
                "SelfCritique: question=%r… issues=%d hallucinations=%d",
                question[:60], len(result.issues), len(result.hallucinations),
            )

        return result

    def _parse(self, raw: str) -> CritiqueResult:
        result = CritiqueResult()
        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1]
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
                cleaned = cleaned.rsplit("```", 1)[0]
                cleaned = cleaned.strip()

            data = json.loads(cleaned)

            if "confidence_adjustment" in data:
                result.confidence_adjustment = float(data["confidence_adjustment"])
            if "issues" in data:
                result.issues = list(data["issues"])
            if "hallucinations" in data:
                result.hallucinations = list(data["hallucinations"])
            if "missing_evidence" in data:
                result.missing_evidence = list(data["missing_evidence"])
            if "revised_answer" in data and data["revised_answer"].strip():
                result.revised_answer = data["revised_answer"].strip()
            if "reasoning_report" in data:
                result.reasoning_report = data["reasoning_report"].strip()

        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("SelfCritique: failed to parse LLM output: %s", exc)
            logger.debug("Raw LLM output: %s", raw[:500])
            result.reasoning_report = f"[SelfCritique parse error: {exc}]"
            result.issues.append(f"Critique parsing failed: {exc}")

        return result
