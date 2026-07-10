from dataclasses import dataclass
from io import BytesIO

from docx import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.services.document_processing_exceptions import DocxTextExtractionError

EXTRACTION_METHOD = "python-docx"


@dataclass(frozen=True, slots=True)
class ExtractedBlock:
    block_index: int
    block_type: str
    text: str
    level: int | None = None


@dataclass(frozen=True, slots=True)
class DocxTextExtractionResult:
    blocks: tuple[ExtractedBlock, ...]
    full_text: str
    block_count: int


def extract_docx_text(content: bytes) -> DocxTextExtractionResult:
    """Extract headings, paragraphs, and tables from a DOCX file."""
    if not content:
        raise DocxTextExtractionError("DOCX file is empty")

    try:
        document = DocxDocument(BytesIO(content))
    except Exception as exc:
        raise DocxTextExtractionError("Failed to open DOCX for text extraction") from exc

    blocks: list[ExtractedBlock] = []
    block_index = 0

    for item in _iter_block_items(document):
        if isinstance(item, Paragraph):
            text = item.text.strip()
            if not text:
                continue

            block_index += 1
            block_type, level = _classify_paragraph(item, text)
            blocks.append(
                ExtractedBlock(
                    block_index=block_index,
                    block_type=block_type,
                    text=text,
                    level=level,
                ),
            )
            continue

        table_text = _extract_table_text(item)
        if not table_text:
            continue

        block_index += 1
        blocks.append(
            ExtractedBlock(
                block_index=block_index,
                block_type="table",
                text=table_text,
            ),
        )

    full_text = "\n\n".join(block.text for block in blocks)
    return DocxTextExtractionResult(
        blocks=tuple(blocks),
        full_text=full_text,
        block_count=len(blocks),
    )


def _iter_block_items(document: DocxDocument):
    parent = document.element.body
    for child in parent.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _classify_paragraph(paragraph: Paragraph, text: str) -> tuple[str, int | None]:
    style_name = paragraph.style.name if paragraph.style is not None else ""
    if style_name.startswith("Heading"):
        level_text = style_name.replace("Heading", "").strip()
        if level_text.isdigit():
            return "heading", int(level_text)
        if style_name == "Heading":
            return "heading", 1
    if paragraph.style and paragraph.style.name == "Title":
        return "heading", 1
    return "paragraph", None


def _extract_table_text(table: Table) -> str:
    rows: list[str] = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)
