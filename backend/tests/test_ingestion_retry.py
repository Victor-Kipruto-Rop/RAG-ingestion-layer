from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api import retry_ingestion_job


class FakeDB:
    def __init__(self, job, raw=None):
        self.job = job
        self.raw = raw
        self.added = []
        self.committed = False

    def get(self, model, key):
        return self.job

    def scalar(self, statement):
        return self.raw

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True


def make_job(file_name="dataset.csv"):
    return SimpleNamespace(
        id="job-1", file_name=file_name, status="FAILED", object_key="registry-uploads/job-1/source",
        attempts=3, last_processed_row=501, next_attempt_at=None, completed_at=None,
        error_summary="temporary failure", correlation_id="req-1",
    )


def test_retry_requeues_tabular_job_and_preserves_progress():
    job = make_job()
    raw = SimpleNamespace(import_status="FAILED")
    db = FakeDB(job, raw)
    result = retry_ingestion_job("job-1", db)
    assert result["status"] == "QUEUED"
    assert result["resume_from_row"] == 501
    assert job.attempts == 0
    assert job.last_processed_row == 501
    assert raw.import_status == "QUEUED"
    assert db.committed
    assert any(getattr(item, "action", None) == "registry_ingestion_manual_retry" for item in db.added)


def test_retry_refuses_pdf_manual_review_job():
    db = FakeDB(make_job("statement.pdf"))
    with pytest.raises(HTTPException) as error:
        retry_ingestion_job("job-1", db)
    assert error.value.status_code == 409
    assert error.value.detail["code"] == "JOB_NOT_RETRYABLE"
