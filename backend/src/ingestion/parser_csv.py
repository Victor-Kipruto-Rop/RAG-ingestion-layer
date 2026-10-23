"""Bounded-memory CSV parsing helpers with strict structural validation."""
import csv
import io
from .storage import download_spooled_file


def iter_csv_file(file_obj, max_records: int):
    """Iterate a seekable binary file without decoding the whole file into memory.

    Header validation is deliberately strict: duplicate/blank headers and rows with
    extra cells are rejected rather than silently losing values through DictReader.
    """
    if max_records < 1:
        raise ValueError('max_records must be positive')
    sample_bytes = file_obj.read(8192)
    file_obj.seek(0)
    try:
        sample = sample_bytes.decode('utf-8-sig')
        encoding = 'utf-8-sig'
    except UnicodeDecodeError:
        sample = sample_bytes.decode('cp1252')
        encoding = 'cp1252'
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\\t|')
    except csv.Error:
        dialect = csv.excel
    text_stream = io.TextIOWrapper(file_obj, encoding=encoding, newline='')
    try:
        reader = csv.DictReader(text_stream, dialect=dialect)
        headers = reader.fieldnames
        if not headers or not any((h or '').strip() for h in headers):
            raise ValueError('CSV has no usable header row')
        normalized_headers = [(h or '').strip().casefold() for h in headers]
        if any(not header for header in normalized_headers):
            raise ValueError('CSV header contains an empty column name')
        if len(set(normalized_headers)) != len(normalized_headers):
            raise ValueError('CSV header contains duplicate column names')
        for row_number, row in enumerate(reader, start=2):
            if row_number - 1 > max_records:
                raise ValueError(f'CSV exceeds configured limit of {max_records} records')
            if None in row:
                raise ValueError(f'CSV row {row_number} has more columns than the header')
            yield row_number, {
                str(k).strip(): str(v or '').strip()
                for k, v in row.items()
                if k is not None
            }
    finally:
        try:
            text_stream.detach()
        except (ValueError, OSError):
            pass


def iter_csv_records(data: bytes, max_records: int):
    """Compatibility helper for tests and small fixtures."""
    with io.BytesIO(data) as file_obj:
        yield from iter_csv_file(file_obj, max_records)


def iter_csv_records_from_storage(key: str, max_records: int):
    """Read storage objects through a disk-backed spool, not a whole-file byte string."""
    with download_spooled_file(key) as file_obj:
        yield from iter_csv_file(file_obj, max_records)
