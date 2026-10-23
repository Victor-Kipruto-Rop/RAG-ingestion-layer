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
    rows = list(iter_csv_records(b"legal_name\tstatus\nAlpha Ltd\tACTIVE\n", 10))
    assert rows == [(2, {"legal_name": "Alpha Ltd", "status": "ACTIVE"})]


def test_extra_columns_are_marked_for_dead_letter_handling():
    rows = list(iter_csv_records(b"legal_name,status\nAlpha Ltd,ACTIVE,UNEXPECTED\n", 10))
    assert rows == [(2, {"__csv_parse_error__": "CSV row contains more values than the header"})]


def test_missing_trailing_values_are_marked_for_dead_letter_handling():
    rows = list(iter_csv_records(b"legal_name,status\nAlpha Ltd\n", 10))
    assert rows == [(2, {"__csv_parse_error__": "CSV row contains fewer values than the header"})]


def test_duplicate_headers_are_rejected_case_insensitively():
    with pytest.raises(ValueError, match="duplicate column headers"):
        list(iter_csv_records(b"legal_name,LEGAL_NAME\nAlpha Ltd,Alpha Ltd\n", 10))


def test_invalid_cp1252_byte_after_sample_fails_with_safe_message():
    payload = b"legal_name\n" + b"A" * 8190 + b"\x81\n"
    with pytest.raises(ValueError, match="invalid text encoding"):
        list(iter_csv_records(payload, 10))


def test_windows_1252_character_after_initial_sample_is_detected():
    payload = b"legal_name\n" + b"A" * 8190 + b"\nCaf\xe9 Limited\n"
    rows = list(iter_csv_records(payload, 10))
    assert rows[1][1]["legal_name"] == "Café Limited"
