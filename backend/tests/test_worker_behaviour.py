"""Worker behaviour: change detection, source precedence, heartbeat, lease loss and upload expiry."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from src import storage, worker
from src.config import settings
from src.database import Base, SessionLocal, engine
from src.models import (AuditLog, IngestionJob, Organization, OrganizationRecordVersion, RegistrySource,
                        WarehouseRawImport)

Base.metadata.create_all(engine)


def _uid():
    return uuid.uuid4().hex[:10].upper()


def _make_job(csv_text, source_name='uploaded_dataset', status='QUEUED', attempts=0):
    job_id = str(uuid.uuid4())
    key = f'tests/{job_id}/data.csv'
    storage.upload_bytes(key, csv_text.encode(), 'text/csv')
    with SessionLocal() as db:
        db.add(IngestionJob(id=job_id, file_name='data.csv', object_key=key, status=status, attempts=attempts, source_name=source_name))
        db.flush()
        db.add(WarehouseRawImport(ingestion_job_id=job_id, object_key=key, original_filename='data.csv', byte_size=len(csv_text),
                                  source_name=source_name, import_status=status))
        db.commit()
    return job_id


def _job(job_id):
    with SessionLocal() as db:
        return db.get(IngestionJob, job_id)


def _org(reg):
    with SessionLocal() as db:
        return db.scalar(select(Organization).where(Organization.normalized_registration_number == reg))


def _versions(org_id):
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(OrganizationRecordVersion).where(OrganizationRecordVersion.organization_id == org_id))


def _source(key, precedence):
    with SessionLocal() as db:
        db.add(RegistrySource(source_key=key, display_name=key, precedence=precedence))
        db.commit()


def test_reimporting_identical_data_creates_no_new_versions_but_refreshes_last_seen():
    reg = 'U' + _uid()
    csv_text = f'Company Name,Registration No\nUnchanged {reg} Limited,{reg}\n'
    worker.process_job(_make_job(csv_text))
    first = _org(reg)
    again = _make_job(csv_text)
    worker.process_job(again)
    second = _org(reg)
    job = _job(again)
    assert (job.status, job.records_processed, job.records_inserted, job.records_updated) == ('COMPLETED', 1, 0, 0)
    assert _versions(first.id) == 1
    assert second.last_seen_at >= first.last_seen_at


def test_changed_data_creates_a_version_and_resets_verification_but_keeps_review_flag():
    verified, flagged = 'V' + _uid(), 'F' + _uid()
    worker.process_job(_make_job(f'Company Name,Registration No\nAlpha {verified},{verified}\nBeta {flagged},{flagged}\n'))
    with SessionLocal() as db:
        db.scalar(select(Organization).where(Organization.normalized_registration_number == verified)).data_quality_status = 'MANUALLY_VERIFIED'
        db.scalar(select(Organization).where(Organization.normalized_registration_number == flagged)).data_quality_status = 'POSSIBLE_DUPLICATE_REVIEW'
        db.commit()
    # identical content must not disturb a reviewed status
    same = _make_job(f'Company Name,Registration No\nAlpha {verified},{verified}\n')
    worker.process_job(same)
    assert _org(verified).data_quality_status == 'MANUALLY_VERIFIED'
    changed = _make_job(f'Company Name,Registration No\nAlpha Renamed {verified},{verified}\nBeta Renamed {flagged},{flagged}\n')
    worker.process_job(changed)
    assert _job(changed).records_updated == 2
    assert _org(verified).data_quality_status == 'IMPORTED_UNVERIFIED'
    assert _org(flagged).data_quality_status == 'POSSIBLE_DUPLICATE_REVIEW'
    assert _versions(_org(verified).id) == 2


def test_lower_precedence_source_cannot_overwrite_a_more_authoritative_one():
    high, low, reg = 'hi-' + _uid().lower(), 'lo-' + _uid().lower(), 'P' + _uid()
    _source(high, 10)
    _source(low, 200)
    worker.process_job(_make_job(f'Company Name,Registration No\nOfficial Name {reg},{reg}\n', source_name=high))
    blocked = _make_job(f'Company Name,Registration No\nScraped Name {reg},{reg}\n', source_name=low)
    worker.process_job(blocked)
    assert _org(reg).legal_name == f'Official Name {reg}'
    assert _job(blocked).records_updated == 0
    with SessionLocal() as db:
        audit = db.scalars(select(AuditLog).where(AuditLog.action == 'registry_lower_precedence_update_skipped')).all()
        assert any(a.details['incoming_source'] == low and a.details['existing_source'] == high for a in audit)
    # the authoritative source may update its own record, and may overwrite a lower one
    worker.process_job(_make_job(f'Company Name,Registration No\nOfficial Name 2 {reg},{reg}\n', source_name=high))
    assert _org(reg).legal_name == f'Official Name 2 {reg}'
    other = 'Q' + _uid()
    worker.process_job(_make_job(f'Company Name,Registration No\nLow First {other},{other}\n', source_name=low))
    worker.process_job(_make_job(f'Company Name,Registration No\nHigh Second {other},{other}\n', source_name=high))
    assert _org(other).legal_name == f'High Second {other}'


def test_fuzzy_duplicates_inside_one_file_are_flagged_for_review():
    tag = 'ZQ' + _uid()
    job_id = _make_job(f'Company Name,Registration No\n{tag} Kenya Limited,DA{tag}\n{tag} Kenya Ltd,DB{tag}\n')
    worker.process_job(job_id)
    assert _org('DA' + tag).data_quality_status == 'IMPORTED_UNVERIFIED'
    assert _org('DB' + tag).data_quality_status == 'POSSIBLE_DUPLICATE_REVIEW'


# --- heartbeat, lease and recovery
def test_claim_sets_a_heartbeat_and_recovery_respects_it(monkeypatch):
    monkeypatch.setattr(settings, 'worker_stale_after_seconds', 60)
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    alive, dead = _make_job('Company Name\nX\n', status='PROCESSING', attempts=1), _make_job('Company Name\nX\n', status='PROCESSING', attempts=1)
    with SessionLocal() as db:
        db.get(IngestionJob, alive).started_at = old
        db.get(IngestionJob, alive).heartbeat_at = datetime.now(timezone.utc)
        db.get(IngestionJob, dead).started_at = old
        db.get(IngestionJob, dead).heartbeat_at = old
        db.commit()
    worker.recover_stale_jobs()
    assert _job(alive).status == 'PROCESSING', 'a job with a fresh heartbeat is alive even if it started long ago'
    assert _job(dead).status == 'QUEUED'
    claimed = _make_job('Company Name\nY\n')
    with SessionLocal() as db:  # make this the oldest queued job so claim_job picks it
        db.get(IngestionJob, claimed).created_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        db.commit()
    assert worker.claim_job() == claimed
    assert _job(claimed).heartbeat_at is not None


def test_a_worker_that_lost_its_lease_stops_without_overwriting_the_new_owner(monkeypatch):
    rows = ''.join(f'Lease {i} {_uid()},L{i}{_uid()}\n' for i in range(3))
    job_id = _make_job('Company Name,Registration No\n' + rows, status='PROCESSING', attempts=1)
    monkeypatch.setattr(settings, 'ingestion_batch_size', 1)

    def another_worker_claims(_keys):
        with SessionLocal() as db:
            db.get(IngestionJob, job_id).attempts = 2
            db.commit()
    monkeypatch.setattr(worker, 'invalidate_lookup_keys', another_worker_claims)
    worker.process_job(job_id)
    job = _job(job_id)
    assert job.records_processed == 1, 'processing stops at the first checkpoint after the lease is lost'
    assert job.status == 'PROCESSING' and job.attempts == 2, 'the new owner keeps control; no retry or failure is recorded'


def test_progress_is_committed_on_a_timer_not_only_by_row_count(monkeypatch):
    rows = [f'Timer {i} {_uid()},T{i}{_uid()}' for i in range(3)]
    job_id = _make_job('Company Name,Registration No\n' + '\n'.join(rows) + '\n', status='PROCESSING', attempts=1)
    monkeypatch.setattr(settings, 'ingestion_batch_size', 100000)
    monkeypatch.setattr(settings, 'worker_commit_interval_seconds', 1)
    clock = iter(range(0, 1000, 5))
    monkeypatch.setattr(worker.time, 'monotonic', lambda: next(clock))
    original = worker.normalize_record

    def explode_on_third(row):
        if row['Company Name'].startswith('Timer 2'):
            raise RuntimeError('simulated crash')
        return original(row)
    monkeypatch.setattr(worker, 'normalize_record', explode_on_third)
    worker.process_job(job_id)
    job = _job(job_id)
    assert job.last_processed_row == 3, 'rows 2 and 3 were checkpointed before the crash on row 4'
    assert job.records_processed == 2 and job.heartbeat_at is not None


# --- abandoned direct uploads
def test_abandoned_direct_uploads_are_expired_and_their_objects_deleted(monkeypatch):
    stale = _make_job('x', status='UPLOADING')
    fresh = _make_job('x', status='UPLOADING')
    with SessionLocal() as db:
        db.get(IngestionJob, stale).created_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    deleted = []
    monkeypatch.setattr(worker, 'delete_object', lambda key: deleted.append(key) or True)
    assert worker.expire_abandoned_uploads() >= 1
    assert _job(stale).status == 'FAILED' and _job(fresh).status == 'UPLOADING'
    assert any(stale in key for key in deleted) and not any(fresh in key for key in deleted)
    with SessionLocal() as db:
        assert db.scalar(select(WarehouseRawImport).where(WarehouseRawImport.ingestion_job_id == stale)).import_status == 'FAILED'


def test_worker_module_imports_cleanly():
    import importlib
    for name in ('src.worker', 'src.preflight', 'src.main', 'src.ingestion.parser_csv'):
        importlib.import_module(name)


def test_a_constraint_conflict_skips_the_row_instead_of_failing_the_whole_job(monkeypatch):
    if engine.dialect.name != 'postgresql':
        pytest.skip('row-level SAVEPOINT isolation is PostgreSQL-only')
    reg, fresh = 'X' + _uid(), 'Y' + _uid()
    worker.process_job(_make_job(f'Company Name,Registration No\nExisting {reg},{reg}\n'))
    original = worker._find_existing
    # Simulate a concurrent worker inserting the same identifier between lookup and insert.
    monkeypatch.setattr(worker, '_find_existing', lambda db, rec: None if rec.get('normalized_registration_number') == reg else original(db, rec))
    job_id = _make_job(f'Company Name,Registration No\nConflicting {reg},{reg}\nGood Row {fresh},{fresh}\n')
    worker.process_job(job_id)
    job = _job(job_id)
    assert (job.status, job.records_inserted, job.records_skipped) == ('COMPLETED_WITH_ERRORS', 1, 1)
    assert _org(fresh) is not None
