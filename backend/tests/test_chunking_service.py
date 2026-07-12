"""Unit tests for chunking_service pure functions and ChunkingService."""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.services.chunking_service import (
    ChunkingService,
    _build_page_map,
    _count_tokens,
    _extract_heading_positions,
    _find_page_number,
    _find_section_title,
    _looks_like_heading,
    _merge_tiny_chunks,
)


class TestChunkingPureFunctions:
    def test_count_tokens_empty(self) -> None:
        assert _count_tokens("") == 0

    def test_count_tokens_short_text(self) -> None:
        assert _count_tokens("Hello world") > 0

    def test_looks_like_heading_atx_markdown(self) -> None:
        assert _looks_like_heading("# Introduction") is True
        assert _looks_like_heading("## Sub Section") is True
        assert _looks_like_heading("### Deep Dive") is True

    def test_looks_like_heading_numbered(self) -> None:
        assert _looks_like_heading("1. Introduction") is True
        assert _looks_like_heading("1.1 Requirements") is True
        assert _looks_like_heading("2.0 Overview") is True

    def test_looks_like_heading_roman_numeral(self) -> None:
        assert _looks_like_heading("I. Overview") is True
        assert _looks_like_heading("II. Background") is True

    def test_looks_like_heading_section_keyword(self) -> None:
        assert _looks_like_heading("Section 1: Scope") is True
        assert _looks_like_heading("Chapter 2: Review") is True
        assert _looks_like_heading("Appendix A: References") is True

    def test_looks_like_heading_uppercase(self) -> None:
        assert _looks_like_heading("IMPORTANT NOTES") is True
        assert _looks_like_heading("EXECUTIVE SUMMARY") is True

    def test_looks_like_heading_not_heading(self) -> None:
        assert _looks_like_heading("This is a normal sentence.") is False
        assert _looks_like_heading("") is False
        assert _looks_like_heading("a") is False

    def test_looks_like_heading_too_long(self) -> None:
        long_text = "A" * 201
        assert _looks_like_heading(long_text) is False

    def test_extract_heading_positions_empty(self) -> None:
        assert _extract_heading_positions("") == []

    def test_extract_heading_positions_no_headings(self) -> None:
        assert _extract_heading_positions("Plain text without headings.") == []

    def test_extract_heading_positions_multiple(self) -> None:
        text = "# Intro\nsome text\n## Details\nmore text"
        result = _extract_heading_positions(text)
        assert len(result) == 2
        assert result[0] == (0, "# Intro")
        assert result[1] == (18, "## Details")

    def test_build_page_map_empty(self) -> None:
        assert _build_page_map([]) == []

    def test_find_page_number_within_range(self) -> None:
        page_map = [{"start": 0, "end": 10, "page_number": 1}]
        assert _find_page_number(page_map, 0) == 1
        assert _find_page_number(page_map, 9) == 1

    def test_find_page_number_out_of_range(self) -> None:
        page_map = [{"start": 0, "end": 10, "page_number": 1}]
        # past-end returns last page
        assert _find_page_number(page_map, 10) == 1

    def test_find_page_number_past_last_page(self) -> None:
        page_map = [{"start": 0, "end": 10, "page_number": 1}]
        assert _find_page_number(page_map, 15) == 1

    def test_find_page_number_empty_map(self) -> None:
        assert _find_page_number([], 0) is None

    def test_find_section_title_none_before(self) -> None:
        headings = [(10, "# Intro")]
        assert _find_section_title(headings, 5) is None

    def test_find_section_title_exact_match(self) -> None:
        headings = [(10, "# Intro"), (20, "## Details")]
        assert _find_section_title(headings, 10) == "# Intro"
        assert _find_section_title(headings, 15) == "# Intro"
        assert _find_section_title(headings, 20) == "## Details"

    def test_find_section_title_empty(self) -> None:
        assert _find_section_title([], 100) is None


class TestMergeTinyChunks:
    def test_merge_none_below_minimum(self) -> None:
        chunks = [
            {"chunk_index": 0, "content": "A" * 200, "token_count": 100},
            {"chunk_index": 1, "content": "B" * 200, "token_count": 100},
        ]
        result = _merge_tiny_chunks(chunks)
        assert len(result) == 2

    def test_merge_tiny_into_previous(self) -> None:
        chunks = [
            {"chunk_index": 0, "content": "A" * 200, "token_count": 100},
            {"chunk_index": 1, "content": "tiny", "token_count": 5},
        ]
        result = _merge_tiny_chunks(chunks)
        assert len(result) == 1

    def test_merge_first_chunk_if_tiny(self) -> None:
        chunks = [
            {"chunk_index": 0, "content": "tiny", "token_count": 5},
            {"chunk_index": 1, "content": "B" * 200, "token_count": 100},
        ]
        result = _merge_tiny_chunks(chunks)
        assert len(result) == 1
        assert "tiny" in result[0]["content"]
        assert "B" in result[0]["content"]

    def test_merge_empty_list(self) -> None:
        assert _merge_tiny_chunks([]) == []

    def test_merge_single_chunk_tiny(self) -> None:
        chunks = [{"chunk_index": 0, "content": "tiny", "token_count": 5}]
        result = _merge_tiny_chunks(chunks)
        assert len(result) == 1


@pytest.fixture
def mock_repository() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def service(
    mock_session: AsyncMock,
    mock_repository: AsyncMock,
) -> ChunkingService:
    return ChunkingService(session=mock_session, chunk_repository=mock_repository)


@pytest.mark.asyncio
async def test_chunk_document_empty_text(
    service: ChunkingService,
    mock_repository: AsyncMock,
) -> None:
    doc_id = uuid.uuid4()
    result = await service.chunk_document(doc_id, text="", filename="test.txt")
    assert result == []
    mock_repository.create_chunks_bulk.assert_not_called()


@pytest.mark.asyncio
async def test_chunk_document_whitespace_only(
    service: ChunkingService,
    mock_repository: AsyncMock,
) -> None:
    doc_id = uuid.uuid4()
    result = await service.chunk_document(doc_id, text="   \n   \n  ", filename="test.txt")
    assert result == []
    mock_repository.create_chunks_bulk.assert_not_called()


@pytest.mark.asyncio
async def test_chunk_document_creates_chunks(
    service: ChunkingService,
    mock_repository: AsyncMock,
) -> None:
    doc_id = uuid.uuid4()
    mock_repository.create_chunks_bulk.return_value = [
        AsyncMock(chunk_index=0),
        AsyncMock(chunk_index=1),
    ]

    result = await service.chunk_document(
        doc_id,
        text="Hello world. " * 500,
        filename="test.txt",
        language="en",
    )

    assert len(result) == 2
    mock_repository.create_chunks_bulk.assert_awaited_once()

    saved_chunks = mock_repository.create_chunks_bulk.await_args[0][0]
    for chunk in saved_chunks:
        metadata = chunk["extra_metadata"]
        assert metadata["document_id"] == str(doc_id)
        assert metadata["filename"] == "test.txt"
        assert metadata["language"] == "en"
        assert "total_chunks" in metadata
        assert metadata["total_chunks"] == len(saved_chunks)
        assert "processing_timestamp" in metadata


def test_build_page_map_and_find_page() -> None:
    pages = [
        {"text": "Page one content.", "page_number": 1},
        {"text": "Page two content.", "page_number": 2},
    ]
    page_map = _build_page_map(pages)
    assert len(page_map) == 2
    assert _find_page_number(page_map, 0) == 1
    # second page starts after "Page one content." + separator
    assert _find_page_number(page_map, page_map[1]["start"]) == 2

    # past the end of last page
    assert _find_page_number(page_map, 100) == 2


def test_build_page_map_skips_empty() -> None:
    pages = [
        {"text": "", "page_number": 1},
        {"text": "Real content", "page_number": 2},
    ]
    page_map = _build_page_map(pages)
    assert len(page_map) == 1
    assert page_map[0]["page_number"] == 2
