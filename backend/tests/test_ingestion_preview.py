import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from openpyxl import Workbook

from src.api import preview_upload


def test_csv_preview_is_non_persistent_and_returns_sample_rows():
    upload = UploadFile(filename="fixture.csv", file=BytesIO(b"legal_name,registration_number\nExample Ltd,CPR-1\n"))
    result = asyncio.run(preview_upload(upload))
    assert result["persisted"] is False
    assert result["columns"] == ["legal_name", "registration_number"]
    assert result["sample_rows"][0]["values"]["legal_name"] == "Example Ltd"
    assert result["message"].startswith("Preview only")


def test_xlsx_preview_returns_first_sheet_sample():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["legal_name", "registration_number"])
    sheet.append(["Example Ltd", "CPR-1"])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    upload = UploadFile(filename="fixture.xlsx", file=BytesIO(buffer.getvalue()))
    result = asyncio.run(preview_upload(upload))
    assert result["file_type"] == "xlsx"
    assert result["columns"] == ["legal_name", "registration_number"]
    assert result["sample_count"] == 1
    assert result["persisted"] is False


def test_preview_rejects_unsupported_pdf():
    upload = UploadFile(filename="document.pdf", file=BytesIO(b"%PDF-1.7"))
    with pytest.raises(HTTPException) as error:
        asyncio.run(preview_upload(upload))
    assert error.value.status_code == 415
