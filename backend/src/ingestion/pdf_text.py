"""Bounded PDF text diagnostics; extracted text is never treated as verified data."""
from dataclasses import dataclass
from io import BytesIO
from pypdf import PdfReader

MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 500


@dataclass(frozen=True)
class PdfExtractionResult:
    page_count: int
    extracted_characters: int
    text: str
    needs_ocr: bool


def extract_pdf_text(
    data: bytes,
    max_characters: int = 2_000_000,
    max_pages: int = MAX_PDF_PAGES,
) -> PdfExtractionResult:
    """Extract bounded searchable text; callers must route the result to review."""
    if not data.startswith(b"%PDF-"):
        raise ValueError("File does not have a valid PDF signature")
    if len(data) > MAX_PDF_BYTES:
        raise ValueError("PDF exceeds the configured extraction size limit")
    if max_characters < 1:
        raise ValueError("max_characters must be positive")
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported for automatic extraction")
        page_count = len(reader.pages)
        if page_count > max_pages:
            raise ValueError(f"PDF exceeds the configured page limit of {max_pages}")
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
            page_count=page_count,
            extracted_characters=len(text),
            text=text,
            needs_ocr=not text.strip(),
        )
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PDF could not be parsed safely") from exc
