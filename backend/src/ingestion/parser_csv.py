"""Bounded-memory CSV parsing helpers."""
import csv
import io
from .storage import download_spooled_file


def iter_csv_file(file_obj, max_records: int):
    """Iterate a seekable binary file without decoding the whole file into memory."""
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
        if not reader.fieldnames or not any((h or '').strip() for h in reader.fieldnames):
            raise ValueError('CSV has no usable header row')
        for row_number, row in enumerate(reader, start=2):
            if row_number - 1 > max_records:
                raise ValueError(f'CSV exceeds configured limit of {max_records} records')
            yield row_number, {str(k or '').strip(): str(v or '').strip() for k, v in row.items() if k is not None}
    finally:
        try: text_stream.detach()
        except (ValueError, OSError): pass


def iter_csv_records(data: bytes, max_records: int):
    """Compatibility helper for tests and small fixtures."""
    with io.BytesIO(data) as file_obj:
        yield from iter_csv_file(file_obj, max_records)


def iter_csv_records_from_storage(key: str, max_records: int):
    """Read storage objects through a disk-backed spool, not a whole-file byte string."""
    with download_spooled_file(key) as file_obj:
        yield from iter_csv_file(file_obj, max_records)
