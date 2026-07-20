"""Synthesis agent — produces a single coherent report from multi-agent output.

Instead of concatenating individual agent answers, the ``SynthesisAgent``
uses an LLM (or a smart heuristic fallback) to read every agent's
analysis, reasoning, and evidence, plus the full conversation history,
then produces a unified report that incorporates accumulated findings,
resolves contradictions, and synthesises complementary evidence.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.ai.base import LLMProvider
from app.agents.framework.response import AgentResponse
from app.schemas.rag import Citation, GraphCitation

logger = logging.getLogger(__name__)

_SYNTHESIS_SYSTEM_PROMPT = """You are a concise answer writer for an industrial asset management system.
Your job is to answer the user's question directly and concisely
(150-300 words) using the conversation history and agent outputs below.

CRITICAL RULES:
1. Never invent: maintenance history, part numbers, spare inventory, failure causes, or schedules.
2. Classify statements: FACT (evidenced), HYPOTHESIS (inference), UNKNOWN (no evidence). Only state FACTS confidently.
3. If evidence is missing, say: "No supporting evidence found."
4. Cite top 3 most relevant documents. Rank by score.
5. Target: 150-300 words. Be concise.
6. NEVER repeat the user's question.
7. NEVER dump document summaries or verbose reference lists.
8. Answer first, then evidence. Do not explain unrelated information.
9. Only expand beyond 300 words if the user explicitly asks for detail.

STRUCTURE YOUR ANSWER (use these headings when relevant):
- **Short Answer** — direct response to the user, 1-3 sentences
- **Evidence** — key facts with source citations
- **Confidence** — high/medium/low with brief explanation
- **Hypothesis** — only if the data supports a reasonable inference (label clearly)
- **References** — document names only, no summaries

Use specialized cards sparingly, only when critical:
   > [!WARNING] For safety-critical warnings
   > [!ASSUMPTION] For unsupported claims

Resolve contradictions by evaluating evidence strength and agent confidence.
End with: "More details available."

You MUST respond with ONLY valid JSON in this format:
{
  "answer": "the concise, structured answer (150-300 words)",
  "reasoning": "brief reasoning for how you arrived at this answer",
  "confidence": 0.0-1.0,
  "confidence_explanation": "why this confidence score"
}"""


def _truncate(text: str, max_chars: int = 500) -> str:
    """Truncate *text* to *max_chars* characters, appending ``…``."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


class SynthesisAgent:
    """Produces a single synthesised report from agent outputs and accumulated context.

    Uses the LLM when available, otherwise falls back to a heuristic
    merge that combines all findings into one coherent answer.
    """

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self._llm = llm_provider

    async def synthesize(
        self,
        question: str,
        agent_results: list[AgentResponse],
        execution_history: list[dict[str, Any]] | None = None,
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
        *,
        conversation_summary: str = "",
        previous_findings: str = "",
        accumulated_evidence: str = "",
    ) -> AgentResponse:
        """Merge multiple agent responses into one synthesised report.

        Args:
            question: The original user question.
            agent_results: Responses from all agents that executed.
            execution_history: Optional structured history from the
                collaboration context.
            conversation_summary: Summary of all prior conversation turns.
            previous_findings: Findings from earlier queries in the conversation.
            accumulated_evidence: Evidence, citations, and data gathered
                across the entire conversation.

        Returns:
            A single ``AgentResponse`` with the synthesised report,
            deduplicated citations, and aggregated confidence.
        """
        if not agent_results:
            return AgentResponse(
                answer="No agents produced results to synthesise.",
                confidence=0.0,
            )

        if self._llm is not None:
            try:
                return await self._llm_synthesize(
                    question, agent_results, execution_history,
                    stream_callback,
                    conversation_summary=conversation_summary,
                    previous_findings=previous_findings,
                    accumulated_evidence=accumulated_evidence,
                )
            except Exception as exc:
                logger.warning("LLM synthesis failed, using heuristic fallback: %s", exc)

        return self._heuristic_synthesize(question, agent_results, previous_findings)

    async def _llm_synthesize(
        self,
        question: str,
        results: list[AgentResponse],
        history: list[dict[str, Any]] | None = None,
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
        *,
        conversation_summary: str = "",
        previous_findings: str = "",
        accumulated_evidence: str = "",
    ) -> AgentResponse:
        prompt = self._build_synthesis_prompt(
            question, results, history,
            conversation_summary=conversation_summary,
            previous_findings=previous_findings,
            accumulated_evidence=accumulated_evidence,
        )

        if stream_callback:
            raw_text = ""
            async for chunk in self._llm.stream_generate(
                prompt=prompt,
                system_prompt=_SYNTHESIS_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=4096,
            ):
                raw_text += chunk
                if stream_callback:
                    await stream_callback(chunk)
            raw = raw_text
        else:
            raw = await self._llm.generate(
                prompt=prompt,
                system_prompt=_SYNTHESIS_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=4096,
            )

        data = _extract_json_dict(raw)
        merged = self._merge_metadata(results)

        return AgentResponse(
            answer=data.get("answer", merged.answer),
            reasoning=data.get("reasoning", merged.reasoning),
            citations=merged.citations,
            graph_citations=merged.graph_citations,
            confidence=min(float(data.get("confidence", merged.confidence)), 1.0),
            confidence_explanation=data.get("confidence_explanation", merged.confidence_explanation),
            tools_used=merged.tools_used,
            agent_name="Synthesis",
        )

    def _build_synthesis_prompt(
        self,
        question: str,
        results: list[AgentResponse],
        history: list[dict[str, Any]] | None = None,
        *,
        conversation_summary: str = "",
        previous_findings: str = "",
        accumulated_evidence: str = "",
    ) -> str:
        lines = [f"## Current Question\n{question}\n"]

        # ── Accumulated conversation context ────────────────────
        if conversation_summary:
            lines.append("## Conversation Summary\n")
            lines.append(conversation_summary)
            lines.append("")

        if previous_findings:
            lines.append("## Previous Findings (from earlier queries)\n")
            lines.append(previous_findings)
            lines.append("")

        if accumulated_evidence:
            lines.append("## Accumulated Evidence (entire conversation)\n")
            lines.append(accumulated_evidence)
            lines.append("")

        # ── Execution trail ─────────────────────────────────────
        if history:
            lines.append("## Execution Trail (current query)\n")
            for i, snap in enumerate(history):
                lines.append(f"### Step {i + 1}: {snap.get('agent_name', snap.get('agent_id', '?'))}")
                if snap.get("messages_posted"):
                    lines.append(f"Messages posted: {', '.join(snap['messages_posted'])}")
                lines.append("")

        # ── Current agent outputs ───────────────────────────────
        lines.append("## Current Agent Outputs\n")
        for i, r in enumerate(results):
            lines.append(f"### Agent {i + 1}: {r.agent_name or 'Unknown'}")
            lines.append(f"**Confidence**: {r.confidence:.2f}")
            if r.confidence_explanation:
                lines.append(f"**Confidence explanation**: {r.confidence_explanation}")
            if r.reasoning:
                lines.append(f"**Reasoning**: {r.reasoning}")
            lines.append(f"**Findings**: {_truncate(r.answer)}")
            if r.tools_used:
                lines.append(f"**Tools**: {', '.join(r.tools_used)}")
            lines.append("")

        lines.append("Produce a single synthesised JSON report as specified in the system prompt.")
        return "\n".join(lines)

    @staticmethod
    def _heuristic_synthesize(
        question: str,
        results: list[AgentResponse],
        previous_findings: str = "",
    ) -> AgentResponse:
        """Fallback: combine all findings, prepend previous if available."""
        if not results:
            return AgentResponse(answer="", confidence=0.0)

        sorted_results = sorted(results, key=lambda r: r.confidence, reverse=True)
        best = sorted_results[0]
        merged = SynthesisAgent._merge_metadata(results)

        # Single result, no prior context → return as-is
        if len(sorted_results) == 1 and not previous_findings:
            merged.answer = sorted_results[0].answer or merged.answer
            return merged

        sections: list[str] = []

        if previous_findings:
            sections.append("## Previous Findings\n" + previous_findings)

        if len(sorted_results) == 1:
            sections.append("## Current Findings\n" + (sorted_results[0].answer or ""))
        else:
            for r in sorted_results:
                if r.answer:
                    sections.append(f"--- {r.agent_name} ---\n{r.answer}")

        merged.answer = "\n\n".join(sections)
        return merged

    @staticmethod
    def _merge_metadata(results: list[AgentResponse]) -> AgentResponse:
        seen_citations: set[str] = set()
        combined_citations: list[Citation] = []
        seen_graph: set[str] = set()
        combined_graph: list[GraphCitation] = []
        all_tools: set[str] = set()
        confidences: list[float] = []
        answer = ""
        reasoning = ""

        for r in results:
            if r.tools_used:
                all_tools.update(r.tools_used)
            for c in r.citations:
                key = f"{c.document_name}:{c.page_number}:{c.chunk_content}"
                if key not in seen_citations:
                    seen_citations.add(key)
                    combined_citations.append(c)
            for gc in r.graph_citations:
                key = f"{gc.entity_name}:{gc.relationship_type}:{gc.related_entity}"
                if key not in seen_graph:
                    seen_graph.add(key)
                    combined_graph.append(gc)
            if r.confidence > 0:
                confidences.append(r.confidence)
            if r.answer:
                answer = r.answer
            if r.reasoning:
                reasoning = reasoning or r.reasoning

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return AgentResponse(
            answer=answer,
            reasoning=reasoning,
            citations=combined_citations,
            graph_citations=combined_graph,
            confidence=max(avg_conf, max(confidences) if confidences else 0.0),
            tools_used=sorted(all_tools),
        )


def _extract_json_dict(text: str) -> dict[str, Any]:
    """Parse JSON from LLM output, handling markdown fences."""
    import json

    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("```"):
                start = i + 1
                break
        end = len(lines)
        for i in range(len(lines) - 1, start - 1, -1):
            if lines[i].strip().startswith("```"):
                end = i
                break
        text = "\n".join(lines[start:end])

    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM synthesis did not return a JSON object")
    return data
