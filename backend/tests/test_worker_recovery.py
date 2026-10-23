from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src import worker
from src.database import Base
from src.models import AuditLog, IngestionJob, WarehouseRawImport


@pytest.mark.parametrize(
    ("attempts", "expected_status"),
    [(1, "QUEUED"), (3, "FAILED")],
)
def test_stale_recovery_updates_import_status_and_audit(
    monkeypatch, attempts, expected_status
):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    old_start = datetime.now(timezone.utc) - timedelta(hours=1)

    with TestSession() as db:
        job = IngestionJob(
            file_name="stale-test.csv",
            object_key="local://stale-test.csv",
            status="PROCESSING",
            attempts=attempts,
            started_at=old_start,
        )
        db.add(job)
        db.flush()
        db.add(
            WarehouseRawImport(
                ingestion_job_id=job.id,
                object_key="stale-test.csv",
                original_filename="stale-test.csv",
                import_status="PROCESSING",
            )
        )
        db.commit()
        job_id = job.id

    monkeypatch.setattr(worker, "SessionLocal", TestSession)
    monkeypatch.setattr(worker.settings, "worker_stale_after_seconds", 60)
    monkeypatch.setattr(worker.settings, "worker_retry_seconds", 1)
    monkeypatch.setattr(worker.settings, "worker_max_attempts", 3)

    worker.recover_stale_jobs()

    with TestSession() as db:
        job = db.get(IngestionJob, job_id)
        raw = db.scalar(
            select(WarehouseRawImport).where(
                WarehouseRawImport.ingestion_job_id == job_id
            )
        )
        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "registry_stale_job_recovered"
            )
        )
        assert job.status == expected_status
        assert raw.import_status == expected_status
        assert audit is not None
        assert audit.details["job_id"] == job_id

    engine.dispose()

def test_expired_direct_upload_is_failed_and_audited(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    with TestSession() as db:
        job = IngestionJob(
            file_name="abandoned.csv",
            status="UPLOADING",
            correlation_id="expired-upload-test",
        )
        db.add(job)
        db.flush()
        db.add(
            WarehouseRawImport(
                ingestion_job_id=job.id,
                object_key="registry-uploads/abandoned.csv",
                original_filename="abandoned.csv",
                import_status="UPLOADING",
                metadata_json={"upload_expires_at": int(datetime.now(timezone.utc).timestamp()) - 60},
            )
        )
        db.commit()
        job_id = job.id

    monkeypatch.setattr(worker, "SessionLocal", TestSession)
    worker.recover_stale_jobs()

    with TestSession() as db:
        job = db.get(IngestionJob, job_id)
        raw = db.scalar(
            select(WarehouseRawImport).where(
                WarehouseRawImport.ingestion_job_id == job_id
            )
        )
        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "registry_direct_upload_expired"
            )
        )
        assert job.status == "FAILED"
        assert job.completed_at is not None
        assert raw.import_status == "FAILED"
        assert audit is not None
        assert audit.details["job_id"] == job_id

    engine.dispose()
