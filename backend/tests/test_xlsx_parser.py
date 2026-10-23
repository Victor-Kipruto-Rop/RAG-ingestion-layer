from io import BytesIO

import pytest
from openpyxl import Workbook

from src.ingestion.parser_xlsx import iter_xlsx_records


def make_xlsx(rows):
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_xlsx_parser_reads_first_sheet_and_preserves_row_numbers():
    data = make_xlsx([
        ["legal_name", "registration_number"],
        ["Example Limited", "CPR-001"],
        [None, None],
        ["Sample Traders", "CPR-002"],
    ])
    records = list(iter_xlsx_records(data, max_records=10))
    assert records == [
        (2, {"legal_name": "Example Limited", "registration_number": "CPR-001"}),
        (4, {"legal_name": "Sample Traders", "registration_number": "CPR-002"}),
    ]


def test_xlsx_parser_disambiguates_duplicate_headers():
    data = make_xlsx([["name", "name"], ["First", "Second"]])
    records = list(iter_xlsx_records(data, max_records=10))
    assert records == [(2, {"name": "First", "name_2": "Second"})]


def test_xlsx_parser_rejects_non_workbook_bytes():
    with pytest.raises(ValueError, match="malformed|valid XLSX"):
        list(iter_xlsx_records(b"not a workbook", max_records=10))


def test_xlsx_parser_enforces_record_limit():
    data = make_xlsx([["name"], ["First"], ["Second"]])
    with pytest.raises(ValueError, match="exceeds configured limit"):
        list(iter_xlsx_records(data, max_records=1))
