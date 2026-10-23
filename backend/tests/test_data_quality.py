from src.api import _quality_summary


class FakeDB:
    def __init__(self, values):
        self.values = iter(values)

    def scalar(self, statement):
        return next(self.values)


def test_quality_summary_reports_measured_identifier_coverage_not_verification():
    summary = _quality_summary(FakeDB([10, 2, 1]))
    assert summary["total_records"] == 10
    assert summary["identified_records"] == 8
    assert summary["missing_identifier_records"] == 2
    assert summary["possible_duplicate_records"] == 1
    assert summary["valid_percentage"] == 80.0
    assert summary["missing_percentage"] == 20.0
    assert summary["duplicate_percentage"] == 10.0
    assert "not legal verification" in summary["definitions"]["valid_percentage"]


def test_quality_summary_handles_empty_registry():
    summary = _quality_summary(FakeDB([0, 0, 0]))
    assert summary["valid_percentage"] == 0.0
    assert summary["missing_percentage"] == 0.0
    assert summary["duplicate_percentage"] == 0.0
