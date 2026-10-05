from app.schemas.rag import Citation
from app.services.evidence_classification import enforce_grounded_answer


def _citation(content: str, name: str = "resume.pdf") -> Citation:
    return Citation(
        chunk_id="chunk-1",
        document_id="doc-1",
        document_name=name,
        chunk_content=content,
        score=0.9,
        similarity_score=0.9,
        highlighted_excerpt=content,
    )


def test_grounding_guard_removes_unsupported_recommendation() -> None:
    answer = (
        "The candidate built the TRACE retrieval platform with FastAPI and Qdrant.\n"
        "They should obtain an AWS certification next."
    )
    guarded, citations, removed = enforce_grounded_answer(
        answer,
        [_citation("Built the TRACE retrieval platform with FastAPI and Qdrant.")],
    )

    assert "TRACE retrieval platform" in guarded
    assert "AWS certification" not in guarded
    assert removed == 1
    assert len(citations) == 1


def test_grounding_guard_filters_unreferenced_citations() -> None:
    guarded, citations, _ = enforce_grounded_answer(
        "The candidate studied computer science at Example University.",
        [
            _citation("Studied computer science at Example University.", "resume.pdf"),
            _citation("Pump P-101 requires lubrication.", "manual.pdf"),
        ],
    )

    assert "computer science" in guarded
    assert [citation.document_name for citation in citations] == ["resume.pdf"]
