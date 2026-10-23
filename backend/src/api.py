import csv,io,logging,uuid
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,File,HTTPException,Query,UploadFile,Header
from fastapi.responses import StreamingResponse
from sqlalchemy import select,func,or_
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import Organization,OrganizationRecordVersion,IngestionJob,IngestionRowError,AuditLog,RegistrySource
from .security import require_api_key
from .storage import upload_bytes,StorageNotConfigured
router=APIRouter();log=logging.getLogger(__name__)
def org_out(o):
 return {'id':o.id,'legal_name':o.legal_name,'registration_number':o.registration_number,'tax_pin':o.tax_pin,'status':o.status,'registry_payload':o.registry_payload or {},'source':{'name':o.source_name,'file':o.source_file,'row':o.source_row,'record_id':o.source_record_id,'published_at':o.source_published_at.isoformat() if o.source_published_at else None},'data_quality_status':o.data_quality_status,'last_seen_at':o.last_seen_at.isoformat() if o.last_seen_at else None,'created_at':o.created_at.isoformat() if o.created_at else None,'updated_at':o.updated_at.isoformat() if o.updated_at else None}
def source_out(s):
 return {'id':s.id,'source_key':s.source_key,'display_name':s.display_name,'jurisdiction':s.jurisdiction,'source_type':s.source_type,'authority_url':s.authority_url,'licence_reference':s.licence_reference,'freshness_sla_hours':s.freshness_sla_hours,'precedence':s.precedence,'enabled':s.enabled,'notes':s.notes,'created_at':s.created_at.isoformat() if s.created_at else None,'updated_at':s.updated_at.isoformat() if s.updated_at else None}
@router.get('/api/v1/registry/lookup',dependencies=[Depends(require_api_key)])
def lookup(reg_no:str|None=None,tax_pin:str|None=None,db:Session=Depends(get_db)):
 if bool(reg_no)==bool(tax_pin):raise HTTPException(422,'Provide exactly one of reg_no or tax_pin')
 from .ingestion.normalizer import normalize_identifier
 ident=normalize_identifier(reg_no or tax_pin)
 col=Organization.normalized_registration_number if reg_no else Organization.normalized_tax_pin
 org=db.scalar(select(Organization).where(col==ident).limit(1))
 if not org:return {'status':'not_found','found':False,'organization':None,'source':'internal_registry'}
 return {'status':'record_found','found':True,'match_type':'exact_identifier','organization':org_out(org),'source':'internal_registry','last_imported_at':org.updated_at.isoformat() if org.updated_at else None,'verification_note':'Imported registry data is evidence for review, not authoritative verification by itself.'}
@router.get('/api/v1/registry/search',dependencies=[Depends(require_api_key)])
def search(q:str=Query(min_length=2,max_length=200),limit:int=Query(default=20,ge=1,le=100),db:Session=Depends(get_db)):
 from .ingestion.normalizer import normalize_legal_name
 norm=normalize_legal_name(q) or ''
 rows=db.scalars(select(Organization).where(Organization.normalized_legal_name.ilike(f'%{norm}%')).order_by(Organization.normalized_legal_name).limit(limit)).all()
 mode='substring' if rows else 'no_match'
 if not rows and db.get_bind().dialect.name=='postgresql':
  rows=db.scalars(select(Organization).where(func.similarity(Organization.normalized_legal_name,norm)>=0.25).order_by(func.similarity(Organization.normalized_legal_name,norm).desc()).limit(limit)).all()
  if rows:mode='postgres_trigram'
 return {'items':[org_out(o) for o in rows],'count':len(rows),'query':q,'match_mode':mode,'warning':'Name matches are candidates for review, not identity verification.'}
@router.get('/api/v1/organizations',dependencies=[Depends(require_api_key)])
def list_orgs(page:int=Query(default=1,ge=1),page_size:int=Query(default=25,ge=1,le=100),q:str|None=None,db:Session=Depends(get_db)):
 from .ingestion.normalizer import normalize_identifier,normalize_legal_name
 stmt=select(Organization)
 if q:
  norm=normalize_legal_name(q) or ''
  stmt=stmt.where(or_(Organization.normalized_legal_name.ilike(f'%{norm}%'),Organization.normalized_registration_number.ilike(f'%{normalize_identifier(q)}%')))
 total=db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
 rows=db.scalars(stmt.order_by(Organization.legal_name).offset((page-1)*page_size).limit(page_size)).all()
 return {'items':[org_out(o) for o in rows],'total':total,'page':page,'page_size':page_size}
@router.get('/api/v1/sources',dependencies=[Depends(require_api_key)])
def list_sources(enabled_only:bool=False,db:Session=Depends(get_db)):
 stmt=select(RegistrySource)
 if enabled_only:stmt=stmt.where(RegistrySource.enabled.is_(True))
 rows=db.scalars(stmt.order_by(RegistrySource.precedence,RegistrySource.display_name)).all()
 return {'items':[source_out(s) for s in rows],'count':len(rows)}
@router.post('/api/v1/sources',dependencies=[Depends(require_api_key)],status_code=201)
def create_source(payload:dict,db:Session=Depends(get_db)):
 key=str(payload.get('source_key','')).strip().lower()
 name=str(payload.get('display_name','')).strip()
 if not key or len(key)>100 or not all(c.isalnum() or c in '-_' for c in key):raise HTTPException(422,'source_key must contain only letters, numbers, hyphens or underscores')
 if not name or len(name)>200:raise HTTPException(422,'display_name is required and must be at most 200 characters')
 if db.scalar(select(RegistrySource).where(RegistrySource.source_key==key)):raise HTTPException(409,'source_key already exists')
 source=RegistrySource(source_key=key,display_name=name,jurisdiction=str(payload.get('jurisdiction') or 'KE')[:100],source_type=str(payload.get('source_type') or 'IMPORTED_DATASET')[:40],authority_url=payload.get('authority_url'),licence_reference=payload.get('licence_reference'),freshness_sla_hours=payload.get('freshness_sla_hours'),precedence=int(payload.get('precedence',100)),enabled=bool(payload.get('enabled',True)),notes=payload.get('notes'))
 db.add(source);db.commit();db.refresh(source);return source_out(source)
@router.post('/api/v1/ingestion/uploads',dependencies=[Depends(require_api_key)],status_code=202)
async def upload(file:UploadFile=File(...),db:Session=Depends(get_db),correlation_id:str|None=Header(default=None,alias='X-Correlation-ID'),idempotency_key:str|None=Header(default=None,alias='Idempotency-Key'),source_key:str|None=Header(default=None,alias='X-Registry-Source')):
 name=(file.filename or 'upload.csv').replace('\\\\','/').split('/')[-1]
 suffix='.'+name.rsplit('.',1)[-1].lower() if '.' in name else ''
 if suffix not in {'.csv','.pdf'}:raise HTTPException(415,'Only CSV and PDF files are accepted')
 if idempotency_key:
  prior=db.scalar(select(IngestionJob).where(IngestionJob.idempotency_key==idempotency_key))
  if prior:return {'job_id':prior.id,'status':prior.status,'idempotent_replay':True}
 source=None
 if source_key:
  source=db.scalar(select(RegistrySource).where(RegistrySource.source_key==source_key.strip().lower(),RegistrySource.enabled.is_(True)))
  if not source:raise HTTPException(422,'Unknown or disabled registry source')
 data=await file.read(settings.max_upload_bytes+1)
 if len(data)>settings.max_upload_bytes:raise HTTPException(413,'File exceeds configured upload limit')
 if not data:raise HTTPException(400,'Uploaded file is empty')
 if suffix=='.pdf' and not data.startswith(b'%PDF-'):raise HTTPException(415,'File extension is PDF but the file signature is invalid')
 if suffix=='.csv' and b'\x00' in data[:4096]:raise HTTPException(415,'CSV contains binary data')
 job=IngestionJob(file_name=name,content_type=file.content_type or 'application/octet-stream',status='QUEUED',source_id=source.id if source else None,source_name=source.source_key if source else 'uploaded_dataset',idempotency_key=idempotency_key)
 db.add(job);db.flush()
 key=f'registry-uploads/{job.id}/{uuid.uuid4().hex}-{name}'
 try:
  upload_bytes(key,data,file.content_type or 'application/octet-stream')
  job.object_key=key
  db.add(AuditLog(action='registry_ingestion_queued',actor='internal-service',file_name=name,details={'job_id':job.id,'source_key':source.source_key if source else None,'correlation_id':correlation_id}))
  db.commit();db.refresh(job)
  return {'job_id':job.id,'file_name':job.file_name,'status':job.status,'records_processed':0,'records_inserted':0,'records_updated':0,'records_skipped':0,'message':'Upload stored; a worker will process this job asynchronously.'}
 except StorageNotConfigured as exc:db.rollback();raise HTTPException(503,'Object storage is not configured') from exc
 except Exception as exc:
  db.rollback();log.exception('Unable to queue ingestion correlation_id=%s',correlation_id)
  raise HTTPException(502,'Unable to store or queue upload') from exc
@router.get('/api/v1/ingestion/jobs',dependencies=[Depends(require_api_key)])
def jobs(page:int=Query(default=1,ge=1),page_size:int=Query(default=25,ge=1,le=100),db:Session=Depends(get_db)):
 rows=db.scalars(select(IngestionJob).order_by(IngestionJob.created_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
 return {'items':[{'id':j.id,'file_name':j.file_name,'status':j.status,'attempts':j.attempts,'source_name':j.source_name,'records_processed':j.records_processed,'records_inserted':j.records_inserted,'records_updated':j.records_updated,'records_skipped':j.records_skipped,'error_summary':j.error_summary,'created_at':j.created_at.isoformat() if j.created_at else None,'started_at':j.started_at.isoformat() if j.started_at else None,'completed_at':j.completed_at.isoformat() if j.completed_at else None} for j in rows]}
@router.get('/api/v1/ingestion/jobs/{job_id}/errors',dependencies=[Depends(require_api_key)])
def job_errors(job_id:str,page:int=Query(default=1,ge=1),page_size:int=Query(default=100,ge=1,le=500),db:Session=Depends(get_db)):
 if not db.get(IngestionJob,job_id):raise HTTPException(404,'Ingestion job not found')
 stmt=select(IngestionRowError).where(IngestionRowError.job_id==job_id)
 total=db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
 rows=db.scalars(stmt.order_by(IngestionRowError.row_number).offset((page-1)*page_size).limit(page_size)).all()
 return {'job_id':job_id,'total':total,'page':page,'page_size':page_size,'items':[{'row_number':r.row_number,'error_code':r.error_code,'message':r.message,'created_at':r.created_at.isoformat() if r.created_at else None} for r in rows]}
@router.get('/api/v1/metrics/summary',dependencies=[Depends(require_api_key)])
def metrics(db:Session=Depends(get_db)):
 return {'total_organizations':db.scalar(select(func.count()).select_from(Organization)) or 0,'total_jobs':db.scalar(select(func.count()).select_from(IngestionJob)) or 0,'queued_jobs':db.scalar(select(func.count()).select_from(IngestionJob).where(IngestionJob.status=='QUEUED')) or 0,'processing_jobs':db.scalar(select(func.count()).select_from(IngestionJob).where(IngestionJob.status=='PROCESSING')) or 0,'completed_jobs':db.scalar(select(func.count()).select_from(IngestionJob).where(IngestionJob.status.in_(['COMPLETED','COMPLETED_WITH_ERRORS']))) or 0,'failed_jobs':db.scalar(select(func.count()).select_from(IngestionJob).where(IngestionJob.status=='FAILED')) or 0}
@router.get('/api/v1/exports/organizations.csv',dependencies=[Depends(require_api_key)])
def export_csv(db:Session=Depends(get_db)):
 def stream():
  buffer=io.StringIO();writer=csv.writer(buffer);writer.writerow(['legal_name','registration_number','tax_pin','status','source_name','source_file','source_row','data_quality_status']);yield buffer.getvalue();buffer.seek(0);buffer.truncate(0)
  for o in db.scalars(select(Organization).order_by(Organization.legal_name).yield_per(500)):
   vals=[o.legal_name,o.registration_number or '',o.tax_pin or '',o.status,o.source_name or '',o.source_file or '',o.source_row or '',o.data_quality_status]
   safe=["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\\t','\\r')) else v for v in vals]
   writer.writerow(safe);yield buffer.getvalue();buffer.seek(0);buffer.truncate(0)
 return StreamingResponse(stream(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=pesaguard-registry-export.csv'})
