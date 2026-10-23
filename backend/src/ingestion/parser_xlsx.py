"""Bounded-row XLSX parsing helpers using openpyxl's read-only worksheet iterator."""
from .storage import download_spooled_file


def _unique_headers(values):
    seen = {}
    headers = []
    for index, value in enumerate(values, start=1):
        base = str(value).strip() if value is not None else ""
        base = base or f"column_{index}"
        seen[base] = seen.get(base, 0) + 1
        headers.append(base if seen[base] == 1 else f"{base}_{seen[base]}")
    return headers


def iter_xlsx_file(file_obj, max_records: int):
    """Yield (1-based worksheet row number, mapping) without loading all rows into memory."""
    if max_records < 1:
        raise ValueError("max_records must be positive")
    from openpyxl import load_workbook

    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    try:
        if not workbook.worksheets:
            raise ValueError("XLSX workbook contains no worksheets")
        worksheet = workbook.worksheets[0]
        rows = worksheet.iter_rows(values_only=True)
        try:
            first = next(rows)
        except StopIteration:
            raise ValueError("XLSX worksheet is empty")
        headers = _unique_headers(first)
        if not any(not header.startswith("column_") or header not in {"column_" + str(i) for i in range(1, len(headers) + 1)} for header in headers):
            raise ValueError("XLSX has no usable header row")
        for row_number, values in enumerate(rows, start=2):
            if row_number - 1 > max_records:
                raise ValueError(f"XLSX exceeds configured limit of {max_records} records")
            values = list(values)
            record = {}
            for index, header in enumerate(headers):
                value = values[index] if index < len(values) else None
                record[header] = "" if value is None else str(value).strip()
            if any(value for value in record.values()):
                yield row_number, record
    finally:
        workbook.close()


def iter_xlsx_records(data: bytes, max_records: int):
    """Compatibility helper for small fixtures and tests."""
    import io
    with io.BytesIO(data) as file_obj:
        yield from iter_xlsx_file(file_obj, max_records)


def iter_xlsx_records_from_storage(key: str, max_records: int):
    """Parse an XLSX object from a disk-backed spool."""
    with download_spooled_file(key) as file_obj:
        yield from iter_xlsx_file(file_obj, max_records)
