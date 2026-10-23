import csv,io,uuid,hashlib
import structlog
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,File,HTTPException,Query,UploadFile,Header,Request
from pydantic import BaseModel,Field
from fastapi.responses import StreamingResponse
from sqlalchemy import select,func,or_
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import Organization,OrganizationRecordVersion,IngestionJob,IngestionRowError,AuditLog,RegistrySource,WarehouseRawImport
from .security import require_api_key
from .storage import upload_fileobj,StorageNotConfigured,presign_upload_url,head_object,read_object_prefix
from .cache import get_json,set_json
router=APIRouter();log=structlog.get_logger(__name__)
def org_out(o):
 return {'id':o.id,'legal_name':o.legal_name,'registration_number':o.registration_number,'tax_pin':o.tax_pin,'status':o.status,'registry_payload':o.registry_payload or {},'source':{'name':o.source_name,'file':o.source_file,'row':o.source_row,'record_id':o.source_record_id,'published_at':o.source_published_at.isoformat() if o.source_published_at else None},'data_quality_status':o.data_quality_status,'last_seen_at':o.last_seen_at.isoformat() if o.last_seen_at else None,'created_at':o.created_at.isoformat() if o.created_at else None,'updated_at':o.updated_at.isoformat() if o.updated_at else None}
def source_out(s):
 return {'id':s.id,'source_key':s.source_key,'display_name':s.display_name,'jurisdiction':s.jurisdiction,'source_type':s.source_type,'authority_url':s.authority_url,'licence_reference':s.licence_reference,'freshness_sla_hours':s.freshness_sla_hours,'precedence':s.precedence,'enabled':s.enabled,'notes':s.notes,'created_at':s.created_at.isoformat() if s.created_at else None,'updated_at':s.updated_at.isoformat() if s.updated_at else None}
@router.get('/api/v1/registry/lookup',dependencies=[Depends(require_api_key)])
def lookup(reg_no:str|None=None,tax_pin:str|None=None,db:Session=Depends(get_db)):
 if bool(reg_no)==bool(tax_pin):raise HTTPException(422,'Provide exactly one of reg_no or tax_pin')
 from .ingestion.normalizer import normalize_identifier
 ident=normalize_identifier(reg_no or tax_pin)
 kind='reg' if reg_no else 'pin'
 cache_key=f'registry:lookup:{kind}:{ident}'
 cached=get_json(cache_key)
 if cached is not None:
  if cached.get('_cache_not_found'):return {'status':'not_found','found':False,'organization':None,'source':'internal_registry'}
  return cached
 col=Organization.normalized_registration_number if reg_no else Organization.normalized_tax_pin
 org=db.scalar(select(Organization).where(col==ident).limit(1))
 if not org:
  set_json(cache_key,{'_cache_not_found':True},settings.registry_cache_negative_ttl_seconds)
  return {'status':'not_found','found':False,'organization':None,'source':'internal_registry'}
 result={'status':'record_found','found':True,'match_type':'exact_identifier','organization':org_out(org),'source':'internal_registry','last_imported_at':org.updated_at.isoformat() if org.updated_at else None,'verification_note':'Imported registry data is evidence for review, not authoritative verification by itself.'}
 set_json(cache_key,result,settings.registry_cache_ttl_seconds)
 return result
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
def _record_quality(org):
 fields = {
  'legal_name': {'present': bool(org.legal_name), 'weight': 25},
  'registration_number': {'present': bool(org.normalized_registration_number), 'weight': 25},
  'tax_pin': {'present': bool(org.normalized_tax_pin), 'weight': 20},
  'source_name': {'present': bool(org.source_name), 'weight': 10},
  'source_file': {'present': bool(org.source_file), 'weight': 10},
  'last_seen_at': {'present': bool(org.last_seen_at), 'weight': 10},
 }
 score = sum(item['weight'] for item in fields.values() if item['present'])
 flags = [f'missing_{name}' for name,item in fields.items() if not item['present']]
 if org.data_quality_status == 'POSSIBLE_DUPLICATE_REVIEW':
  flags.append('possible_duplicate_review')
 if org.data_quality_status in {'IMPORTED_UNVERIFIED','UNREVIEWED','POSSIBLE_DUPLICATE_REVIEW'}:
  flags.append('not_authoritatively_verified')
 return {
  'organization_id': org.id,
  'completeness_score': score,
  'fields': {name:{'present':item['present'],'weight':item['weight']} for name,item in fields.items()},
  'flags': flags,
  'source': {'name':org.source_name,'file':org.source_file,'row':org.source_row,'published_at':org.source_published_at.isoformat() if org.source_published_at else None},
  'data_quality_status': org.data_quality_status,
  'verification_status': 'not_verified',
  'score_definition': 'Weighted field completeness and source attribution only. This score is not a probability, trust rating, or legal verification result.'
 }

@router.get('/api/v1/organizations/{organization_id}/quality',dependencies=[Depends(require_api_key)])
def organization_quality(organization_id:str,db:Session=Depends(get_db)):
 org=db.get(Organization,organization_id)
 if not org:raise HTTPException(404,'Organization record not found')
 return _record_quality(org)

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
class DirectUploadRequest(BaseModel):
 file_name:str=Field(min_length=1,max_length=500)
 size_bytes:int=Field(gt=0)

@router.post('/api/v1/ingestion/uploads/presign',dependencies=[Depends(require_api_key)],status_code=201)
def presign_direct_upload(payload:DirectUploadRequest,request:Request,db:Session=Depends(get_db),correlation_id:str|None=Header(default=None,alias='X-Correlation-ID'),idempotency_key:str|None=Header(default=None,alias='Idempotency-Key')):
 name=payload.file_name.replace(chr(92),'/').split('/')[-1]
 suffix='.'+name.rsplit('.',1)[-1].lower() if '.' in name else ''
 if suffix not in {'.csv','.pdf','.xlsx'}:raise HTTPException(415,'Only CSV, XLSX, and PDF files are accepted')
 if payload.size_bytes>settings.max_direct_upload_bytes:raise HTTPException(413,'File exceeds configured direct-upload limit')
 if suffix=='.xlsx' and payload.size_bytes>settings.max_xlsx_upload_bytes:raise HTTPException(413,'XLSX file exceeds the configured XLSX upload limit')
 content_type='application/pdf' if suffix=='.pdf' else ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if suffix=='.xlsx' else 'text/csv')
 correlation_id=(correlation_id or getattr(request.state,'request_id',None) or str(uuid.uuid4()))[:100]
 if idempotency_key:
  prior=db.scalar(select(IngestionJob).where(IngestionJob.idempotency_key==idempotency_key))
  if prior:
   raw=db.scalar(select(WarehouseRawImport).where(WarehouseRawImport.ingestion_job_id==prior.id))
   if prior.status!='UPLOADING' or not raw or raw.byte_size!=payload.size_bytes or prior.file_name!=name or prior.content_type!=content_type:raise HTTPException(409,'Idempotency key is already associated with a different or completed upload')
   try:url=presign_upload_url(prior.object_key,content_type,settings.direct_upload_url_ttl_seconds)
   except StorageNotConfigured as exc:raise HTTPException(503,'Direct object storage is not configured') from exc
   return {'job_id':prior.id,'status':prior.status,'upload_url':url,'content_type':content_type,'expires_in_seconds':settings.direct_upload_url_ttl_seconds,'idempotent_replay':True}
 job=IngestionJob(file_name=name,correlation_id=correlation_id,content_type=content_type,status='UPLOADING',source_name='direct_r2_upload',idempotency_key=idempotency_key)
 db.add(job);db.flush()
 key=f'registry-uploads/{job.id}/{uuid.uuid4().hex}-{name}'
 try:url=presign_upload_url(key,content_type,settings.direct_upload_url_ttl_seconds)
 except StorageNotConfigured as exc:db.rollback();raise HTTPException(503,'Direct object storage is not configured') from exc
 job.object_key=key
 expires_at=int(datetime.now(timezone.utc).timestamp())+settings.direct_upload_url_ttl_seconds
 db.add(WarehouseRawImport(ingestion_job_id=job.id,object_key=key,original_filename=name,content_type=content_type,byte_size=payload.size_bytes,source_name='direct_r2_upload',uploaded_by='internal-service',import_status='UPLOADING',metadata_json={'correlation_id':correlation_id,'file_suffix':suffix,'upload_expires_at':expires_at,'direct_upload':True}))
 db.add(AuditLog(action='registry_direct_upload_presigned',actor='internal-service',file_name=name,details={'job_id':job.id,'correlation_id':correlation_id,'expected_size_bytes':payload.size_bytes}))
 db.commit()
 return {'job_id':job.id,'status':job.status,'upload_url':url,'content_type':content_type,'expires_in_seconds':settings.direct_upload_url_ttl_seconds,'idempotent_replay':False}

@router.post('/api/v1/ingestion/uploads/{job_id}/complete',dependencies=[Depends(require_api_key)])
def complete_direct_upload(job_id:str,db:Session=Depends(get_db)):
 job=db.get(IngestionJob,job_id)
 if not job:raise HTTPException(404,'Ingestion job not found')
 if job.status!='UPLOADING':return {'job_id':job.id,'status':job.status,'idempotent_replay':True}
 raw=db.scalar(select(WarehouseRawImport).where(WarehouseRawImport.ingestion_job_id==job.id))
 if not raw:raise HTTPException(409,'Upload metadata is missing')
 if int((raw.metadata_json or {}).get('upload_expires_at',0))<int(datetime.now(timezone.utc).timestamp()):
  job.status='FAILED';job.error_summary='Direct upload URL expired before completion.';job.completed_at=datetime.now(timezone.utc);raw.import_status='FAILED';db.commit();raise HTTPException(410,'Direct upload expired; create a new upload job')
 try:
  metadata=head_object(job.object_key)
 except StorageNotConfigured as exc:raise HTTPException(503,'Direct object storage is not configured') from exc
 except Exception as exc:raise HTTPException(502,'Unable to verify uploaded object') from exc
 actual_size=int(metadata.get('ContentLength',0) or 0)
 if actual_size<=0 or actual_size>settings.max_direct_upload_bytes or actual_size!=raw.byte_size:
  job.status='FAILED';job.error_summary='Uploaded object size did not match the declared size.';job.completed_at=datetime.now(timezone.utc);raw.import_status='FAILED';db.commit();raise HTTPException(422,'Uploaded object size did not match the declared size')
 try:
  prefix=read_object_prefix(job.object_key,4096)
 except Exception as exc:raise HTTPException(502,'Unable to inspect uploaded object signature') from exc
 suffix='.'+job.file_name.rsplit('.',1)[-1].lower() if '.' in job.file_name else ''
 if suffix=='.pdf' and not prefix.startswith(b'%PDF-'):
  job.status='FAILED';job.error_summary='PDF signature validation failed.';job.completed_at=datetime.now(timezone.utc);raw.import_status='FAILED';db.commit();raise HTTPException(415,'PDF file signature is invalid')
 if suffix=='.xlsx' and not prefix.startswith(b'PK\x03\x04'):
  job.status='FAILED';job.error_summary='XLSX archive signature validation failed.';job.completed_at=datetime.now(timezone.utc);raw.import_status='FAILED';db.commit();raise HTTPException(415,'XLSX file signature is invalid')
 if suffix=='.csv' and b'\x00' in prefix:
  job.status='FAILED';job.error_summary='CSV binary signature validation failed.';job.completed_at=datetime.now(timezone.utc);raw.import_status='FAILED';db.commit();raise HTTPException(415,'CSV contains binary data')
 raw.byte_size=actual_size;raw.import_status='QUEUED'
 raw.metadata_json={**(raw.metadata_json or {}),'r2_etag':str(metadata.get('ETag','')).strip('"'),'upload_completed_at':datetime.now(timezone.utc).isoformat()}
 job.status='QUEUED';job.error_summary=None
 db.add(AuditLog(action='registry_direct_upload_completed',actor='internal-service',file_name=job.file_name,details={'job_id':job.id,'correlation_id':job.correlation_id,'byte_size':actual_size}))
 db.commit()
 return {'job_id':job.id,'status':job.status,'file_name':job.file_name,'correlation_id':job.correlation_id,'message':'Object verified in private storage and queued for background processing.'}
@router.post('/api/v1/ingestion/preview',dependencies=[Depends(require_api_key)])
async def preview_upload(file:UploadFile=File(...)):
 name=(file.filename or 'upload.csv').replace(chr(92),'/').split('/')[-1]
 suffix='.'+name.rsplit('.',1)[-1].lower() if '.' in name else ''
 if suffix not in {'.csv','.xlsx'}:raise HTTPException(415,'Preview supports CSV and XLSX files; PDF remains manual-review-only')
 data=await file.read(5*1024*1024+1)
 if len(data)>5*1024*1024:raise HTTPException(413,'Preview is limited to 5 MiB; submit the full file to create an ingestion job')
 if not data:raise HTTPException(400,'Uploaded file is empty')
 if suffix=='.xlsx':
  if not data.startswith(b'PK\x03\x04'):raise HTTPException(415,'XLSX file signature is invalid')
  from itertools import islice
  from .ingestion.parser_xlsx import iter_xlsx_records
  try:
   iterator=iter_xlsx_records(data,21)
   sample=list(islice(iterator,21))
   iterator.close()
  except ValueError as exc:raise HTTPException(422,str(exc)) from exc
  columns=list(sample[0][1].keys()) if sample else []
 else:
  if b'\x00' in data[:4096]:raise HTTPException(415,'CSV contains binary data')
  try:text_data=data.decode('utf-8-sig')
  except UnicodeDecodeError:
   try:text_data=data.decode('cp1252')
   except UnicodeDecodeError as exc:raise HTTPException(415,'CSV encoding is unsupported') from exc
  try:
   dialect=csv.Sniffer().sniff(text_data[:8192],delimiters=',;\t|')
  except csv.Error:dialect=csv.excel
  reader=csv.DictReader(io.StringIO(text_data,newline=''),dialect=dialect)
  columns=[str(h or '').strip() for h in (reader.fieldnames or [])]
  if not columns or not any(columns):raise HTTPException(422,'CSV has no usable header row')
  sample=[]
  for index,row in enumerate(reader):
   if index>=21:break
   sample.append((index+2,{str(k or '').strip():str(v or '').strip()[:500] for k,v in row.items() if k is not None}))
 return {'file_name':name,'file_type':suffix[1:],'columns':columns,'sample_rows':[{'row_number':number,'values':{key:str(value)[:500] for key,value in values.items()}} for number,values in sample[:20]],'sample_count':min(len(sample),20),'has_more':len(sample)>20,'preview_limit_bytes':5*1024*1024,'persisted':False,'message':'Preview only. No ingestion job or registry record was created.'}

@router.post('/api/v1/ingestion/uploads',dependencies=[Depends(require_api_key)],status_code=202)
async def upload(request:Request,file:UploadFile=File(...),db:Session=Depends(get_db),correlation_id:str|None=Header(default=None,alias='X-Correlation-ID'),idempotency_key:str|None=Header(default=None,alias='Idempotency-Key'),source_key:str|None=Header(default=None,alias='X-Registry-Source')):
 correlation_id=(correlation_id or getattr(request.state,'request_id',None) or str(uuid.uuid4()))[:100]
 name=(file.filename or 'upload.csv').replace(chr(92), '/').split('/')[-1]
 suffix='.'+name.rsplit('.',1)[-1].lower() if '.' in name else ''
 if suffix not in {'.csv','.pdf','.xlsx'}:raise HTTPException(415,'Only CSV, XLSX, and PDF files are accepted')
 if idempotency_key:
  prior=db.scalar(select(IngestionJob).where(IngestionJob.idempotency_key==idempotency_key))
  if prior:return {'job_id':prior.id,'status':prior.status,'idempotent_replay':True}
 source=None
 if source_key:
  source=db.scalar(select(RegistrySource).where(RegistrySource.source_key==source_key.strip().lower(),RegistrySource.enabled.is_(True)))
  if not source:raise HTTPException(422,'Unknown or disabled registry source')
 file.file.seek(0);digest=hashlib.sha256();size=0;prefix=b''
 while True:
  chunk=file.file.read(1024*1024)
  if not chunk:break
  if size==0:prefix=chunk[:4096]
  size+=len(chunk)
  if size>settings.max_upload_bytes:raise HTTPException(413,'File exceeds configured upload limit')
  digest.update(chunk)
 if size==0:raise HTTPException(400,'Uploaded file is empty')
 if suffix=='.pdf' and not prefix.startswith(b'%PDF-'):raise HTTPException(415,'File extension is PDF but the file signature is invalid')
 if suffix=='.xlsx' and not prefix.startswith(b'PK\x03\x04'):raise HTTPException(415,'File extension is XLSX but the file signature is invalid')
 if suffix=='.csv' and b'\x00' in prefix:raise HTTPException(415,'CSV contains binary data')
 file.file.seek(0)
 content_type='application/pdf' if suffix=='.pdf' else ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if suffix=='.xlsx' else 'text/csv')
 job=IngestionJob(file_name=name,correlation_id=correlation_id,content_type=content_type,status='QUEUED',source_id=source.id if source else None,source_name=source.source_key if source else 'uploaded_dataset',idempotency_key=idempotency_key)
 db.add(job);db.flush()
 key=f'registry-uploads/{job.id}/{uuid.uuid4().hex}-{name}'
 try:
  upload_fileobj(key,file.file,content_type)
  job.object_key=key
  db.add(WarehouseRawImport(ingestion_job_id=job.id,object_key=key,original_filename=name,content_type=content_type,byte_size=size,sha256_hex=digest.hexdigest(),source_id=source.id if source else None,source_name=source.source_key if source else 'uploaded_dataset',uploaded_by='internal-service',import_status='QUEUED',metadata_json={'correlation_id':correlation_id,'file_suffix':suffix}))
  db.add(AuditLog(action='registry_ingestion_queued',actor='internal-service',file_name=name,details={'job_id':job.id,'source_key':source.source_key if source else None,'correlation_id':correlation_id}))
  db.commit();db.refresh(job)
  return {'job_id':job.id,'file_name':job.file_name,'correlation_id':job.correlation_id,'status':job.status,'records_processed':0,'records_inserted':0,'records_updated':0,'records_skipped':0,'message':'Upload stored; a worker will process this job asynchronously.'}
 except StorageNotConfigured as exc:db.rollback();raise HTTPException(503,'Object storage is not configured') from exc
 except Exception as exc:
  db.rollback();log.exception('ingestion_upload_queue_failed',correlation_id=correlation_id)
  raise HTTPException(502,'Unable to store or queue upload') from exc
@router.get('/api/v1/ingestion/jobs',dependencies=[Depends(require_api_key)])
def jobs(page:int=Query(default=1,ge=1),page_size:int=Query(default=25,ge=1,le=100),db:Session=Depends(get_db)):
 rows=db.scalars(select(IngestionJob).order_by(IngestionJob.created_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
 return {'items':[{'id':j.id,'file_name':j.file_name,'correlation_id':j.correlation_id,'status':j.status,'attempts':j.attempts,'source_name':j.source_name,'records_processed':j.records_processed,'records_inserted':j.records_inserted,'records_updated':j.records_updated,'records_skipped':j.records_skipped,'error_summary':j.error_summary,'created_at':j.created_at.isoformat() if j.created_at else None,'started_at':j.started_at.isoformat() if j.started_at else None,'completed_at':j.completed_at.isoformat() if j.completed_at else None} for j in rows]}
@router.post('/api/v1/ingestion/jobs/{job_id}/retry',dependencies=[Depends(require_api_key)])
def retry_ingestion_job(job_id:str,db:Session=Depends(get_db)):
 job=db.get(IngestionJob,job_id)
 if not job:raise HTTPException(404,'Ingestion job not found')
 if job.status in {'QUEUED','PROCESSING'}:return {'job_id':job.id,'status':job.status,'idempotent_replay':True}
 if job.status!='FAILED':raise HTTPException(409,detail={'code':'JOB_NOT_RETRYABLE','message':'Only failed ingestion jobs can be retried. PDF manual-review jobs cannot be retried as tabular imports.'})
 if not job.object_key:raise HTTPException(409,detail={'code':'JOB_SOURCE_MISSING','message':'The original source object is not available.'})
 suffix='.'+job.file_name.rsplit('.',1)[-1].lower() if '.' in job.file_name else ''
 if suffix not in {'.csv','.xlsx'}:raise HTTPException(409,detail={'code':'MANUAL_REVIEW_REQUIRED','message':'This file type is not eligible for automatic reprocessing.'})
 raw=db.scalar(select(WarehouseRawImport).where(WarehouseRawImport.ingestion_job_id==job.id))
 if raw:raw.import_status='QUEUED'
 job.status='QUEUED';job.next_attempt_at=None;job.completed_at=None;job.error_summary=None
 db.add(AuditLog(action='registry_ingestion_manual_retry',actor='internal-service',file_name=job.file_name,details={'job_id':job.id,'correlation_id':job.correlation_id,'resume_from_row':job.last_processed_row or 1}))
 db.commit()
 return {'job_id':job.id,'status':job.status,'resume_from_row':job.last_processed_row or 1,'message':'Job queued for retry. Persisted row progress is retained so processing can resume safely.'}

@router.get('/api/v1/ingestion/jobs/{job_id}/errors',dependencies=[Depends(require_api_key)])
def job_errors(job_id:str,page:int=Query(default=1,ge=1),page_size:int=Query(default=100,ge=1,le=500),db:Session=Depends(get_db)):
 if not db.get(IngestionJob,job_id):raise HTTPException(404,'Ingestion job not found')
 stmt=select(IngestionRowError).where(IngestionRowError.job_id==job_id)
 total=db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
 rows=db.scalars(stmt.order_by(IngestionRowError.row_number).offset((page-1)*page_size).limit(page_size)).all()
 return {'job_id':job_id,'total':total,'page':page,'page_size':page_size,'items':[{'row_number':r.row_number,'error_code':r.error_code,'message':r.message,'created_at':r.created_at.isoformat() if r.created_at else None} for r in rows]}
def _quality_summary(db: Session):
 total = db.scalar(select(func.count()).select_from(Organization)) or 0
 missing_identifiers = db.scalar(select(func.count()).select_from(Organization).where(
  Organization.normalized_registration_number.is_(None), Organization.normalized_tax_pin.is_(None))) or 0
 duplicate_candidates = db.scalar(select(func.count()).select_from(Organization).where(
  Organization.data_quality_status == 'POSSIBLE_DUPLICATE_REVIEW')) or 0
 pct = lambda count: round((count / total) * 100, 2) if total else 0.0
 identified = max(0, total - missing_identifiers)
 return {
  'total_records': total,
  'identified_records': identified,
  'missing_identifier_records': missing_identifiers,
  'possible_duplicate_records': duplicate_candidates,
  'valid_percentage': pct(identified),
  'missing_percentage': pct(missing_identifiers),
  'duplicate_percentage': pct(duplicate_candidates),
  'definitions': {
   'valid_percentage': 'Share of records with at least one normalized registration number or tax PIN; this is identifier coverage, not legal verification.',
   'missing_percentage': 'Share of records missing both normalized registration number and tax PIN.',
   'duplicate_percentage': 'Share of records already flagged POSSIBLE_DUPLICATE_REVIEW by ingestion; not a complete duplicate scan.'
  }
 }

@router.get('/api/v1/quality/summary',dependencies=[Depends(require_api_key)])
def quality_summary(db:Session=Depends(get_db)):
 return _quality_summary(db)

@router.get('/api/v1/audit/logs',dependencies=[Depends(require_api_key)])
def list_audit_logs(page:int=Query(default=1,ge=1),page_size:int=Query(default=50,ge=1,le=200),action:str|None=None,db:Session=Depends(get_db)):
 stmt=select(AuditLog)
 if action:stmt=stmt.where(AuditLog.action==action[:100])
 total=db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
 rows=db.scalars(stmt.order_by(AuditLog.created_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
 return {'items':[{'id':row.id,'action':row.action,'actor':row.actor,'file_name':row.file_name,'details':row.details or {},'created_at':row.created_at.isoformat() if row.created_at else None} for row in rows],'total':total,'page':page,'page_size':page_size}

@router.get('/api/v1/metrics/summary',dependencies=[Depends(require_api_key)])
def metrics(db:Session=Depends(get_db)):
 return {'total_organizations':db.scalar(select(func.count()).select_from(Organization)) or 0,'total_jobs':db.scalar(select(func.count()).select_from(IngestionJob)) or 0,'queued_jobs':db.scalar(select(func.count()).select_from(IngestionJob).where(IngestionJob.status=='QUEUED')) or 0,'processing_jobs':db.scalar(select(func.count()).select_from(IngestionJob).where(IngestionJob.status=='PROCESSING')) or 0,'completed_jobs':db.scalar(select(func.count()).select_from(IngestionJob).where(IngestionJob.status.in_(['COMPLETED','COMPLETED_WITH_ERRORS']))) or 0,'failed_jobs':db.scalar(select(func.count()).select_from(IngestionJob).where(IngestionJob.status=='FAILED')) or 0,'data_quality':_quality_summary(db)}
@router.get('/api/v1/exports/organizations.csv',dependencies=[Depends(require_api_key)])
def export_csv(db:Session=Depends(get_db)):
 def stream():
  buffer=io.StringIO();writer=csv.writer(buffer);writer.writerow(['legal_name','registration_number','tax_pin','status','source_name','source_file','source_row','data_quality_status']);yield buffer.getvalue();buffer.seek(0);buffer.truncate(0)
  for o in db.scalars(select(Organization).order_by(Organization.legal_name).yield_per(500)):
   vals=[o.legal_name,o.registration_number or '',o.tax_pin or '',o.status,o.source_name or '',o.source_file or '',o.source_row or '',o.data_quality_status]
   safe=["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\\t','\\r')) else v for v in vals]
   writer.writerow(safe);yield buffer.getvalue();buffer.seek(0);buffer.truncate(0)
 return StreamingResponse(stream(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=pesaguard-registry-export.csv'})

@router.get('/api/v1/warehouse/query-organization',dependencies=[Depends(require_api_key)])
def query_organization(registration_number:str|None=None,tax_pin:str|None=None,legal_name:str|None=None,db:Session=Depends(get_db)):
 supplied=[bool(registration_number and registration_number.strip()),bool(tax_pin and tax_pin.strip()),bool(legal_name and legal_name.strip())]
 if sum(supplied)!=1:raise HTTPException(422,'Provide exactly one of registration_number, tax_pin, or legal_name')
 if registration_number or tax_pin:
  from .ingestion.normalizer import normalize_identifier
  ident=normalize_identifier(registration_number or tax_pin)
  col=Organization.normalized_registration_number if registration_number else Organization.normalized_tax_pin
  org=db.scalar(select(Organization).where(col==ident).limit(1))
  if org:return {'found':True,'match_type':'exact_identifier','organization':org_out(org),'fallback_required':False,'fallback_provider_candidates':[],'verification_note':'Imported data is not authoritative verification.'}
  return {'found':False,'match_type':'none','organization':None,'fallback_required':True,'fallback_provider_candidates':['Dojah','Verifisha'],'provider_status':'NOT_CONFIGURED','message':'No local exact match. PesaGuard may invoke a separately configured external verification provider.'}
 result=search(q=legal_name,limit=10,db=db)
 items=result['items']
 return {'found':bool(items),'match_type':result['match_mode'],'candidates':items,'organization':items[0] if len(items)==1 else None,'fallback_required':not bool(items),'fallback_provider_candidates':['Dojah','Verifisha'] if not items else [],'provider_status':'NOT_CONFIGURED' if not items else None,'warning':'Name-based matches are candidates, not identity verification.'}
@router.get('/api/v1/warehouse/health/telemetry',dependencies=[Depends(require_api_key)])
def warehouse_telemetry(db:Session=Depends(get_db)):
 return {'status':'ok','indexed_organizations':db.scalar(select(func.count()).select_from(Organization)) or 0,'raw_files':db.scalar(select(func.count()).select_from(WarehouseRawImport)) or 0,'query_logs':db.scalar(select(func.count()).select_from(WarehouseAccessLog)) or 0,'queued_imports':db.scalar(select(func.count()).select_from(WarehouseRawImport).where(WarehouseRawImport.import_status=='QUEUED')) or 0,'failed_imports':db.scalar(select(func.count()).select_from(WarehouseRawImport).where(WarehouseRawImport.import_status=='FAILED')) or 0,'storage_usage_bytes':db.scalar(select(func.coalesce(func.sum(WarehouseRawImport.byte_size),0))) or 0,'storage_usage_note':'Byte total is based on recorded uploads, not a live R2 bucket inventory.','generated_at':datetime.now(timezone.utc).isoformat()}
