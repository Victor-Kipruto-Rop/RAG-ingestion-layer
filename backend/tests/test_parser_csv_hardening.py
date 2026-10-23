import pytest

from src.ingestion.parser_csv import iter_csv_records


def test_csv_parser_preserves_normal_rows():
    rows = list(iter_csv_records(b"legal_name,registration_number\nAcme Limited,CPR-1\n", 10))
    assert rows == [(2, {"legal_name": "Acme Limited", "registration_number": "CPR-1"})]


def test_csv_parser_rejects_duplicate_headers_case_insensitively():
    with pytest.raises(ValueError, match="duplicate column names"):
        list(iter_csv_records(b"legal_name, Legal_Name\nAcme,Acme\n", 10))


def test_csv_parser_rejects_empty_header_cells():
    with pytest.raises(ValueError, match="empty column name"):
        list(iter_csv_records(b"legal_name,,registration_number\nAcme,x,CPR-1\n", 10))


def test_csv_parser_rejects_rows_with_extra_cells_instead_of_dropping_data():
    with pytest.raises(ValueError, match="row 2 has more columns"):
        list(iter_csv_records(b"legal_name,registration_number\nAcme,CPR-1,unexpected\n", 10))


def test_csv_parser_enforces_record_limit():
    with pytest.raises(ValueError, match="exceeds configured limit"):
        list(iter_csv_records(b"legal_name\nAcme\nBeta\n", 1))


def test_csv_parser_keeps_short_rows_with_empty_values():
    rows = list(iter_csv_records(b"legal_name,registration_number\nAcme\n", 10))
    assert rows == [(2, {"legal_name": "Acme", "registration_number": ""})]
