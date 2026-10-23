"""Run with: python -m src.worker. PostgreSQL is recommended for multiple workers."""
import argparse,logging,time,traceback
import structlog
from datetime import datetime,timezone,timedelta
from sqlalchemy import select
from .config import settings
from .database import SessionLocal
from .models import IngestionJob,Organization,OrganizationRecordVersion,IngestionRowError,AuditLog,WarehouseRawImport,FailedImportDLQ
from .storage import download_bytes
from .ingestion.parser_csv import iter_csv_records_from_storage
from .ingestion.normalizer import normalize_record
from .entity_resolution import similarity_score
from .cache import invalidate_lookup_keys
structlog.configure(processors=[structlog.processors.TimeStamper(fmt='iso'),structlog.processors.add_log_level,structlog.processors.format_exc_info,structlog.processors.JSONRenderer()],logger_factory=structlog.stdlib.LoggerFactory())
logging.basicConfig(level=logging.INFO,format='%(message)s')
log=structlog.get_logger('registry.worker')

_SENSITIVE_KEY_PARTS=('tax_pin','kra_pin','pin','phone','mobile','email','password','secret','token','account_number','identity_number','id_number')
def _sanitize_dlq_row(row):
 safe={}
 for key,value in row.items():
  normalized=str(key).strip().lower().replace('-','_')
  safe[str(key)[:100]]='[REDACTED]' if any(part in normalized for part in _SENSITIVE_KEY_PARTS) else (str(value)[:500] if value is not None else None)
 return safe

def _sanitize_diagnostic(value,row):
 text=str(value)
 for key,item in row.items():
  normalized=str(key).strip().lower().replace('-','_')
  if item is not None and any(part in normalized for part in _SENSITIVE_KEY_PARTS):
   secret=str(item)
   if secret: text=text.replace(secret,'[REDACTED]')
 return text[:16000]

def now():return datetime.now(timezone.utc)
def snap(o):
 return {'legal_name':o.legal_name,'normalized_legal_name':o.normalized_legal_name,'registration_number':o.registration_number,'normalized_registration_number':o.normalized_registration_number,'tax_pin':o.tax_pin,'normalized_tax_pin':o.normalized_tax_pin,'status':o.status,'registry_payload':o.registry_payload or {},'data_quality_status':o.data_quality_status}
def claim_job():
 with SessionLocal() as db:
  stmt=select(IngestionJob).where(IngestionJob.status=='QUEUED', (IngestionJob.next_attempt_at.is_(None)) | (IngestionJob.next_attempt_at<=now())).order_by(IngestionJob.created_at).limit(1)
  if db.bind.dialect.name=='postgresql':stmt=stmt.with_for_update(skip_locked=True)
  job=db.scalar(stmt)
  if not job:return None
  job.status='PROCESSING';job.attempts=(job.attempts or 0)+1;job.started_at=now();job.next_attempt_at=None;db.commit()
  return job.id
def process_job(job_id):
 with SessionLocal() as db:
  job=db.get(IngestionJob,job_id)
  if not job:return
  log.info('ingestion_job_started',job_id=job_id,request_id=job.correlation_id)
  try:
   if not job.object_key:raise RuntimeError('Ingestion source object is missing')
   suffix='.'+job.file_name.rsplit('.',1)[-1].lower() if '.' in job.file_name else ''
   raw_import=db.scalar(select(WarehouseRawImport).where(WarehouseRawImport.ingestion_job_id==job.id))
   if suffix=='.pdf':
    from .ingestion.pdf_text import extract_pdf_text
    data=download_bytes(job.object_key)
    diagnostics=extract_pdf_text(data, enable_ocr=settings.pdf_ocr_enabled, max_ocr_pages=settings.pdf_ocr_max_pages)
    job.status='NEEDS_PDF_PROCESSING'
    if diagnostics.needs_ocr and diagnostics.extracted_characters:
     job.error_summary=f'Extracted {diagnostics.extracted_characters} character(s) from {diagnostics.page_count} page(s), but OCR coverage is incomplete; manual review is required.'
    elif diagnostics.needs_ocr and diagnostics.ocr_attempted and not diagnostics.ocr_available:
     job.error_summary=f'PDF has {diagnostics.page_count} page(s); OCR was unavailable or failed, so manual review is required.'
    elif diagnostics.needs_ocr:
     job.error_summary=f'PDF has {diagnostics.page_count} page(s) but no searchable text; OCR and manual review are required.'
    else:
     job.error_summary=f'Extracted {diagnostics.extracted_characters} character(s) from {diagnostics.page_count} page(s); manual review is required. Extracted text is not treated as verified data.'
    if raw_import:
     raw_import.import_status='NEEDS_PDF_PROCESSING'
     metadata=dict(raw_import.metadata_json or {})
     metadata.update({'pdf_page_count':diagnostics.page_count,'pdf_extracted_characters':diagnostics.extracted_characters,'pdf_needs_ocr':diagnostics.needs_ocr,'pdf_extraction_version':2,'pdf_ocr_attempted':diagnostics.ocr_attempted,'pdf_ocr_available':diagnostics.ocr_available,'pdf_ocr_pages_processed':diagnostics.ocr_pages_processed,'requires_manual_review':True})
     raw_import.metadata_json=metadata
    job.completed_at=now()
    db.add(AuditLog(action='registry_pdf_extraction_diagnostics',actor='ingestion-worker',file_name=job.file_name,details={'job_id':job.id,'page_count':diagnostics.page_count,'extracted_characters':diagnostics.extracted_characters,'needs_ocr':diagnostics.needs_ocr,'ocr_attempted':diagnostics.ocr_attempted,'ocr_available':diagnostics.ocr_available,'ocr_pages_processed':diagnostics.ocr_pages_processed,'manual_review_required':True}))
    db.commit();return
   if raw_import:raw_import.import_status='PROCESSING';db.flush()
   processed=job.records_processed or 0
   inserted=job.records_inserted or 0
   updated=job.records_updated or 0
   skipped=job.records_skipped or 0
   changed_lookup_keys=set()
   batch_count=0
   last_row_number=job.last_processed_row or 1
   for row_num,row in iter_csv_records_from_storage(job.object_key,settings.max_records_per_file):
    if row_num <= last_row_number:
     continue
    processed+=1
    batch_count+=1
    last_row_number=row_num
    try:
     rec=normalize_record(row);reg=rec.get('normalized_registration_number');pin=rec.get('normalized_tax_pin')
     if reg:changed_lookup_keys.add(f'registry:lookup:reg:{reg}')
     if pin:changed_lookup_keys.add(f'registry:lookup:pin:{pin}')
     existing=None
     if reg:existing=db.scalar(select(Organization).where(Organization.normalized_registration_number==reg).limit(1))
     if existing is None and not reg and pin:existing=db.scalar(select(Organization).where(Organization.normalized_tax_pin==pin).limit(1))
     potential_duplicates=[]
     if existing is None and rec.get('legal_name'):
      name_tokens=rec['normalized_legal_name'].split()
      prefix=(name_tokens[0][:3] if name_tokens else '')
      if prefix:
       candidates=db.scalars(select(Organization).where(Organization.normalized_legal_name.ilike(f'{prefix}%')).order_by(Organization.normalized_legal_name).limit(200)).all()
       for candidate in candidates:
        score=similarity_score(rec['legal_name'],candidate.legal_name)
        if score>=92.0:
         potential_duplicates.append({'organization_id':candidate.id,'similarity_score':score})
     if existing:
      before=snap(existing)
      if existing.normalized_registration_number:changed_lookup_keys.add(f'registry:lookup:reg:{existing.normalized_registration_number}')
      if existing.normalized_tax_pin:changed_lookup_keys.add(f'registry:lookup:pin:{existing.normalized_tax_pin}')
      for key,value in rec.items():setattr(existing,key,value)
      existing.source_file=job.file_name;existing.source_row=row_num;existing.source_name=job.source_name or 'uploaded_dataset';existing.source_record_id=reg or pin;existing.last_seen_at=now();existing.data_quality_status='IMPORTED_UNVERIFIED'
      db.flush()
      db.add(OrganizationRecordVersion(organization_id=existing.id,change_type='UPDATED',snapshot={'before':before,'after':snap(existing)},source_name=existing.source_name,source_file=job.file_name,source_row=row_num));updated+=1
     else:
      quality='POSSIBLE_DUPLICATE_REVIEW' if potential_duplicates else 'IMPORTED_UNVERIFIED'
      org=Organization(**rec,source_file=job.file_name,source_row=row_num,source_name=job.source_name or 'uploaded_dataset',source_record_id=reg or pin,last_seen_at=now(),data_quality_status=quality)
      db.add(org);db.flush()
      snapshot={'after':snap(org),'possible_duplicate_candidates':potential_duplicates}
      db.add(OrganizationRecordVersion(organization_id=org.id,change_type='CREATED_POSSIBLE_DUPLICATE' if potential_duplicates else 'CREATED',snapshot=snapshot,source_name=org.source_name,source_file=job.file_name,source_row=row_num))
      if potential_duplicates:db.add(AuditLog(action='registry_possible_duplicate_candidate',actor='ingestion-worker',file_name=job.file_name,details={'job_id':job.id,'row_number':row_num,'new_organization_id':org.id,'candidates':potential_duplicates,'decision':'manual_review_required'}))
      inserted+=1
    except ValueError as exc:
     skipped+=1
     message=_sanitize_diagnostic(exc,row)[:1000]
     db.add(IngestionRowError(job_id=job.id,row_number=row_num,error_code='INVALID_ROW',message=message))
     db.add(FailedImportDLQ(job_id=job.id,row_number=row_num,error_code='INVALID_ROW',error_type=type(exc).__name__,message=message,sanitized_row=_sanitize_dlq_row(row),traceback_text=_sanitize_diagnostic(traceback.format_exc(),row)))
    except Exception:
     raise
    if batch_count >= max(1, settings.ingestion_batch_size):
     job.last_processed_row=last_row_number
     job.records_processed=processed;job.records_inserted=inserted;job.records_updated=updated;job.records_skipped=skipped
     if raw_import:raw_import.import_status='PROCESSING'
     db.commit()
     invalidate_lookup_keys(changed_lookup_keys)
     changed_lookup_keys.clear()
     db.expunge_all()
     job=db.get(IngestionJob,job_id)
     raw_import=db.scalar(select(WarehouseRawImport).where(WarehouseRawImport.ingestion_job_id==job.id)) if job else None
     batch_count=0
   job.last_processed_row=last_row_number
   job.records_processed=processed;job.records_inserted=inserted;job.records_updated=updated;job.records_skipped=skipped
   job.status='COMPLETED_WITH_ERRORS' if skipped else 'COMPLETED'
   if raw_import:raw_import.import_status=job.status
   job.error_summary=f'{skipped} row(s) were skipped; see row-errors endpoint.' if skipped else None;job.completed_at=now()
   db.add(AuditLog(action='registry_ingestion_completed',actor='ingestion-worker',file_name=job.file_name,details={'job_id':job.id,'processed':processed,'inserted':inserted,'updated':updated,'skipped':skipped}))
   db.commit()
   invalidate_lookup_keys(changed_lookup_keys)
   log.info('ingestion_job_completed',job_id=job_id,request_id=job.correlation_id,status=job.status,processed=processed,inserted=inserted,updated=updated,skipped=skipped)
  except Exception as exc:
   db.rollback()
   with SessionLocal() as retry_db:
    job=retry_db.get(IngestionJob,job_id)
    if job:
     raw_import=retry_db.scalar(select(WarehouseRawImport).where(WarehouseRawImport.ingestion_job_id==job.id))
     if job.attempts < settings.worker_max_attempts:
      job.status='QUEUED'
      if raw_import:raw_import.import_status='QUEUED'
      job.next_attempt_at=now()+timedelta(seconds=max(1,settings.worker_retry_seconds)*(2**max(0,job.attempts-1)));job.error_summary=f'Attempt {job.attempts} failed; retry scheduled. {str(exc)[:500]}'
     else:
      job.status='FAILED'
      if raw_import:raw_import.import_status='FAILED'
      job.error_summary=f'Ingestion failed after {job.attempts} attempts: {str(exc)[:800]}';job.completed_at=now()
     retry_db.commit()
   log.exception('job_processing_failed',job_id=job_id)
def recover_stale_jobs():
 cutoff=now()-timedelta(seconds=max(60,settings.worker_stale_after_seconds))
 with SessionLocal() as db:
  stale=db.scalars(select(IngestionJob).where(IngestionJob.status=='PROCESSING',IngestionJob.started_at<cutoff)).all()
  for job in stale:
   raw_import=db.scalar(select(WarehouseRawImport).where(WarehouseRawImport.ingestion_job_id==job.id))
   if job.attempts < settings.worker_max_attempts:
    job.status='QUEUED';job.next_attempt_at=now()+timedelta(seconds=max(1,settings.worker_retry_seconds));job.error_summary='Recovered stale processing job after worker interruption.'
    if raw_import:raw_import.import_status='QUEUED'
   else:
    job.status='FAILED';job.completed_at=now();job.error_summary='Worker interrupted repeatedly; maximum attempts reached.'
    if raw_import:raw_import.import_status='FAILED'
   db.add(AuditLog(action='registry_stale_job_recovered',actor='ingestion-worker',file_name=job.file_name,details={'job_id':job.id,'attempts':job.attempts,'recovered_status':job.status}))
  if stale:
   db.commit()
   log.warning('stale_jobs_recovered',count=len(stale))
def run_batch(max_jobs=None):
 """Process a bounded number of eligible jobs, then exit for scheduled runners."""
 logging.basicConfig(level=logging.INFO,format='%(message)s')
 limit=max(1, int(max_jobs if max_jobs is not None else settings.worker_max_jobs_per_run))
 log.info('scheduled_ingestion_batch_starting', max_jobs=limit)
 recover_stale_jobs()
 processed=0
 for _ in range(limit):
  job_id=claim_job()
  if not job_id:
   break
  process_job(job_id)
  processed+=1
 log.info('scheduled_ingestion_batch_finished', claimed_jobs=processed)
 return processed

def run_forever():
 logging.basicConfig(level=logging.INFO,format='%(message)s');log.info('ingestion_worker_starting')
 while True:
  try:
   recover_stale_jobs()
   job_id=claim_job()
   if job_id:process_job(job_id)
   else:time.sleep(max(0.25,settings.worker_poll_seconds))
  except KeyboardInterrupt:break
  except Exception:log.exception('worker_loop_error');time.sleep(max(1,settings.worker_retry_seconds))

if __name__=='__main__':
 parser=argparse.ArgumentParser(description='PesaGuard ingestion worker')
 parser.add_argument('--batch', action='store_true', help='Process a bounded batch and exit')
 parser.add_argument('--max-jobs', type=int, default=None, help='Override the batch job limit')
 args=parser.parse_args()
 if args.batch:
  run_batch(args.max_jobs)
 else:
  run_forever()
