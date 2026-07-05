import pytest

from app.services.document_exceptions import (
    EmptyFileError,
    FileTooLargeError,
    UnsupportedFileTypeError,
)
from app.services.document_service import DocumentService


@pytest.fixture
def service() -> DocumentService:
    return DocumentService(session=None, document_repository=None, storage=None)


def test_validate_upload_rejects_empty_file(service: DocumentService) -> None:
    with pytest.raises(EmptyFileError):
        service._validate_upload("empty.txt", b"")


def test_validate_upload_rejects_unsupported_extension(service: DocumentService) -> None:
    with pytest.raises(UnsupportedFileTypeError):
        service._validate_upload("malware.exe", b"bad")


def test_validate_upload_rejects_pdf_with_invalid_content(service: DocumentService) -> None:
    with pytest.raises(UnsupportedFileTypeError):
        service._validate_upload("report.pdf", b"not-a-pdf")


def test_validate_upload_accepts_valid_pdf(service: DocumentService) -> None:
    extension, mime_type = service._validate_upload("report.pdf", b"%PDF-1.4 test")
    assert extension == "pdf"
    assert mime_type == "application/pdf"


def test_validate_upload_accepts_valid_txt(service: DocumentService) -> None:
    extension, mime_type = service._validate_upload("notes.txt", b"hello")
    assert extension == "txt"
    assert mime_type == "text/plain"


def test_apply_metadata_updates_source_and_department(service: DocumentService) -> None:
    updated = service._apply_metadata_updates(
        {"source": "legacy"},
        {"source": "inspection", "department": "Engineering"},
    )
    assert updated["source"] == "inspection"
    assert updated["department"] == "Engineering"


def test_apply_metadata_updates_can_clear_values(service: DocumentService) -> None:
    updated = service._apply_metadata_updates(
        {"source": "legacy", "department": "Engineering"},
        {"source": "", "department": ""},
    )
    assert "source" not in updated
    assert "department" not in updated
