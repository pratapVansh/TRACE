from io import BytesIO

import pytest
from openpyxl import Workbook

from app.services.document_processing_exceptions import XlsxTextExtractionError
from app.services.xlsx_text_extraction import extract_xlsx_text


def _build_xlsx() -> bytes:
    workbook = Workbook()
    assets = workbook.active
    assets.title = "Assets"
    assets.append(["Tag", "Value"])
    assets.append(["P-101", "120 psi"])

    logs = workbook.create_sheet("Logs")
    logs.append(["Event", "Status"])
    logs.append(["Inspection", "Complete"])

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_extract_xlsx_text_reads_worksheet_names_and_cells() -> None:
    result = extract_xlsx_text(_build_xlsx())

    assert result.worksheet_count == 2
    assert result.worksheets[0].name == "Assets"
    assert result.worksheets[1].name == "Logs"
    assert "P-101" in result.worksheets[0].text
    assert "Inspection" in result.worksheets[1].text
    assert "[Assets]" in result.full_text
    assert "[Logs]" in result.full_text


def test_extract_xlsx_text_formats_rows_as_readable_text() -> None:
    result = extract_xlsx_text(_build_xlsx())

    assert "Tag | Value" in result.worksheets[0].text
    assert "P-101 | 120 psi" in result.worksheets[0].text


def test_extract_xlsx_text_rejects_empty_bytes() -> None:
    with pytest.raises(XlsxTextExtractionError, match="empty"):
        extract_xlsx_text(b"")


def test_extract_xlsx_text_rejects_invalid_bytes() -> None:
    with pytest.raises(XlsxTextExtractionError, match="Failed to open XLSX"):
        extract_xlsx_text(b"not-an-xlsx")
