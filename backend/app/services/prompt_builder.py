from dataclasses import dataclass

from app.core.logging import logger
from app.schemas.hybrid import GraphFact
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

GRAPH_AWARE_SYSTEM_PROMPT = """You are a technical documentation assistant with access to both document excerpts and a knowledge graph of entities and relationships.

Rules:
- Answer ONLY using the information in the retrieved context and graph knowledge.
- Do NOT use any prior knowledge or external information.
- Do NOT make up, infer, or hallucinate any facts, figures, or details.
- If the context does not contain the answer, explicitly state: "The provided documents do not contain information about this."
- Cite the source document name and page number (if available) for each piece of information you use.
- When using graph facts, reference the entity names and relationship types provided.
- Be concise and precise. Quote directly when helpful.
- If the context partially answers the question, only address the part that is covered."""

# M35: token budget — approximate (chars / 4)
_MAX_USER_PROMPT_TOKENS = 6000
_MAX_CHARS = _MAX_USER_PROMPT_TOKENS * 4


@dataclass
class PromptResult:
    system_prompt: str
    user_prompt: str


def _format_graph_facts_for_chunk(facts: list[GraphFact]) -> str:
    if not facts:
        return ""
    lines = ["    Graph Facts:"]
    for f in facts:
        if f.relationship_type and f.related_entity:
            lines.append(f"    - {f.entity_name} ({f.entity_type}) — {f.relationship_type} → {f.related_entity}")
        else:
            lines.append(f"    - {f.entity_name} ({f.entity_type})")
    return "\n".join(lines)


def _build_graph_knowledge_block(graph_facts: list[GraphFact]) -> str:
    if not graph_facts:
        return ""
    lines = ["Graph Knowledge:", "------------------"]
    seen: set[str] = set()
    for f in graph_facts:
        key = f"{f.entity_name}:{f.relationship_type}:{f.related_entity}"
        if key in seen:
            continue
        seen.add(key)
        if f.relationship_type and f.related_entity:
            lines.append(f"• {f.entity_name} ({f.entity_type}) —[{f.relationship_type}]→ {f.related_entity}")
        else:
            lines.append(f"• {f.entity_name} ({f.entity_type})")
    return "\n".join(lines)


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


class PromptBuilder:
    def build_prompt(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        system_prompt: str | None = None,
        history: list[dict] | None = None,
        graph_facts: list[GraphFact] | None = None,
        max_tokens: int = _MAX_USER_PROMPT_TOKENS,
    ) -> PromptResult:
        use_graph = graph_facts is not None and len(graph_facts) > 0
        resolved_system = system_prompt or (GRAPH_AWARE_SYSTEM_PROMPT if use_graph else DEFAULT_SYSTEM_PROMPT)

        # M35: build chunk blocks with score-based ranking
        chunk_blocks: list[tuple[float, str, RetrievedChunk]] = []
        for chunk in chunks:
            source = chunk.document_name
            if chunk.page_number is not None:
                source += f" (page {chunk.page_number})"
            block = (
                f"Source: {source}\n"
                f"    Content: {chunk.content}"
            )
            chunk_blocks.append((chunk.score, block, chunk))

        # Sort by score descending (highest relevance first)
        chunk_blocks.sort(key=lambda x: x[0], reverse=True)

        # M35: build graph block
        graph_block = ""
        graph_fact_list = graph_facts or []
        if use_graph:
            graph_block = "\n\n" + _build_graph_knowledge_block(graph_fact_list)

        # M35: build history block
        history_block = ""
        if history:
            lines = ["Conversation History:"]
            for entry in history:
                role = entry.get("role", "user").capitalize()
                content = entry.get("content", "")
                lines.append(f"{role}: {content}")
            history_block = "\n".join(lines) + "\n\n"

        # M35: measure overhead (everything that isn't a chunk)
        overhead = (
            "Retrieved Context:\n"
            "------------------\n"
            f"{graph_block}\n\n"
            "------------------\n"
            f"{history_block}"
            f"Question: {question}"
        )
        overhead_chars = len(overhead)
        available_chars = max_chars = max_tokens * 4 - overhead_chars

        # M35: select chunks that fit within budget
        selected_blocks: list[str] = []
        used_chars = 0
        for i, (score, block, chunk) in enumerate(chunk_blocks, 1):
            numbered_block = f"[{i}] {block}"
            block_cost = len(numbered_block) + 2  # +2 for "\n\n" separator
            if used_chars + block_cost <= available_chars:
                selected_blocks.append(numbered_block)
                used_chars += block_cost
            else:
                # M35: truncate chunk content to fit within remaining budget
                remaining = available_chars - used_chars
                if remaining > 60:
                    source_line = f"[{i}] Source: {source}"
                    truncated_content = chunk.content[:max(remaining - len(source_line) - 30, 0)]
                    truncated_block = f"{source_line}\n    Content: {truncated_content}...[truncated]"
                    selected_blocks.append(truncated_block)
                    used_chars += len(truncated_block)
                elif not selected_blocks and remaining > 0:
                    source_line = f"[{i}] Source: {source}"
                    truncated_content = chunk.content[:max(remaining - len(source_line) - 30, 0)]
                    truncated_block = f"{source_line}\n    Content: {truncated_content}...[truncated]"
                    selected_blocks.append(truncated_block)
                    used_chars += len(truncated_block)
                break

        context_text = "\n\n".join(selected_blocks)

        user_prompt = (
            "Retrieved Context:\n"
            "------------------\n"
            f"{context_text}"
            f"{graph_block}\n\n"
            "------------------\n"
            f"{history_block}"
            f"Question: {question}"
        )

        logger.info(
            "Prompt built: %d chunks (%d selected), %d graph_facts, history=%d msgs, "
            "system=%d chars, user=%d chars, user_tokens=%d",
            len(chunks),
            len(selected_blocks),
            len(graph_fact_list) if graph_facts else 0,
            len(history) if history else 0,
            len(resolved_system),
            len(user_prompt),
            _estimate_tokens(user_prompt),
        )

        return PromptResult(system_prompt=resolved_system, user_prompt=user_prompt)
