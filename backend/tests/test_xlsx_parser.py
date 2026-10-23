from io import BytesIO

import pytest
from openpyxl import Workbook

from src.ingestion.parser_xlsx import iter_xlsx_records, iter_xlsx_file


def make_xlsx(rows):
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_xlsx_parser_yields_header_mapped_records_and_row_numbers():
    data = make_xlsx([
        ["Legal name", "Registration number", "Tax PIN"],
        ["Example Ltd", "CPR-123", "A123456789Z"],
        ["Second Co", "CPR-456", None],
    ])
    assert list(iter_xlsx_records(data, 10)) == [
        (2, {"Legal name": "Example Ltd", "Registration number": "CPR-123", "Tax PIN": "A123456789Z"}),
        (3, {"Legal name": "Second Co", "Registration number": "CPR-456", "Tax PIN": ""}),
    ]


def test_xlsx_parser_makes_duplicate_headers_unique():
    data = make_xlsx([["Name", "Name"], ["First", "Second"]])
    assert list(iter_xlsx_records(data, 10)) == [(2, {"Name": "First", "Name_2": "Second"})]


def test_xlsx_parser_rejects_missing_header_and_row_limit():
    with pytest.raises(ValueError, match="usable header"):
        list(iter_xlsx_records(make_xlsx([[None, None], ["data", "data"]]), 10))
    with pytest.raises(ValueError, match="exceeds configured limit"):
        list(iter_xlsx_records(make_xlsx([["Name"], ["One"], ["Two"]]), 1))


def test_xlsx_file_parser_supports_seekable_stream():
    stream = BytesIO(make_xlsx([["Name"], ["A"]]))
    assert list(iter_xlsx_file(stream, 5)) == [(2, {"Name": "A"})]
