from dataclasses import dataclass, field

from app.core.logging import logger
from app.schemas.retrieval import RetrievedChunk

DEFAULT_SYSTEM_PROMPT = """You are a technical documentation assistant. Your role is to answer questions based strictly on the retrieved context provided below.

Rules:
- Answer ONLY using the information in the retrieved context.
- Do NOT use any prior knowledge or external information.
- Do NOT make up, infer, or hallucinate any facts, figures, or details.
- If the context does not contain the answer, explicitly state: "The provided documents do not contain information about this."
- Cite the source document name and page number (if available) for each piece of information you use.
- Be concise and precise. Quote directly when helpful.
- If the context partially answers the question, only address the part that is covered."""


@dataclass
class PromptResult:
    system_prompt: str
    user_prompt: str


class PromptBuilder:
    def build_prompt(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        system_prompt: str | None = None,
        history: list[dict] | None = None,
    ) -> PromptResult:
        resolved_system = system_prompt or DEFAULT_SYSTEM_PROMPT

        context_blocks: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk.document_name
            if chunk.page_number is not None:
                source += f" (page {chunk.page_number})"
            block = (
                f"[{i}] Source: {source}\n"
                f"    Content: {chunk.content}"
            )
            context_blocks.append(block)

        context_text = "\n\n".join(context_blocks)

        history_block = ""
        if history:
            lines = ["Conversation History:"]
            for entry in history:
                role = entry.get("role", "user").capitalize()
                content = entry.get("content", "")
                lines.append(f"{role}: {content}")
            history_block = "\n".join(lines) + "\n\n"

        user_prompt = (
            "Retrieved Context:\n"
            "------------------\n"
            f"{context_text}\n\n"
            "------------------\n"
            f"{history_block}"
            f"Question: {question}"
        )

        logger.info(
            "Prompt built: %d chunks, history=%d msgs, system=%d chars, user=%d chars",
            len(chunks),
            len(history) if history else 0,
            len(resolved_system),
            len(user_prompt),
        )

        return PromptResult(system_prompt=resolved_system, user_prompt=user_prompt)
