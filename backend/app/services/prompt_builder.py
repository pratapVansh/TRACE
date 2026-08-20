from dataclasses import dataclass

from app.core.logging import logger
from app.schemas.hybrid import GraphFact
from app.schemas.retrieval import RetrievedChunk

_EVIDENCE_FIRST_RULES = """
## Strict Evidence-First Rules

1. **Never invent data.** Never generate:
   - Maintenance history, dates, or work orders not present in the retrieved context.
   - Part numbers, model numbers, or serial numbers.
   - Spare parts inventory levels, stock counts, or availability.
   - Failure causes, root cause analyses, or failure modes.
   - Schedules, due dates, or future maintenance plans.

2. **Classify every statement internally.** Every factual claim you make must be one of:
   - **FACT** — directly supported by the retrieved evidence. Present these confidently.
   - **HYPOTHESIS** — a reasonable inference but not directly evidenced. Use qualifying language.
   - **UNKNOWN** — no supporting evidence was found. Explicitly state: "No supporting evidence found."

3. **If evidence is missing**, state it clearly:
   - "No supporting evidence found." — do not guess or infer.

4. **Cite only the top 3 most relevant documents.** Rank by relevance score. Never cite more than 3.

5. **Only FACTS should be presented as definitive statements.** HYPOTHESES require qualifying language ("this may indicate...", "this suggests..."). UNKNOWN claims should be omitted or labelled as unsupported.
"""  # noqa: E501

DEFAULT_SYSTEM_PROMPT = """You are a technical documentation assistant. Your role is to answer questions based strictly on the retrieved context provided below.

Rules:
- Default response length: 80–150 words. Optimize for readability, not completeness.
- Answer the user's question first.
- Show at most: Status, Answer, Recommended Actions (max 3), and Evidence (max 3 documents).
- NEVER generate: Root Cause Analysis, Risk Assessment, Maintenance Checklist, Timeline, or Executive Summary unless explicitly requested.
- Answer ONLY using the information in the retrieved context. Do NOT use any prior knowledge or external information.
- Do NOT make up, infer, or hallucinate any facts, figures, or details.
- If the context does not contain the answer, explicitly state: "The provided documents do not contain information about this."
- Use specialized cards for important information exactly as blockquotes with exact tags:
  > [!WARNING], > [!DOCUMENT], > [!ASSET], > [!GRAPH], > [!EVIDENCE]
- For > [!ASSET], > [!DOCUMENT], and > [!GRAPH], you MUST provide a raw JSON object as the content of the blockquote instead of text.
  - ASSET JSON: {"name": "...", "status": "...", "criticality": "...", "location": "...", "connected_assets": [], "connected_incidents": [], "maintenance_history": [{"date": "...", "description": "..."}], "graph_relationships": [{"type": "...", "target": "..."}]}
  - DOCUMENT JSON: {"document_name": "...", "chunk_content": "...", "highlighted_excerpt": "...", "page_number": 1, "confidence": 0.9}
  - GRAPH JSON: {"nodes": [{"id": "...", "label": "...", "group": "..."}], "edges": [{"source": "...", "target": "...", "label": "..."}]}
- Unsupported claims MUST be explicitly labelled as assumptions using > [!ASSUMPTION].
- Evidence MUST always appear BELOW conclusions (max 3 docs).
- Every citation MUST include: Document name, Confidence, Score, and Click to preview document.
- End every response with exactly: "More details available."
""" + _EVIDENCE_FIRST_RULES

GRAPH_AWARE_SYSTEM_PROMPT = """You are a technical documentation assistant with access to both document excerpts and a knowledge graph of entities and relationships.

Rules:
- Default response length: 80–150 words. Optimize for readability, not completeness.
- Answer the user's question first.
- Show at most: Status, Answer, Recommended Actions (max 3), and Evidence (max 3 documents).
- NEVER generate: Root Cause Analysis, Risk Assessment, Maintenance Checklist, Timeline, or Executive Summary unless explicitly requested.
- Answer ONLY using the information in the retrieved context and graph knowledge.
- Do NOT make up, infer, or hallucinate any facts, figures, or details.
- If the context does not contain the answer, explicitly state: "The provided documents do not contain information about this."
- Use specialized cards for important information exactly as blockquotes with exact tags:
  > [!WARNING], > [!DOCUMENT], > [!ASSET], > [!GRAPH], > [!EVIDENCE]
- For > [!ASSET], > [!DOCUMENT], and > [!GRAPH], you MUST provide a raw JSON object as the content of the blockquote instead of text.
  - ASSET JSON: {"name": "...", "status": "...", "criticality": "...", "location": "...", "connected_assets": [], "connected_incidents": [], "maintenance_history": [{"date": "...", "description": "..."}], "graph_relationships": [{"type": "...", "target": "..."}]}
  - DOCUMENT JSON: {"document_name": "...", "chunk_content": "...", "highlighted_excerpt": "...", "page_number": 1, "confidence": 0.9}
  - GRAPH JSON: {"nodes": [{"id": "...", "label": "...", "group": "..."}], "edges": [{"source": "...", "target": "...", "label": "..."}]}
- Unsupported claims MUST be explicitly labelled as assumptions using > [!ASSUMPTION].
- Evidence MUST always appear BELOW conclusions (max 3 docs).
- Every citation MUST include: Document name, Confidence, Score, and Click to preview document.
- End every response with exactly: "More details available."
""" + _EVIDENCE_FIRST_RULES

# M35: token budget — approximate (chars / 4)
_MAX_USER_PROMPT_TOKENS = 6000
_MAX_CHARS = _MAX_USER_PROMPT_TOKENS * 4


@dataclass
class PromptResult:
    system_prompt: str
    user_prompt: str
    history: list[dict] | None = None


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


def _format_source(chunk: RetrievedChunk) -> str:
    source = chunk.document_name
    if chunk.page_number is not None:
        source += f" (page {chunk.page_number})"
    return source


class PromptBuilder:
    def build_prompt(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        system_prompt: str | None = None,
        history: list[dict] | None = None,
        graph_facts: list[GraphFact] | None = None,
        additional_system_context: str | None = None,
        max_tokens: int = _MAX_USER_PROMPT_TOKENS,
    ) -> PromptResult:
        use_graph = graph_facts is not None and len(graph_facts) > 0
        base_system = system_prompt or (GRAPH_AWARE_SYSTEM_PROMPT if use_graph else DEFAULT_SYSTEM_PROMPT)

        resolved_system = base_system
        if additional_system_context:
            resolved_system = base_system + "\n\n" + additional_system_context

        # M35: build chunk blocks with score-based ranking
        chunk_blocks: list[tuple[float, str, RetrievedChunk]] = []
        for chunk in chunks:
            block = (
                f"Source: {_format_source(chunk)}\n"
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

        # M35: measure overhead (everything that isn't a chunk)
        # NOTE: history is no longer embedded in the user prompt text;
        # it is returned separately via PromptResult.history and injected
        # as distinct message entries by the LLM provider.
        overhead = (
            "Retrieved Context:\n"
            "------------------\n"
            f"{graph_block}\n\n"
            "------------------\n"
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
                if remaining > 60 or (not selected_blocks and remaining > 0):
                    source_line = f"[{i}] Source: {_format_source(chunk)}"
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

        return PromptResult(
            system_prompt=resolved_system,
            user_prompt=user_prompt,
            history=history,
        )
