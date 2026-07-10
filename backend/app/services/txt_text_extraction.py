from dataclasses import dataclass

from app.services.document_processing_exceptions import TextExtractionError

EXTRACTION_METHOD = "plain_text"


@dataclass(frozen=True, slots=True)
class TxtTextExtractionResult:
    full_text: str
    char_count: int


def extract_txt_text(content: bytes) -> TxtTextExtractionResult:
    if not content:
        raise TextExtractionError("TXT file is empty")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except Exception as exc:
            raise TextExtractionError("Failed to decode TXT file as UTF-8 or Latin-1") from exc

    stripped = text.strip()
    return TxtTextExtractionResult(
        full_text=stripped,
        char_count=len(stripped),
    )
