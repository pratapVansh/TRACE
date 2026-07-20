"""Response formatter — enforces answer quality rules.

Ensures every response is concise (150–300 words by default), well
structured, and free of repetition, document dumps, and fluff.
"""

import logging
import re
from typing import Any

from app.schemas.rag import Citation

logger = logging.getLogger(__name__)


_MIN_WORDS = 150
_MAX_WORDS = 300


class ResponseFormatter:
    """Enforces answer quality: length, structure, conciseness.

    Usage::

        formatter = ResponseFormatter()
        formatted = formatter.format(
            answer=raw_answer,
            citations=result.citations,
            confidence=result.confidence,
            question=original_question,
        )
    """

    def format(
        self,
        answer: str,
        *,
        citations: list[Citation] | None = None,
        confidence: float = 0.0,
        question: str | None = None,
        max_words: int = _MAX_WORDS,
        min_words: int = _MIN_WORDS,
    ) -> str:
        """Apply all formatting rules."""
        if not answer.strip():
            return answer

        result = answer

        # 1. Strip leading/trailing whitespace
        result = result.strip()

        # 2. Remove question repetition from the beginning
        if question:
            result = self._remove_question_prefix(result, question)

        # 3. Remove verbose document dumps
        result = self._remove_document_dumps(result)

        # 4. Remove "Current Question" / "Conversation Summary" section headers
        result = self._remove_internal_headers(result)

        # 5. Ensure the required structure
        result = self._ensure_structure(result, citations, confidence)

        # 6. Enforce word limits
        word_count = self._count_words(result)
        if word_count > max_words:
            logger.info("Truncating answer from %d to %d words", word_count, max_words)
            result = self._truncate_words(result, max_words)
        elif word_count < min_words and word_count < 50:
            pass

        return result

    # ── Public helpers (useful for standalone use) ──────────────────────

    @staticmethod
    def count_words(text: str) -> int:
        return len(text.split())

    @staticmethod
    def truncate_words(text: str, max_words: int) -> str:
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]) + "…"

    # ── Internal rules ─────────────────────────────────────────────────

    @staticmethod
    def _count_words(text: str) -> int:
        return len(text.split())

    @staticmethod
    def _truncate_words(text: str, max_words: int) -> str:
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]) + "…"

    @staticmethod
    def _remove_question_prefix(text: str, question: str) -> str:
        """Remove leading lines that repeat the user's question verbatim."""
        lines = text.splitlines()
        if not lines:
            return text

        # Remove standalone "## Current Question" header line
        stripped = lines[0].strip()
        if stripped.startswith("## Current Question") or stripped.startswith("Current Question"):
            lines = lines[1:]

        # If the next line(s) repeat the question verbatim, remove them
        question_lower = question.strip().lower()
        cleaned = []
        skipped_question = False
        for line in lines:
            line_stripped = line.strip()
            if not skipped_question and (
                line_stripped.lower() == question_lower
                or line_stripped.lower().rstrip("?") == question_lower.rstrip("?")
                or line_stripped.lower().startswith(question_lower[:60])
            ):
                skipped_question = True
                continue
            cleaned.append(line)

        return "\n".join(cleaned).strip()

    @staticmethod
    def _remove_document_dumps(text: str) -> str:
        """Remove verbose document summary blocks.

        Removes:
        - Lines starting with ``- **[`` (document citations like ``- **[DocName]**``)
        - Lines that are just bare document names with scores
        - Bulleted lists of the form ``1. [Source] (score=0.xx): content``
        - ``### Retrieved Documents`` sections and similar
        """
        lines = text.splitlines()
        cleaned: list[str] = []
        in_bad_section = False

        for line in lines:
            stripped = line.strip()

            # Detect section headers that introduce document dumps
            if re.match(r"^#{1,3}\s*(Retrieved Documents|Reference Documents|Evidence Sources|Documents Consulted)", stripped, re.IGNORECASE):
                in_bad_section = True
                continue
            if stripped.startswith("### Retrieved ") or stripped.startswith("## Retrieved "):
                in_bad_section = True
                continue

            # End of bad section (next heading or blank line after content)
            if in_bad_section and (stripped.startswith("##") or stripped.startswith("---") or stripped == ""):
                in_bad_section = False
                if stripped:
                    cleaned.append(line)
                continue

            if in_bad_section:
                continue

            # Skip individual document citation lines
            if re.match(r"^- \*\*\[", stripped):
                continue
            if re.match(r"^\d+\.\s*\[.+\]\s*\(score=", stripped):
                continue
            if re.match(r"^- \*\*.+\*\* --\[", stripped):
                continue

            cleaned.append(line)

        return "\n".join(cleaned).strip()

    @staticmethod
    def _remove_internal_headers(text: str) -> str:
        """Remove internal agent section headers that shouldn't reach the user."""
        headers_to_remove = [
            "Current Question",
            "Conversation Summary",
            "Previous Findings \\(from earlier queries\\)",
            "Accumulated Evidence \\(entire conversation\\)",
            "Execution Trail",
            "Current Agent Outputs",
            "Prior Agent Outputs",
            "Prior Step Outputs",
            "Execution Snapshots",
            "Step Outputs",
            "Agent Scratchpad",
        ]
        lines = text.splitlines()
        cleaned: list[str] = []
        in_removed_section = False

        for line in lines:
            stripped = line.strip()
            is_header = any(
                re.match(rf"^#{{1,3}}\s*{pattern}\s*$", stripped, re.IGNORECASE)
                for pattern in headers_to_remove
            )
            if is_header:
                in_removed_section = True
                continue
            if in_removed_section and stripped == "":
                in_removed_section = False
                continue
            if in_removed_section:
                continue
            cleaned.append(line)

        return "\n".join(cleaned).strip()

    @staticmethod
    def _find_existing_headings(text: str) -> set[str]:
        """Find all section heading labels (both ``## Name`` and ``**Name**`` styles)."""
        headings: set[str] = set()
        for line in text.splitlines():
            stripped = line.strip()
            # ## Style
            m = re.match(r"^##\s+(.+?)\s*$", stripped)
            if m:
                headings.add(m.group(1).lower())
                continue
            # **bold** style at line start
            m = re.match(r"^\*\*(.+?)\*\*\s*[—\-–]?\s*", stripped)
            if m:
                headings.add(m.group(1).lower())
        return headings

    @staticmethod
    def _ensure_structure(
        answer: str,
        citations: list[Citation] | None = None,
        confidence: float = 0.0,
    ) -> str:
        """Ensure the answer has the required structure.

        Required sections (order matters):
        1. Short answer (direct response, 1-3 sentences)
        2. Evidence (key supporting facts)
        3. Confidence (explicit statement)
        4. Hypothesis (only if applicable)
        5. References (document citations)

        Only appends sections the LLM didn't already include.
        """
        existing = ResponseFormatter._find_existing_headings(answer)

        parts: list[str] = []

        # The first paragraph(s) are the short answer
        parts.append(answer.strip())

        # Add missing sections
        has_evidence = any("evidence" in s for s in existing)
        if not has_evidence and citations:
            evidence_lines = []
            for c in citations[:5]:
                if c.score > 0:
                    evidence_lines.append(
                        f"- {c.document_name} (score={c.score:.2f})"
                    )
            if evidence_lines:
                parts.append("## Evidence\n" + "\n".join(evidence_lines))

        has_confidence = any("confidence" in s for s in existing)
        if not has_confidence:
            label = "High" if confidence >= 0.7 else "Moderate" if confidence >= 0.4 else "Low"
            parts.append(f"## Confidence\n{label} ({confidence:.0%})")

        has_references = any("reference" in s for s in existing)
        if not has_references and citations:
            ref_lines = [
                f"- {c.document_name}"
                for c in citations[:5]
            ]
            if ref_lines:
                parts.append("## References\n" + "\n".join(ref_lines))

        result = "\n\n".join(parts)
        if not result.endswith("More details available."):
            result += "\n\nMore details available."
        return result
