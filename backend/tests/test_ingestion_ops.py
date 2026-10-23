from src.ingestion_ops import safe_csv_cell


def test_csv_diagnostic_cells_are_safe_from_spreadsheet_formulas():
    assert safe_csv_cell('=HYPERLINK("https://example.invalid")').startswith("'=")
    assert safe_csv_cell("+cmd").startswith("'+")
    assert safe_csv_cell("-1").startswith("'-")
    assert safe_csv_cell("@SUM(A1:A2)").startswith("'@")
    assert safe_csv_cell("ordinary diagnostic") == "ordinary diagnostic"


def test_csv_diagnostic_cell_preserves_empty_and_none_values():
    assert safe_csv_cell(None) == ""
    assert safe_csv_cell("") == ""
    assert safe_csv_cell("INVALID_ROW") == ""
