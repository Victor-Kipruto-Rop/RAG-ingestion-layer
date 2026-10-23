"""Bounded-memory CSV parsing helpers."""
import codecs
import csv
import io

from .storage import download_spooled_file


def _detect_encoding(file_obj):
    """Validate the whole stream without loading it into memory."""
    decoder = codecs.getincrementaldecoder("utf-8-sig")()
    valid_utf8 = True
    try:
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            if b"\x00" in chunk:
                raise ValueError("CSV contains binary data")
            if valid_utf8:
                try:
                    decoder.decode(chunk, final=False)
                except UnicodeDecodeError:
                    valid_utf8 = False
        if valid_utf8:
            try:
                decoder.decode(b"", final=True)
            except UnicodeDecodeError:
                valid_utf8 = False
        return "utf-8-sig" if valid_utf8 else "cp1252"
    finally:
        file_obj.seek(0)


def iter_csv_file(file_obj, max_records: int):
    """Iterate a seekable binary file without decoding the whole file into memory."""
    if max_records < 1:
        raise ValueError("max_records must be positive")

    encoding = _detect_encoding(file_obj)
    sample_bytes = file_obj.read(8192)
    file_obj.seek(0)
    sample = sample_bytes.decode(encoding)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    text_stream = io.TextIOWrapper(file_obj, encoding=encoding, errors="strict", newline="")
    try:
        reader = csv.DictReader(text_stream, dialect=dialect, restkey="__extra_columns__")
        if not reader.fieldnames or not any((header or "").strip() for header in reader.fieldnames):
            raise ValueError("CSV has no usable header row")

        normalized_headers = [str(header or "").strip().casefold() for header in reader.fieldnames]
        if len(set(normalized_headers)) != len(normalized_headers):
            raise ValueError("CSV contains duplicate column headers")

        for row_number, row in enumerate(reader, start=2):
            if row_number - 1 > max_records:
                raise ValueError(f"CSV exceeds configured limit of {max_records} records")
            if row.get("__extra_columns__"):
                yield row_number, {"__csv_parse_error__": "CSV row contains more values than the header"}
                continue
            if any(value is None for key, value in row.items() if key != "__extra_columns__"):
                yield row_number, {"__csv_parse_error__": "CSV row contains fewer values than the header"}
                continue
            yield row_number, {
                str(key or "").strip(): str(value or "").strip()
                for key, value in row.items()
                if key is not None and key != "__extra_columns__"
            }
    except UnicodeDecodeError as exc:
        raise ValueError("CSV contains invalid text encoding; export as UTF-8 or Windows-1252") from exc
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
