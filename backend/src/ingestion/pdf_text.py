"""Bounded PDF text/OCR diagnostics; extracted text is never verified data."""
from dataclasses import dataclass
from io import BytesIO
from pypdf import PdfReader

MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 500
DEFAULT_OCR_MAX_PAGES = 25


@dataclass(frozen=True)
class PdfExtractionResult:
    page_count: int
    extracted_characters: int
    text: str
    needs_ocr: bool
    ocr_attempted: bool
    ocr_available: bool
    ocr_pages_processed: int


def extract_pdf_text(
    data: bytes,
    max_characters: int = 2_000_000,
    max_pages: int = MAX_PDF_PAGES,
    enable_ocr: bool = False,
    max_ocr_pages: int = DEFAULT_OCR_MAX_PAGES,
) -> PdfExtractionResult:
    """Extract bounded text for diagnostics; every PDF still requires manual review."""
    if not data.startswith(b"%PDF-"):
        raise ValueError("File does not have a valid PDF signature")
    if len(data) > MAX_PDF_BYTES:
        raise ValueError("PDF exceeds the configured extraction size limit")
    if max_characters < 1:
        raise ValueError("max_characters must be positive")
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    if max_ocr_pages < 1:
        raise ValueError("max_ocr_pages must be positive")
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
        text = "\n".join(parts).strip()
        ocr_attempted = False
        ocr_available = False
        ocr_pages_processed = 0

        # OCR is used only when no embedded text was found. It never creates
        # verified records; its output is returned for transient diagnostics only.
        if not text and enable_ocr:
            ocr_attempted = True
            try:
                import pypdfium2 as pdfium
                import pytesseract

                ocr_available = True
                document = pdfium.PdfDocument(data)
                ocr_parts = []
                for index in range(min(page_count, max_ocr_pages)):
                    remaining = max_characters - sum(len(part) for part in ocr_parts)
                    if remaining <= 0:
                        break
                    page = document[index]
                    bitmap = page.render(scale=1.25)
                    image = bitmap.to_pil()
                    try:
                        extracted = pytesseract.image_to_string(image, timeout=12)
                    finally:
                        image.close()
                        bitmap.close()
                        page.close()
                    ocr_parts.append((extracted or "")[:remaining])
                    ocr_pages_processed += 1
                document.close()
                text = "\n".join(ocr_parts).strip()
            except Exception:
                # Missing Tesseract, timeout, or malformed page: retain the PDF
                # for manual review without leaking OCR engine details to users.
                ocr_available = False
                text = ""
        return PdfExtractionResult(
            page_count=page_count,
            extracted_characters=len(text),
            text=text[:max_characters],
            needs_ocr=(not text or (ocr_attempted and page_count > ocr_pages_processed)),
            ocr_attempted=ocr_attempted,
            ocr_available=ocr_available,
            ocr_pages_processed=ocr_pages_processed,
        )
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PDF could not be parsed safely") from exc
