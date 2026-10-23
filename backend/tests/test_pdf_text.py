from io import BytesIO

import pytest
from pypdf import PdfWriter

from src.ingestion.pdf_text import extract_pdf_text


def blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_rejects_non_pdf_bytes():
    with pytest.raises(ValueError, match="PDF signature"):
        extract_pdf_text(b"not a pdf")


def test_blank_pdf_requires_ocr_and_manual_review_signal():
    result = extract_pdf_text(blank_pdf())
    assert result.page_count == 1
    assert result.extracted_characters == 0
    assert result.needs_ocr is True
    assert result.ocr_attempted is False
    assert result.ocr_pages_processed == 0


def test_character_limit_must_be_positive():
    with pytest.raises(ValueError, match="positive"):
        extract_pdf_text(blank_pdf(), max_characters=0)

def test_page_limit_must_be_positive():
    with pytest.raises(ValueError, match="max_pages must be positive"):
        extract_pdf_text(blank_pdf(), max_pages=0)


def test_pdf_size_limit_is_enforced_before_parsing():
    from src.ingestion.pdf_text import MAX_PDF_BYTES

    with pytest.raises(ValueError, match="size limit"):
        extract_pdf_text(b"%PDF-" + b"x" * MAX_PDF_BYTES)

def test_ocr_is_opt_in():
    result = extract_pdf_text(blank_pdf(), enable_ocr=False)
    assert result.ocr_attempted is False
    assert result.needs_ocr is True


def test_ocr_page_limit_must_be_positive():
    with pytest.raises(ValueError, match="max_ocr_pages must be positive"):
        extract_pdf_text(blank_pdf(), max_ocr_pages=0)
