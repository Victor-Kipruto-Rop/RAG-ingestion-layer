from io import BytesIO

import pytest

from src.ingestion.parser_csv import iter_csv_file, iter_csv_records


def test_csv_rows_are_iterated_with_line_numbers():
    rows = list(iter_csv_records(b"legal_name,registration_number\nAlpha Ltd,REG-1\nBeta Ltd,REG-2\n", 10))
    assert rows == [
        (2, {"legal_name": "Alpha Ltd", "registration_number": "REG-1"}),
        (3, {"legal_name": "Beta Ltd", "registration_number": "REG-2"}),
    ]


def test_csv_record_limit_is_enforced_during_iteration():
    rows = iter_csv_records(b"legal_name\nAlpha Ltd\nBeta Ltd\n", 1)
    assert next(rows)[1]["legal_name"] == "Alpha Ltd"
    with pytest.raises(ValueError, match="configured limit"):
        next(rows)


def test_empty_or_missing_header_is_rejected():
    with pytest.raises(ValueError, match="header"):
        list(iter_csv_records(b"\n\n", 10))


def test_file_iterator_accepts_seekable_binary_stream():
    stream = BytesIO(b"legal_name;status\nAlpha Ltd;ACTIVE\n")
    assert list(iter_csv_file(stream, 10)) == [
        (2, {"legal_name": "Alpha Ltd", "status": "ACTIVE"})
    ]


def test_tab_delimited_csv_is_detected():
    rows = list(iter_csv_records(b"legal_name\\tstatus\\nAlpha Ltd\\tACTIVE\\n", 10))
    assert rows == [(2, {"legal_name": "Alpha Ltd", "status": "ACTIVE"})]

def test_large_csv_is_consumed_in_bounded_reads():
    class ReadTrackingStream(BytesIO):
        def __init__(self, data):
            super().__init__(data)
            self.read_sizes = []

        def read(self, size=-1):
            self.read_sizes.append(size)
            return super().read(size)

        def read1(self, size=-1):
            self.read_sizes.append(size)
            return super().read1(size)

    data = ("legal_name,registration_number\\n" + "".join(
        f"Example Company {index},REG-{index}\\n" for index in range(2500)
    )).encode()
    stream = ReadTrackingStream(data)

    rows = iter_csv_file(stream, 3000)
    assert next(rows)[1]["legal_name"] == "Example Company 0"
    assert sum(1 for _ in rows) == 2499
    assert stream.read_sizes
    assert all(size >= 0 for size in stream.read_sizes), "parser must not issue an unbounded read"

