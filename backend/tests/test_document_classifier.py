from app.services.document_classifier import classify_document


def test_resume_filename_sets_semantic_type_independent_of_pdf_format() -> None:
    result = classify_document("Vansh_Resume.pdf")

    assert result.document_type == "resume"
    assert result.category == "Resume"


def test_resume_content_sets_semantic_type_for_generic_filename() -> None:
    result = classify_document(
        "profile.pdf",
        "Education\nB.Tech Computer Science\nProjects\nTRACE RAG\nExperience\nEngineer",
    )

    assert result.document_type == "resume"
    assert result.category == "Resume"


def test_file_format_does_not_force_pdf_to_manual() -> None:
    result = classify_document("misc.pdf")

    assert result.document_type == "document"
