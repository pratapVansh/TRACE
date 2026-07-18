"""Chunking service — splits document text into structured chunks.
    
Preserves code blocks, tables, and lists as atomic units.
Splits at headings and section breaks; uses RecursiveCharacterTextSplitter
only as fallback within large paragraph regions.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import tiktoken
from langchain_core.documents import Document as LangChainDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.document_chunk import DocumentChunk
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.schemas.document_chunks import DocumentChunkCreate

_ENCODING = None


def _get_tokenizer() -> tiktoken.Encoding:
    global _ENCODING
    if _ENCODING is None:
        _ENCODING = tiktoken.get_encoding("cl100k_base")
    return _ENCODING


def _count_tokens(text: str) -> int:
    return len(_get_tokenizer().encode(text))


_HEADING_RE = re.compile(
    r"^("
    r"#{1,6}\s+.+"                          # Markdown ATX headings
    r"|[\d]+(?:\.\d+)*[\.\)]?\s+.+"         # Numbered "1. Title", "1.1 Title"
    r"|[IVXLCDM]+[\.\)]\s+.+"               # Roman numeral "I. Title"
    r"|(?:Section|Chapter|Part|Appendix)\s+[\dIVXLCDMA]+[\s:].+"  # "Section 1: Title", "Appendix A: Title"
    r")",
    re.IGNORECASE | re.MULTILINE,
)


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 200:
        return False
    if stripped.endswith((".", "!", "?", ";", ":")):
        return False
    if _HEADING_RE.match(stripped):
        return True
    if stripped.isupper() and len(stripped) > 3:
        return True
    return False


def _extract_heading_positions(text: str) -> list[tuple[int, str]]:
    """Return list of (char_offset, heading_text) for all detected headings."""
    headings: list[tuple[int, str]] = []
    lines = text.split("\n")
    offset = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if _looks_like_heading(stripped):
            headings.append((offset, stripped))
        elif (i + 1 < len(lines)
              and re.match(r"^[=\-]+\s*$", lines[i + 1])
              and stripped):
            headings.append((offset, stripped))
        offset += len(line) + 1
    return headings


def _build_page_map(pages: list[dict]) -> list[dict]:
    """Build char-offset → page_number mapping from a pages list.

    Expects each entry to have *text* and optionally *page_number*.
    Pages are assumed joined with ``"\\n\\n"`` to form the full text.
    """
    page_map: list[dict] = []
    offset = 0
    for entry in pages:
        text = entry.get("text", "")
        if not text:
            continue
        page_number = entry.get("page_number")
        page_map.append({
            "start": offset,
            "end": offset + len(text),
            "page_number": page_number,
        })
        offset += len(text) + 2
    return page_map


def _find_page_number(page_map: list[dict], char_offset: int) -> int | None:
    for entry in page_map:
        if entry["start"] <= char_offset < entry["end"]:
            return entry["page_number"]
    if page_map:
        last = page_map[-1]
        if char_offset >= last["end"]:
            return last["page_number"]
    return None


def _find_section_title(
    heading_positions: list[tuple[int, str]],
    char_offset: int,
) -> str | None:
    title: str | None = None
    for pos, heading in heading_positions:
        if pos <= char_offset:
            title = heading
        else:
            break
    return title


# --- Semantic region parsing ---

_CODE_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")
_TABLE_ROW_RE = re.compile(r"^\|.+\|$")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s|[-*+]\[[ x]\]\s|\d+[\.\)]\s)")
_SECTION_BREAK_RE = re.compile(r"^(-{3,}|\*{3,}|_{3,})\s*$")


@dataclass(slots=True)
class _SemanticRegion:
    type: str
    content: str
    start_offset: int


def _parse_semantic_regions(text: str) -> list[_SemanticRegion]:
    """Parse text into ordered semantic regions preserving structural elements."""
    regions: list[_SemanticRegion] = []
    lines = text.split("\n")
    i = 0
    offset = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            offset += len(line) + 1
            i += 1
            continue

        if _SECTION_BREAK_RE.match(stripped):
            regions.append(_SemanticRegion("section_break", stripped, offset))
            offset += len(line) + 1
            i += 1
            continue

        code_match = _CODE_FENCE_RE.match(stripped)
        if code_match:
            fence_char = code_match.group(1)[0]
            fence_len = len(code_match.group(1))
            start = offset
            code_lines = [line]
            offset += len(line) + 1
            i += 1
            while i < len(lines):
                code_lines.append(lines[i])
                offset += len(lines[i]) + 1
                if _CODE_FENCE_RE.match(lines[i].strip()):
                    closing = lines[i].strip()
                    if closing[0] == fence_char and len(closing) >= fence_len:
                        i += 1
                        break
                i += 1
            regions.append(_SemanticRegion("code", "\n".join(code_lines), start))
            continue

        if _TABLE_ROW_RE.match(stripped):
            start = offset
            table_lines = [line]
            offset += len(line) + 1
            i += 1
            while i < len(lines) and _TABLE_ROW_RE.match(lines[i].strip()):
                table_lines.append(lines[i])
                offset += len(lines[i]) + 1
                i += 1
            regions.append(_SemanticRegion("table", "\n".join(table_lines), start))
            continue

        if _LIST_ITEM_RE.match(stripped):
            start = offset
            list_lines = [line]
            offset += len(line) + 1
            i += 1
            while i < len(lines):
                next_s = lines[i].strip()
                if not next_s:
                    break
                if _LIST_ITEM_RE.match(next_s):
                    list_lines.append(lines[i])
                    offset += len(lines[i]) + 1
                    i += 1
                    continue
                break
            regions.append(_SemanticRegion("list", "\n".join(list_lines), start))
            continue

        if _looks_like_heading(stripped):
            regions.append(_SemanticRegion("heading", stripped, offset))
            offset += len(line) + 1
            i += 1
            continue

        start = offset
        para_lines = [line]
        offset += len(line) + 1
        i += 1
        while i < len(lines):
            next_s = lines[i].strip()
            if not next_s:
                offset += len(lines[i]) + 1
                i += 1
                break
            if (_looks_like_heading(next_s)
                    or _CODE_FENCE_RE.match(next_s)
                    or _TABLE_ROW_RE.match(next_s)
                    or _LIST_ITEM_RE.match(next_s)
                    or _SECTION_BREAK_RE.match(next_s)):
                break
            para_lines.append(lines[i])
            offset += len(lines[i]) + 1
            i += 1
        regions.append(_SemanticRegion("paragraph", "\n".join(para_lines), start))

    return regions


def _split_paragraph_region(
    region: _SemanticRegion,
    chunk_size: int,
    chunk_overlap: int,
) -> list[_SemanticRegion]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=_count_tokens,
        separators=["\n\n\n", "\n\n", "\n", " ", ""],
        add_start_index=True,
    )
    source = LangChainDocument(page_content=region.content)
    split_docs = splitter.split_documents([source])
    return [
        _SemanticRegion(
            type="paragraph",
            content=doc.page_content,
            start_offset=region.start_offset + doc.metadata.get("start_index", 0),
        )
        for doc in split_docs
        if doc.page_content.strip()
    ]


def _chunk_regions(
    regions: list[_SemanticRegion],
    chunk_size: int,
    chunk_overlap: int,
    page_map: list[dict],
    heading_positions: list[tuple[int, str]],
) -> list[dict]:
    """Group semantic regions into document chunks."""
    current_regions: list[_SemanticRegion] = []
    current_tokens = 0
    chunks: list[dict] = []

    def _make_chunk(regions_or_region: list[_SemanticRegion] | _SemanticRegion) -> dict:
        if isinstance(regions_or_region, list):
            content = "\n\n".join(r.content for r in regions_or_region)
            start_offset = regions_or_region[0].start_offset
        else:
            content = regions_or_region.content
            start_offset = regions_or_region.start_offset
        return {
            "chunk_index": 0,
            "page_number": _find_page_number(page_map, start_offset),
            "section_title": _find_section_title(heading_positions, start_offset),
            "content": content,
            "token_count": _count_tokens(content),
            "extra_metadata": {},
            "embedding_status": "pending",
        }

    def _flush() -> dict | None:
        nonlocal current_regions, current_tokens
        if not current_regions:
            return None
        chunk = _make_chunk(current_regions)
        current_regions = []
        current_tokens = 0
        return chunk

    for region in regions:
        rt = _count_tokens(region.content)

        if region.type == "section_break":
            chunk = _flush()
            if chunk:
                chunks.append(chunk)
            continue

        if region.type == "heading":
            chunk = _flush()
            if chunk:
                chunks.append(chunk)
            current_regions.append(region)
            current_tokens = rt
            continue

        if current_tokens + rt <= chunk_size:
            current_regions.append(region)
            current_tokens += rt
        elif not current_regions:
            if region.type == "paragraph":
                for sub in _split_paragraph_region(region, chunk_size, chunk_overlap):
                    chunks.append(_make_chunk(sub))
            else:
                chunks.append(_make_chunk(region))
        else:
            chunk = _flush()
            if chunk:
                chunks.append(chunk)
            current_regions.append(region)
            current_tokens = rt

    chunk = _flush()
    if chunk:
        chunks.append(chunk)

    return chunks


class ChunkingService:
    def __init__(
        self,
        session: AsyncSession,
        chunk_repository: DocumentChunkRepository,
    ) -> None:
        self._session = session
        self._chunk_repository = chunk_repository

    async def create_chunk(self, data: DocumentChunkCreate) -> DocumentChunk:
        return await self._chunk_repository.create_chunk(
            document_id=data.document_id,
            chunk_index=data.chunk_index,
            content=data.content,
            page_number=data.page_number,
            section_title=data.section_title,
            extra_metadata=data.metadata,
            token_count=data.token_count,
        )

    async def create_chunks_bulk(
        self,
        chunks: list[DocumentChunkCreate],
    ) -> list[DocumentChunk]:
        return await self._chunk_repository.create_chunks_bulk(
            [c.model_dump() for c in chunks],
        )

    async def get_chunks_by_document(
        self,
        document_id: UUID,
        embedding_status: str | None = None,
    ) -> Sequence[DocumentChunk]:
        return await self._chunk_repository.get_chunks_by_document(
            document_id,
            embedding_status=embedding_status,
        )

    async def delete_document_chunks(self, document_id: UUID) -> None:
        await self._chunk_repository.delete_document_chunks(document_id)

    async def chunk_document(
        self,
        document_id: UUID,
        *,
        text: str,
        pages: list[dict] | None = None,
        filename: str | None = None,
        language: str | None = None,
    ) -> Sequence[DocumentChunk]:
        """Chunk full document text and persist the resulting chunks.

        Each chunk's metadata includes document_id, filename, language,
        total_chunks, and processing_timestamp.
        """
        raw = self._chunk_text(text, pages=pages)
        if not raw:
            return []

        total = len(raw)
        now = datetime.now(UTC)

        for entry in raw:
            entry["document_id"] = document_id
            entry["extra_metadata"].update({
                "document_id": str(document_id),
                "filename": filename,
                "language": language,
                "total_chunks": total,
                "processing_timestamp": now.isoformat(),
            })

        saved = await self._chunk_repository.create_chunks_bulk(raw)

        logger.info(
            "Chunked document document_id=%s chunks=%d",
            document_id,
            total,
        )
        return saved

    def _chunk_text(
        self,
        text: str,
        *,
        pages: list[dict] | None = None,
    ) -> list[dict]:
        """Pure chunking logic — returns list of chunk dicts ready for persistence.

        Uses semantic chunking: preserves code blocks, tables, lists as atomic units,
        splits at headings and section breaks, and uses RecursiveCharacterTextSplitter
        only as fallback within large paragraph regions.
        """
        if not text or not text.strip():
            return []

        page_map = _build_page_map(pages) if pages else []
        heading_positions = _extract_heading_positions(text)
        regions = _parse_semantic_regions(text)

        if not regions:
            return []

        chunks = _chunk_regions(
            regions,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            page_map=page_map,
            heading_positions=heading_positions,
        )

        chunks = self._merge_tiny_chunks(chunks)

        for i, entry in enumerate(chunks):
            entry["chunk_index"] = i
            entry.pop("_merged", None)

        return chunks

    @staticmethod
    def _merge_tiny_chunks(chunks: list[dict]) -> list[dict]:
        return _merge_tiny_chunks(chunks)


def _merge_tiny_chunks(chunks: list[dict]) -> list[dict]:
    """Merge chunks below *chunk_min_size* into a neighbouring chunk."""
    if not chunks:
        return chunks

    min_size = settings.chunk_min_size

    merged: list[dict] = [chunks[0]]
    for chunk in chunks[1:]:
        if chunk["token_count"] < min_size and merged:
            prev = merged[-1]
            prev["content"] = prev["content"] + "\n" + chunk["content"]
            prev["token_count"] = _count_tokens(prev["content"])
            prev["_merged"] = True
        else:
            merged.append(chunk)

    if len(merged) > 1 and merged[0]["token_count"] < min_size:
        second = merged[1]
        merged[0]["content"] = merged[0]["content"] + "\n" + second["content"]
        merged[0]["token_count"] = _count_tokens(merged[0]["content"])
        merged[0]["_merged"] = True
        merged.pop(1)

    return merged
