"""Safe PDF text extraction diagnostics; never treats extracted text as verified data."""
from dataclasses import dataclass
from io import BytesIO
from pypdf import PdfReader


@dataclass(frozen=True)
class PdfExtractionResult:
    page_count: int
    extracted_characters: int
    text: str
    needs_ocr: bool


def extract_pdf_text(data: bytes, max_characters: int = 2_000_000) -> PdfExtractionResult:
    """Extract bounded searchable text; callers must route the result to review."""
    if not data.startswith(b"%PDF-"):
        raise ValueError("File does not have a valid PDF signature")
    if max_characters < 1:
        raise ValueError("max_characters must be positive")
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported for automatic extraction")
        parts = []
        count = 0
        for page in reader.pages:
            remaining = max_characters - count
            if remaining <= 0:
                break
            extracted = page.extract_text() or ""
            piece = extracted[:remaining]
            parts.append(piece)
            count += len(piece)
        text = "\n".join(parts)
        return PdfExtractionResult(
            page_count=len(reader.pages),
            extracted_characters=len(text),
            text=text,
            needs_ocr=not text.strip(),
        )
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PDF could not be parsed safely") from exc
