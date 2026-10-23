import csv,io,logging,uuid
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,File,HTTPException,Query,UploadFile,Header
from fastapi.responses import StreamingResponse
from rapidfuzz import fuzz
from sqlalchemy import select,func,or_
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import Organization,IngestionJob,AuditLog
from .security import require_api_key
from .ingestion.parser_csv import iter_csv_records
from .ingestion.normalizer import normalize_record,normalize_identifier,normalize_legal_name
from .storage import upload_bytes,StorageNotConfigured
router=APIRouter();log=logging.getLogger(__name__)
def org_out(o):return {'id':o.id,'legal_name':o.legal_name,'registration_number':o.registration_number,'status':o.status,'registry_payload':o.registry_payload or {},'source_file':o.source_file,'source_row':o.source_row,'created_at':o.created_at.isoformat() if o.created_at else None,'updated_at':o.updated_at.isoformat() if o.updated_at else None}
@router.get('/api/v1/registry/lookup',dependencies=[Depends(require_api_key)])
def lookup(reg_no:str|None=None,tax_pin:str|None=None,db:Session=Depends(get_db)):
 if not reg_no and not tax_pin:raise HTTPException(422,'Provide reg_no or tax_pin')
 ident=normalize_identifier(reg_no or tax_pin)
 col=Organization.normalized_registration_number if reg_no else Organization.normalized_tax_pin
 org=db.scalar(select(Organization).where(col==ident).limit(1))
 if not org:return {'status':'not_found','found':False,'organization':None,'source':'internal_registry'}
 return {'status':'record_found','found':True,'match_type':'exact_identifier','organization':org_out(org),'source':'internal_registry','last_imported_at':org.updated_at.isoformat() if org.updated_at else None,'verification_note':'A local record is not authoritative verification.'}
@router.get('/api/v1/registry/search',dependencies=[Depends(require_api_key)])
def search(q:str=Query(min_length=2,max_length=200),limit:int=Query(default=20,ge=1,le=100),db:Session=Depends(get_db)):
 norm=normalize_legal_name(q) or '';rows=db.scalars(select(Organization).where(Organization.normalized_legal_name.ilike(f'%{norm}%')).limit(limit)).all()
 if not rows:
  candidates=db.scalars(select(Organization).limit(500)).all();ranked=sorted(((fuzz.WRatio(norm,o.normalized_legal_name or ''),o) for o in candidates),key=lambda x:x[0],reverse=True);rows=[o for score,o in ranked[:limit] if score>=65]
 return {'items':[org_out(o) for o in rows],'count':len(rows),'query':q}
@router.get('/api/v1/organizations',dependencies=[Depends(require_api_key)])
def list_orgs(page:int=Query(default=1,ge=1),page_size:int=Query(default=25,ge=1,le=100),q:str|None=None,db:Session=Depends(get_db)):
 stmt=select(Organization)
 if q:stmt=stmt.where(or_(Organization.normalized_legal_name.ilike(f'%{q.upper()}%'),Organization.normalized_registration_number.ilike(f'%{q.upper()}%')))
 total=db.scalar(select(func.count()).select_from(stmt.subquery())) or 0;rows=db.scalars(stmt.order_by(Organization.legal_name).offset((page-1)*page_size).limit(page_size)).all()
 return {'items':[org_out(o) for o in rows],'total':total,'page':page,'page_size':page_size}
@router.post('/api/v1/ingestion/uploads',dependencies=[Depends(require_api_key)])
async def upload(file:UploadFile=File(...),db:Session=Depends(get_db),correlation_id:str|None=Header(default=None,alias='X-Correlation-ID')):
 name=(file.filename or 'upload.csv').replace('\\','/').split('/')[-1];suffix='.'+name.rsplit('.',1)[-1].lower() if '.' in name else ''
 if suffix not in {'.csv','.pdf'}:raise HTTPException(415,'Only CSV and PDF files are accepted')
 data=await file.read(settings.max_upload_bytes+1)
 if len(data)>settings.max_upload_bytes:raise HTTPException(413,'File exceeds configured upload limit')
 if not data:raise HTTPException(400,'Uploaded file is empty')
 job=IngestionJob(file_name=name,status='PROCESSING');db.add(job);db.flush();key=f'registry-uploads/{job.id}/{uuid.uuid4().hex}-{name}'
 try:
  try:upload_bytes(key,data,file.content_type or 'application/octet-stream');job.object_key=key
  except StorageNotConfigured:
   if settings.app_env.lower()=='production':raise HTTPException(503,'Object storage is not configured')
   job.error_summary='R2 not configured; original file not retained after request'
  except Exception as exc:
   log.exception('R2 upload failed correlation_id=%s',correlation_id)
   if settings.app_env.lower()=='production':raise HTTPException(502,'Unable to store original file') from exc
   job.error_summary='R2 upload failed in development mode'
  if suffix=='.pdf':job.status='NEEDS_PDF_PROCESSING';job.error_summary='PDF stored if R2 is configured; PDF text extraction and record ingestion are not implemented in this release.'
  else:
   inserted=skipped=processed=0
   for row_num,row in iter_csv_records(data,settings.max_records_per_file):
    processed+=1
    try:
     rec=normalize_record(row);reg=rec.get('normalized_registration_number');existing=db.scalar(select(Organization).where(Organization.normalized_registration_number==reg).limit(1)) if reg else None
     if existing:
      for k,v in rec.items():setattr(existing,k,v)
      existing.source_file=name;existing.source_row=row_num
     else:db.add(Organization(**rec,source_file=name,source_row=row_num));inserted+=1
    except ValueError:skipped+=1
   job.records_processed=processed;job.records_inserted=inserted;job.records_skipped=skipped;job.status='COMPLETED_WITH_ERRORS' if skipped else 'COMPLETED';job.completed_at=datetime.now(timezone.utc)
  db.add(AuditLog(action='registry_ingestion',actor='internal-service',file_name=name,details={'job_id':job.id,'status':job.status,'correlation_id':correlation_id}));db.commit();db.refresh(job)
  return {'job_id':job.id,'file_name':job.file_name,'status':job.status,'records_processed':job.records_processed,'records_inserted':job.records_inserted,'records_updated':job.records_updated,'records_skipped':job.records_skipped,'error_summary':job.error_summary}
 except HTTPException:db.rollback();raise
 except Exception as exc:db.rollback();log.exception('Ingestion failed correlation_id=%s',correlation_id);raise HTTPException(500,'Ingestion failed; inspect server diagnostics') from exc
@router.get('/api/v1/ingestion/jobs',dependencies=[Depends(require_api_key)])
def jobs(page:int=Query(default=1,ge=1),page_size:int=Query(default=25,ge=1,le=100),db:Session=Depends(get_db)):
 rows=db.scalars(select(IngestionJob).order_by(IngestionJob.created_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
 return {'items':[{'id':j.id,'file_name':j.file_name,'status':j.status,'records_processed':j.records_processed,'records_inserted':j.records_inserted,'records_updated':j.records_updated,'records_skipped':j.records_skipped,'error_summary':j.error_summary,'created_at':j.created_at.isoformat() if j.created_at else None,'completed_at':j.completed_at.isoformat() if j.completed_at else None} for j in rows]}
@router.get('/api/v1/metrics/summary',dependencies=[Depends(require_api_key)])
def metrics(db:Session=Depends(get_db)):
 return {'total_organizations':db.scalar(select(func.count()).select_from(Organization)) or 0,'total_jobs':db.scalar(select(func.count()).select_from(IngestionJob)) or 0,'completed_jobs':db.scalar(select(func.count()).select_from(IngestionJob).where(IngestionJob.status=='COMPLETED')) or 0,'failed_jobs':db.scalar(select(func.count()).select_from(IngestionJob).where(IngestionJob.status=='FAILED')) or 0}
@router.get('/api/v1/exports/organizations.csv',dependencies=[Depends(require_api_key)])
def export_csv(db:Session=Depends(get_db)):
 def stream():
  buffer=io.StringIO();writer=csv.writer(buffer);writer.writerow(['legal_name','registration_number','status','source_file','source_row']);yield buffer.getvalue();buffer.seek(0);buffer.truncate(0)
  for o in db.scalars(select(Organization).order_by(Organization.legal_name).yield_per(500)):
   vals=[o.legal_name,o.registration_number or '',o.status,o.source_file or '',o.source_row or ''];safe=["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\\t','\\r')) else v for v in vals];writer.writerow(safe);yield buffer.getvalue();buffer.seek(0);buffer.truncate(0)
 return StreamingResponse(stream(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=pesaguard-registry-export.csv'})
