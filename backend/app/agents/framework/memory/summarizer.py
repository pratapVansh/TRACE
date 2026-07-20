from abc import ABC, abstractmethod
from typing import Any


class ContextSummarizer(ABC):
    """Interface for summarizing agent context into a concise prompt.

    Designed to be backed by an LLM in production, but ships with
    a lightweight default that works without any external service.
    """

    @abstractmethod
    async def summarize_messages(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 2000,
    ) -> str:
        """Produce a summary of the given message list."""

    @abstractmethod
    async def summarize_text(
        self,
        text: str,
        max_tokens: int = 500,
    ) -> str:
        """Produce a summary of an arbitrary text block."""


class SimpleSummarizer(ContextSummarizer):
    """Lightweight summarizer that truncates text to an approximate
    token budget.

    No external dependencies — uses a simple whitespace-based token
    estimate.  Replace with an LLM-backed implementation when the
    agent framework enters production.
    """

    async def summarize_messages(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 2000,
    ) -> str:
        if not messages:
            return ""

        lines: list[str] = []
        estimate = 0
        for m in reversed(messages):
            line = f"{m.get('role', 'unknown')}: {m.get('content', '')}"
            approx = max(1, len(line.split()))
            if estimate + approx > max_tokens:
                break
            lines.append(line)
            estimate += approx

        lines.reverse()

        if len(lines) < len(messages):
            lines.insert(
                0,
                f"[{len(messages) - len(lines)} earlier message(s) omitted]",
            )

        return "\n".join(lines)

    async def summarize_text(
        self,
        text: str,
        max_tokens: int = 500,
    ) -> str:
        words = text.split()
        if len(words) <= max_tokens:
            return text
        return " ".join(words[:max_tokens]) + "..."
