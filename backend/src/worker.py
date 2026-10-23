"""Run with: python -m src.worker. PostgreSQL is recommended for multiple workers."""
import logging,time
from datetime import datetime,timezone
from sqlalchemy import select
from .config import settings
from .database import SessionLocal
from .models import IngestionJob,Organization,OrganizationRecordVersion,IngestionRowError,AuditLog
from .storage import download_bytes
from .ingestion.parser_csv import iter_csv_records
from .ingestion.normalizer import normalize_record
log=logging.getLogger('registry.worker')
def now():return datetime.now(timezone.utc)
def snap(o):
 return {'legal_name':o.legal_name,'normalized_legal_name':o.normalized_legal_name,'registration_number':o.registration_number,'normalized_registration_number':o.normalized_registration_number,'tax_pin':o.tax_pin,'normalized_tax_pin':o.normalized_tax_pin,'status':o.status,'registry_payload':o.registry_payload or {},'data_quality_status':o.data_quality_status}
def claim_job():
 with SessionLocal() as db:
  stmt=select(IngestionJob).where(IngestionJob.status=='QUEUED').order_by(IngestionJob.created_at).limit(1)
  if db.bind.dialect.name=='postgresql':stmt=stmt.with_for_update(skip_locked=True)
  job=db.scalar(stmt)
  if not job:return None
  job.status='PROCESSING';job.attempts=(job.attempts or 0)+1;job.started_at=now();db.commit()
  return job.id
def process_job(job_id):
 with SessionLocal() as db:
  job=db.get(IngestionJob,job_id)
  if not job:return
  try:
   if not job.object_key:raise RuntimeError('Ingestion source object is missing')
   suffix='.'+job.file_name.rsplit('.',1)[-1].lower() if '.' in job.file_name else ''
   if suffix=='.pdf':
    job.status='NEEDS_PDF_PROCESSING';job.error_summary='PDF extraction/OCR is not enabled; upload is retained for a future processing adapter.';job.completed_at=now();db.commit();return
   data=download_bytes(job.object_key)
   processed=inserted=updated=skipped=0
   for row_num,row in iter_csv_records(data,settings.max_records_per_file):
    processed+=1
    try:
     rec=normalize_record(row);reg=rec.get('normalized_registration_number');pin=rec.get('normalized_tax_pin')
     existing=None
     if reg:existing=db.scalar(select(Organization).where(Organization.normalized_registration_number==reg).limit(1))
     if existing is None and not reg and pin:existing=db.scalar(select(Organization).where(Organization.normalized_tax_pin==pin).limit(1))
     if existing:
      before=snap(existing)
      for key,value in rec.items():setattr(existing,key,value)
      existing.source_file=job.file_name;existing.source_row=row_num;existing.source_name=job.source_name or 'uploaded_dataset';existing.source_record_id=reg or pin;existing.last_seen_at=now();existing.data_quality_status='IMPORTED_UNVERIFIED'
      db.flush()
      db.add(OrganizationRecordVersion(organization_id=existing.id,change_type='UPDATED',snapshot={'before':before,'after':snap(existing)},source_name=existing.source_name,source_file=job.file_name,source_row=row_num));updated+=1
     else:
      org=Organization(**rec,source_file=job.file_name,source_row=row_num,source_name=job.source_name or 'uploaded_dataset',source_record_id=reg or pin,last_seen_at=now(),data_quality_status='IMPORTED_UNVERIFIED')
      db.add(org);db.flush()
      db.add(OrganizationRecordVersion(organization_id=org.id,change_type='CREATED',snapshot={'after':snap(org)},source_name=org.source_name,source_file=job.file_name,source_row=row_num));inserted+=1
    except ValueError as exc:
     skipped+=1;db.add(IngestionRowError(job_id=job.id,row_number=row_num,error_code='INVALID_ROW',message=str(exc)[:1000]))
    except Exception as exc:
     skipped+=1;db.add(IngestionRowError(job_id=job.id,row_number=row_num,error_code='ROW_PROCESSING_ERROR',message=str(exc)[:1000]))
   job.records_processed=processed;job.records_inserted=inserted;job.records_updated=updated;job.records_skipped=skipped
   job.status='COMPLETED_WITH_ERRORS' if skipped else 'COMPLETED';job.error_summary=f'{skipped} row(s) were skipped; see row-errors endpoint.' if skipped else None;job.completed_at=now()
   db.add(AuditLog(action='registry_ingestion_completed',actor='ingestion-worker',file_name=job.file_name,details={'job_id':job.id,'processed':processed,'inserted':inserted,'updated':updated,'skipped':skipped}))
   db.commit()
  except Exception as exc:
   db.rollback()
   with SessionLocal() as retry_db:
    job=retry_db.get(IngestionJob,job_id)
    if job:
     if job.attempts < settings.worker_max_attempts:
      job.status='QUEUED';job.error_summary=f'Attempt {job.attempts} failed; will retry. {str(exc)[:500]}'
     else:
      job.status='FAILED';job.error_summary=f'Ingestion failed after {job.attempts} attempts: {str(exc)[:800]}';job.completed_at=now()
     retry_db.commit()
   log.exception('Job processing failed job_id=%s',job_id)
def run_forever():
 logging.basicConfig(level=logging.INFO);log.info('Ingestion worker starting')
 while True:
  try:
   job_id=claim_job()
   if job_id:process_job(job_id)
   else:time.sleep(max(0.25,settings.worker_poll_seconds))
  except KeyboardInterrupt:break
  except Exception:log.exception('Worker loop error');time.sleep(max(1,settings.worker_retry_seconds))
if __name__=='__main__':run_forever()
