import copy
import csv
import hashlib
import io
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .cache import get_json, set_json
from .config import settings
from .database import SessionLocal, get_db
from .ingestion.normalizer import normalize_identifier, normalize_legal_name
from .models import (AuditLog, IngestionJob, IngestionRowError, Organization, RegistrySource,
                     WarehouseAccessLog, WarehouseRawImport)
from .security import is_customer_identity, require_api_key
from .storage import (StorageNotConfigured, delete_object, head_object, presign_upload_url,
                      read_object_prefix, upload_fileobj)

router = APIRouter()
log = structlog.get_logger(__name__)

UPLOAD_SLACK_BYTES = 1024 * 1024
FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r', '\n')
COMPLETED_STATUSES = ['COMPLETED', 'COMPLETED_WITH_ERRORS']


# ---------------------------------------------------------------- presentation helpers
def _mask_pin(value):
    if not value:
        return value
    return '*' * max(0, len(value) - 2) + value[-2:]


def _mask_payload(payload):
    return {k: ('[REDACTED]' if ('pin' in k.lower() or 'tax' in k.lower()) else v) for k, v in (payload or {}).items()}


def org_out(o, mask=False):
    """Serialize an organization. Customer-facing callers get masked tax identifiers."""
    return {
        'id': o.id, 'legal_name': o.legal_name, 'registration_number': o.registration_number,
        'tax_pin': _mask_pin(o.tax_pin) if mask else o.tax_pin, 'status': o.status,
        'registry_payload': _mask_payload(o.registry_payload) if mask else (o.registry_payload or {}),
        'source': {'name': o.source_name, 'file': o.source_file, 'row': o.source_row, 'record_id': o.source_record_id,
                   'published_at': o.source_published_at.isoformat() if o.source_published_at else None},
        'data_quality_status': o.data_quality_status,
        'last_seen_at': o.last_seen_at.isoformat() if o.last_seen_at else None,
        'created_at': o.created_at.isoformat() if o.created_at else None,
        'updated_at': o.updated_at.isoformat() if o.updated_at else None,
    }


def _as_utc(value):
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def source_out(s, last_import=None):
    last_import = _as_utc(last_import)
    if s.freshness_sla_hours is None:
        freshness = 'no_sla'
    elif last_import is None:
        freshness = 'never_imported'
    else:
        age_hours = (datetime.now(timezone.utc) - last_import).total_seconds() / 3600
        freshness = 'stale' if age_hours > s.freshness_sla_hours else 'fresh'
    return {'id': s.id, 'source_key': s.source_key, 'display_name': s.display_name, 'jurisdiction': s.jurisdiction,
            'source_type': s.source_type, 'authority_url': s.authority_url, 'licence_reference': s.licence_reference,
            'freshness_sla_hours': s.freshness_sla_hours, 'precedence': s.precedence, 'enabled': s.enabled,
            'notes': s.notes, 'last_successful_import_at': last_import.isoformat() if last_import else None,
            'freshness_status': freshness,
            'created_at': s.created_at.isoformat() if s.created_at else None,
            'updated_at': s.updated_at.isoformat() if s.updated_at else None}


def _like(text):
    """Contains-pattern with LIKE wildcards in user input escaped."""
    return '%' + text.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'


def _csv_safe(value):
    """Neutralise spreadsheet formula injection for text cells."""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def _correlation(request, correlation_id):
    return (correlation_id or getattr(request.state, 'request_id', None) or str(uuid.uuid4()))[:100]


def _clean_name(file_name):
    return (file_name or 'upload.csv').replace(chr(92), '/').split('/')[-1]


def _suffix(name):
    return '.' + name.rsplit('.', 1)[-1].lower() if '.' in name else ''


# ---------------------------------------------------------------- lookup and search
def _lookup_identifier(db, kind, ident):
    cache_key = f'registry:lookup:{kind}:{ident}'
    cached = get_json(cache_key)
    if cached is not None:
        if cached.get('_cache_not_found'):
            return None
        return cached
    col = Organization.normalized_registration_number if kind == 'reg' else Organization.normalized_tax_pin
    org = db.scalar(select(Organization).where(col == ident).limit(1))
    if not org:
        set_json(cache_key, {'_cache_not_found': True}, settings.registry_cache_negative_ttl_seconds)
        return None
    result = {'status': 'record_found', 'found': True, 'match_type': 'exact_identifier', 'organization': org_out(org),
              'source': 'internal_registry', 'last_imported_at': org.updated_at.isoformat() if org.updated_at else None,
              'verification_note': 'Imported registry data is evidence for review, not authoritative verification by itself.'}
    set_json(cache_key, result, settings.registry_cache_ttl_seconds)
    return result


def _present_lookup(result, mask):
    """Cache holds the unmasked record; masking is applied per caller on the way out."""
    if result is None:
        return {'status': 'not_found', 'found': False, 'organization': None, 'source': 'internal_registry'}
    if not mask:
        return result
    masked = copy.deepcopy(result)
    org = result['organization']
    masked['organization'] = {**org, 'tax_pin': _mask_pin(org.get('tax_pin')), 'registry_payload': _mask_payload(org.get('registry_payload'))}
    return masked


@router.get('/api/v1/registry/lookup')
def lookup(reg_no: str | None = None, tax_pin: str | None = None, db: Session = Depends(get_db), caller: str = Depends(require_api_key)):
    if bool(reg_no) == bool(tax_pin):
        raise HTTPException(422, 'Provide exactly one of reg_no or tax_pin')
    ident = normalize_identifier(reg_no or tax_pin)
    if not ident:
        raise HTTPException(422, 'Identifier must contain letters or digits')
    result = _lookup_identifier(db, 'reg' if reg_no else 'pin', ident)
    return _present_lookup(result, is_customer_identity(caller))

@router.post('/api/v1/registry/lookup')
def lookup_post(payload: dict, db: Session = Depends(get_db), caller: str = Depends(require_api_key)):
    """POST variant keeps registration numbers and tax PINs out of URL/access logs."""
    reg_no = payload.get('reg_no')
    tax_pin = payload.get('tax_pin')
    if reg_no is not None and not isinstance(reg_no, str):
        raise HTTPException(422, 'reg_no must be a string')
    if tax_pin is not None and not isinstance(tax_pin, str):
        raise HTTPException(422, 'tax_pin must be a string')
    if bool((reg_no or '').strip()) == bool((tax_pin or '').strip()):
        raise HTTPException(422, 'Provide exactly one of reg_no or tax_pin')
    ident = normalize_identifier(reg_no or tax_pin)
    if not ident:
        raise HTTPException(422, 'Identifier must contain letters or digits')
    if len(ident) > 128:
        raise HTTPException(422, 'Identifier is too long')
    result = _lookup_identifier(db, 'reg' if reg_no else 'pin', ident)
    return _present_lookup(result, is_customer_identity(caller))


def _search(db, q, limit, mask):
    norm = normalize_legal_name(q) or ''
    if not norm:
        raise HTTPException(422, 'Query must contain searchable characters')
    rows = db.scalars(select(Organization).where(Organization.normalized_legal_name.ilike(_like(norm), escape='\\'))
                      .order_by(Organization.normalized_legal_name).limit(limit)).all()
    mode = 'substring' if rows else 'no_match'
    if not rows and db.get_bind().dialect.name == 'postgresql':
        similarity = func.similarity(Organization.normalized_legal_name, norm)
        rows = db.scalars(select(Organization).where(similarity >= 0.25).order_by(similarity.desc()).limit(limit)).all()
        if rows:
            mode = 'postgres_trigram'
    return {'items': [org_out(o, mask) for o in rows], 'count': len(rows), 'query': q, 'match_mode': mode,
            'warning': 'Name matches are candidates for review, not identity verification.'}


@router.get('/api/v1/registry/search')
def search(q: str = Query(min_length=2, max_length=200), limit: int = Query(default=20, ge=1, le=100),
           db: Session = Depends(get_db), caller: str = Depends(require_api_key)):
    return _search(db, q, limit, is_customer_identity(caller))


@router.get('/api/v1/organizations')
def list_orgs(page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100), q: str | None = None,
              db: Session = Depends(get_db), caller: str = Depends(require_api_key)):
    stmt = select(Organization)
    if q and q.strip():
        norm = normalize_legal_name(q) or ''
        ident = normalize_identifier(q) or ''
        conditions = []
        if norm:
            conditions.append(Organization.normalized_legal_name.ilike(_like(norm), escape='\\'))
        if ident:
            conditions.append(Organization.normalized_registration_number.ilike(_like(ident), escape='\\'))
        if not conditions:
            raise HTTPException(422, 'Query must contain searchable characters')
        stmt = stmt.where(or_(*conditions))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Organization.legal_name).offset((page - 1) * page_size).limit(page_size)).all()
    mask = is_customer_identity(caller)
    return {'items': [org_out(o, mask) for o in rows], 'total': total, 'page': page, 'page_size': page_size}


# ---------------------------------------------------------------- sources
class SourceCreate(BaseModel):
    source_key: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    jurisdiction: str = Field(default='KE', max_length=100)
    source_type: str = Field(default='IMPORTED_DATASET', max_length=40)
    authority_url: str | None = Field(default=None, max_length=1000)
    licence_reference: str | None = Field(default=None, max_length=500)
    freshness_sla_hours: int | None = Field(default=None, ge=1, le=24 * 365)
    precedence: int = Field(default=100, ge=0, le=10000)
    enabled: bool = True
    notes: str | None = Field(default=None, max_length=10000)

    @field_validator('source_key')
    @classmethod
    def _key(cls, value):
        value = value.strip().lower()
        if not value or not all(c.isalnum() or c in '-_' for c in value):
            raise ValueError('source_key must contain only letters, numbers, hyphens or underscores')
        return value

    @field_validator('display_name')
    @classmethod
    def _name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('display_name is required')
        return value

    @field_validator('authority_url')
    @classmethod
    def _url(cls, value):
        if value and not value.lower().startswith(('http://', 'https://')):
            raise ValueError('authority_url must be an http(s) URL')
        return value


@router.get('/api/v1/sources', dependencies=[Depends(require_api_key)])
def list_sources(enabled_only: bool = False, db: Session = Depends(get_db)):
    stmt = select(RegistrySource)
    if enabled_only:
        stmt = stmt.where(RegistrySource.enabled.is_(True))
    rows = db.scalars(stmt.order_by(RegistrySource.precedence, RegistrySource.display_name)).all()
    last_imports = dict(db.execute(
        select(IngestionJob.source_id, func.max(IngestionJob.completed_at))
        .where(IngestionJob.status.in_(COMPLETED_STATUSES), IngestionJob.source_id.is_not(None))
        .group_by(IngestionJob.source_id)).all())
    return {'items': [source_out(s, last_imports.get(s.id)) for s in rows], 'count': len(rows)}


@router.post('/api/v1/sources', dependencies=[Depends(require_api_key)], status_code=201)
def create_source(payload: SourceCreate, db: Session = Depends(get_db)):
    if db.scalar(select(RegistrySource).where(RegistrySource.source_key == payload.source_key)):
        raise HTTPException(409, 'source_key already exists')
    source = RegistrySource(**payload.model_dump())
    db.add(source)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'source_key already exists')
    db.refresh(source)
    return source_out(source)


# ---------------------------------------------------------------- direct (presigned) uploads
class DirectUploadRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=500)
    size_bytes: int = Field(gt=0)


def _fail_direct_upload(db, job, raw, summary):
    job.status = 'FAILED'
    job.error_summary = summary
    job.completed_at = datetime.now(timezone.utc)
    raw.import_status = 'FAILED'
    db.commit()
    if job.object_key:
        delete_object(job.object_key)  # do not leave rejected objects in the bucket


@router.post('/api/v1/ingestion/uploads/presign', dependencies=[Depends(require_api_key)], status_code=201)
def presign_direct_upload(payload: DirectUploadRequest, request: Request, db: Session = Depends(get_db),
                          correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
                          idempotency_key: str | None = Header(default=None, alias='Idempotency-Key')):
    name = _clean_name(payload.file_name)
    suffix = _suffix(name)
    if suffix not in {'.csv', '.pdf'}:
        raise HTTPException(415, 'Only CSV and PDF files are accepted')
    if payload.size_bytes > settings.max_direct_upload_bytes:
        raise HTTPException(413, 'File exceeds configured direct-upload limit')
    content_type = 'application/pdf' if suffix == '.pdf' else 'text/csv'
    correlation_id = _correlation(request, correlation_id)
    ttl = settings.direct_upload_url_ttl_seconds
    if idempotency_key:
        prior = db.scalar(select(IngestionJob).where(IngestionJob.idempotency_key == idempotency_key))
        if prior:
            raw = db.scalar(select(WarehouseRawImport).where(WarehouseRawImport.ingestion_job_id == prior.id))
            if prior.status != 'UPLOADING' or not raw or raw.byte_size != payload.size_bytes or prior.file_name != name or prior.content_type != content_type:
                raise HTTPException(409, 'Idempotency key is already associated with a different or completed upload')
            try:
                url = presign_upload_url(prior.object_key, content_type, ttl, payload.size_bytes)
            except StorageNotConfigured as exc:
                raise HTTPException(503, 'Direct object storage is not configured') from exc
            return {'job_id': prior.id, 'status': prior.status, 'upload_url': url, 'content_type': content_type,
                    'expires_in_seconds': ttl, 'idempotent_replay': True}
    job = IngestionJob(file_name=name, correlation_id=correlation_id, content_type=content_type, status='UPLOADING',
                       source_name='direct_r2_upload', idempotency_key=idempotency_key)
    db.add(job)
    db.flush()
    key = f'registry-uploads/{job.id}/{uuid.uuid4().hex}-{name}'
    try:
        url = presign_upload_url(key, content_type, ttl, payload.size_bytes)
    except StorageNotConfigured as exc:
        db.rollback()
        raise HTTPException(503, 'Direct object storage is not configured') from exc
    job.object_key = key
    expires_at = int(datetime.now(timezone.utc).timestamp()) + ttl
    db.add(WarehouseRawImport(ingestion_job_id=job.id, object_key=key, original_filename=name, content_type=content_type,
                              byte_size=payload.size_bytes, source_name='direct_r2_upload', uploaded_by='internal-service',
                              import_status='UPLOADING',
                              metadata_json={'correlation_id': correlation_id, 'file_suffix': suffix, 'upload_expires_at': expires_at, 'direct_upload': True}))
    db.add(AuditLog(action='registry_direct_upload_presigned', actor='internal-service', file_name=name,
                    details={'job_id': job.id, 'correlation_id': correlation_id, 'expected_size_bytes': payload.size_bytes}))
    db.commit()
    return {'job_id': job.id, 'status': job.status, 'upload_url': url, 'content_type': content_type,
            'expires_in_seconds': ttl, 'idempotent_replay': False}


@router.post('/api/v1/ingestion/uploads/{job_id}/complete', dependencies=[Depends(require_api_key)])
def complete_direct_upload(job_id: str, db: Session = Depends(get_db)):
    job = db.get(IngestionJob, job_id)
    if not job:
        raise HTTPException(404, 'Ingestion job not found')
    if job.status != 'UPLOADING':
        return {'job_id': job.id, 'status': job.status, 'idempotent_replay': True}
    raw = db.scalar(select(WarehouseRawImport).where(WarehouseRawImport.ingestion_job_id == job.id))
    if not raw:
        raise HTTPException(409, 'Upload metadata is missing')
    if int((raw.metadata_json or {}).get('upload_expires_at', 0)) < int(datetime.now(timezone.utc).timestamp()):
        _fail_direct_upload(db, job, raw, 'Direct upload URL expired before completion.')
        raise HTTPException(410, 'Direct upload expired; create a new upload job')
    try:
        metadata = head_object(job.object_key)
    except StorageNotConfigured as exc:
        raise HTTPException(503, 'Direct object storage is not configured') from exc
    except Exception as exc:
        raise HTTPException(502, 'Unable to verify uploaded object') from exc
    actual_size = int(metadata.get('ContentLength', 0) or 0)
    if actual_size <= 0 or actual_size > settings.max_direct_upload_bytes or actual_size != raw.byte_size:
        _fail_direct_upload(db, job, raw, 'Uploaded object size did not match the declared size.')
        raise HTTPException(422, 'Uploaded object size did not match the declared size')
    try:
        prefix = read_object_prefix(job.object_key, 4096)
    except Exception as exc:
        raise HTTPException(502, 'Unable to inspect uploaded object signature') from exc
    suffix = _suffix(job.file_name)
    if suffix == '.pdf' and not prefix.startswith(b'%PDF-'):
        _fail_direct_upload(db, job, raw, 'PDF signature validation failed.')
        raise HTTPException(415, 'PDF file signature is invalid')
    if suffix == '.csv' and b'\x00' in prefix:
        _fail_direct_upload(db, job, raw, 'CSV binary signature validation failed.')
        raise HTTPException(415, 'CSV contains binary data')
    raw.byte_size = actual_size
    raw.import_status = 'QUEUED'
    raw.metadata_json = {**(raw.metadata_json or {}), 'r2_etag': str(metadata.get('ETag', '')).strip('"'),
                         'upload_completed_at': datetime.now(timezone.utc).isoformat()}
    job.status = 'QUEUED'
    job.error_summary = None
    db.add(AuditLog(action='registry_direct_upload_completed', actor='internal-service', file_name=job.file_name,
                    details={'job_id': job.id, 'correlation_id': job.correlation_id, 'byte_size': actual_size}))
    db.commit()
    return {'job_id': job.id, 'status': job.status, 'file_name': job.file_name, 'correlation_id': job.correlation_id,
            'message': 'Object verified in private storage and queued for background processing.'}


# ---------------------------------------------------------------- multipart upload
@router.post('/api/v1/ingestion/uploads', dependencies=[Depends(require_api_key)], status_code=202)
def upload(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db),
           correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
           idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
           source_key: str | None = Header(default=None, alias='X-Registry-Source')):
    # Synchronous handler on purpose: hashing, object storage and database writes are blocking
    # and must run in FastAPI's threadpool, not on the event loop.
    declared = request.headers.get('content-length')
    if declared and declared.isdigit() and int(declared) > settings.max_upload_bytes + UPLOAD_SLACK_BYTES:
        raise HTTPException(413, 'File exceeds configured upload limit')
    correlation_id = _correlation(request, correlation_id)
    name = _clean_name(file.filename)
    suffix = _suffix(name)
    if suffix not in {'.csv', '.pdf'}:
        raise HTTPException(415, 'Only CSV and PDF files are accepted')
    source = None
    if source_key:
        source = db.scalar(select(RegistrySource).where(RegistrySource.source_key == source_key.strip().lower(), RegistrySource.enabled.is_(True)))
        if not source:
            raise HTTPException(422, 'Unknown or disabled registry source')
    file.file.seek(0)
    digest = hashlib.sha256()
    size = 0
    prefix = b''
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        if size == 0:
            prefix = chunk[:4096]
        size += len(chunk)
        if size > settings.max_upload_bytes:
            raise HTTPException(413, 'File exceeds configured upload limit')
        digest.update(chunk)
    if size == 0:
        raise HTTPException(400, 'Uploaded file is empty')
    if suffix == '.pdf' and not prefix.startswith(b'%PDF-'):
        raise HTTPException(415, 'File extension is PDF but the file signature is invalid')
    if suffix == '.csv' and b'\x00' in prefix:
        raise HTTPException(415, 'CSV contains binary data')
    sha256_hex = digest.hexdigest()
    if idempotency_key:
        prior = db.scalar(select(IngestionJob).where(IngestionJob.idempotency_key == idempotency_key))
        if prior:
            return _replay_or_conflict(db, prior, name, sha256_hex)
    file.file.seek(0)
    content_type = file.content_type or 'application/octet-stream'
    job = IngestionJob(file_name=name, correlation_id=correlation_id, content_type=content_type, status='QUEUED',
                       source_id=source.id if source else None, source_name=source.source_key if source else 'uploaded_dataset',
                       idempotency_key=idempotency_key)
    db.add(job)
    db.flush()
    key = f'registry-uploads/{job.id}/{uuid.uuid4().hex}-{name}'
    stored = False
    try:
        upload_fileobj(key, file.file, content_type)
        stored = True
        job.object_key = key
        db.add(WarehouseRawImport(ingestion_job_id=job.id, object_key=key, original_filename=name, content_type=content_type,
                                  byte_size=size, sha256_hex=sha256_hex, source_id=source.id if source else None,
                                  source_name=source.source_key if source else 'uploaded_dataset', uploaded_by='internal-service',
                                  import_status='QUEUED', metadata_json={'correlation_id': correlation_id, 'file_suffix': suffix}))
        db.add(AuditLog(action='registry_ingestion_queued', actor='internal-service', file_name=name,
                        details={'job_id': job.id, 'source_key': source.source_key if source else None, 'correlation_id': correlation_id}))
        db.commit()
        db.refresh(job)
        return {'job_id': job.id, 'file_name': job.file_name, 'correlation_id': job.correlation_id, 'status': job.status,
                'records_processed': 0, 'records_inserted': 0, 'records_updated': 0, 'records_skipped': 0,
                'message': 'Upload stored; a worker will process this job asynchronously.'}
    except StorageNotConfigured as exc:
        db.rollback()
        raise HTTPException(503, 'Object storage is not configured') from exc
    except IntegrityError:
        # A concurrent request used the same Idempotency-Key.
        db.rollback()
        if stored:
            delete_object(key)
        prior = db.scalar(select(IngestionJob).where(IngestionJob.idempotency_key == idempotency_key)) if idempotency_key else None
        if prior:
            return _replay_or_conflict(db, prior, name, sha256_hex)
        raise HTTPException(502, 'Unable to store or queue upload')
    except Exception as exc:
        db.rollback()
        if stored:
            delete_object(key)  # do not orphan the object when the database write failed
        log.exception('ingestion_upload_queue_failed', correlation_id=correlation_id)
        raise HTTPException(502, 'Unable to store or queue upload') from exc


def _replay_or_conflict(db, prior, name, sha256_hex):
    raw = db.scalar(select(WarehouseRawImport).where(WarehouseRawImport.ingestion_job_id == prior.id))
    if prior.file_name == name and raw is not None and raw.sha256_hex == sha256_hex:
        return {'job_id': prior.id, 'status': prior.status, 'idempotent_replay': True}
    raise HTTPException(409, 'Idempotency key is already associated with a different upload')


# ---------------------------------------------------------------- jobs, metrics, export
@router.get('/api/v1/ingestion/jobs', dependencies=[Depends(require_api_key)])
def jobs(page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100), db: Session = Depends(get_db)):
    rows = db.scalars(select(IngestionJob).order_by(IngestionJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {'items': [{'id': j.id, 'file_name': j.file_name, 'correlation_id': j.correlation_id, 'status': j.status,
                       'attempts': j.attempts, 'source_name': j.source_name, 'records_processed': j.records_processed,
                       'records_inserted': j.records_inserted, 'records_updated': j.records_updated,
                       'records_skipped': j.records_skipped, 'error_summary': j.error_summary,
                       'created_at': j.created_at.isoformat() if j.created_at else None,
                       'started_at': j.started_at.isoformat() if j.started_at else None,
                       'completed_at': j.completed_at.isoformat() if j.completed_at else None} for j in rows]}


@router.get('/api/v1/ingestion/jobs/{job_id}/errors', dependencies=[Depends(require_api_key)])
def job_errors(job_id: str, page: int = Query(default=1, ge=1), page_size: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)):
    if not db.get(IngestionJob, job_id):
        raise HTTPException(404, 'Ingestion job not found')
    stmt = select(IngestionRowError).where(IngestionRowError.job_id == job_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(IngestionRowError.row_number).offset((page - 1) * page_size).limit(page_size)).all()
    return {'job_id': job_id, 'total': total, 'page': page, 'page_size': page_size,
            'items': [{'row_number': r.row_number, 'error_code': r.error_code, 'message': r.message,
                       'created_at': r.created_at.isoformat() if r.created_at else None} for r in rows]}


@router.get('/api/v1/metrics/summary', dependencies=[Depends(require_api_key)])
def metrics(db: Session = Depends(get_db)):
    def count_jobs(*conditions):
        return db.scalar(select(func.count()).select_from(IngestionJob).where(*conditions)) or 0
    return {'total_organizations': db.scalar(select(func.count()).select_from(Organization)) or 0,
            'total_jobs': count_jobs(), 'queued_jobs': count_jobs(IngestionJob.status == 'QUEUED'),
            'processing_jobs': count_jobs(IngestionJob.status == 'PROCESSING'),
            'completed_jobs': count_jobs(IngestionJob.status.in_(COMPLETED_STATUSES)),
            'failed_jobs': count_jobs(IngestionJob.status == 'FAILED')}


EXPORT_COLUMNS = ['legal_name', 'registration_number', 'tax_pin', 'status', 'source_name', 'source_file', 'source_row', 'data_quality_status']


@router.get('/api/v1/exports/organizations.csv')
def export_csv(db: Session = Depends(get_db), caller: str = Depends(require_api_key)):
    db.add(AuditLog(action='registry_export_started', actor=str(caller)[:200], details={}))
    db.commit()

    def stream():
        # The request-scoped session may be closed before a streaming body finishes,
        # so the generator owns its session.
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        def flush():
            data = buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            return data

        writer.writerow(EXPORT_COLUMNS)
        yield flush()
        with SessionLocal() as stream_db:
            stmt = select(Organization).order_by(Organization.legal_name).execution_options(yield_per=500)
            for o in stream_db.scalars(stmt):
                values = [o.legal_name, o.registration_number or '', o.tax_pin or '', o.status, o.source_name or '',
                          o.source_file or '', o.source_row or '', o.data_quality_status]
                writer.writerow([_csv_safe(v) for v in values])
                yield flush()

    return StreamingResponse(stream(), media_type='text/csv; charset=utf-8',
                             headers={'Content-Disposition': 'attachment; filename=pesaguard-registry-export.csv'})


# ---------------------------------------------------------------- warehouse
@router.get('/api/v1/warehouse/query-organization')
def query_organization(registration_number: str | None = None, tax_pin: str | None = None, legal_name: str | None = None,
                       db: Session = Depends(get_db), caller: str = Depends(require_api_key)):
    supplied = [bool(registration_number and registration_number.strip()), bool(tax_pin and tax_pin.strip()), bool(legal_name and legal_name.strip())]
    if sum(supplied) != 1:
        raise HTTPException(422, 'Provide exactly one of registration_number, tax_pin, or legal_name')
    mask = is_customer_identity(caller)
    if registration_number or tax_pin:
        ident = normalize_identifier(registration_number or tax_pin)
        if not ident:
            raise HTTPException(422, 'Identifier must contain letters or digits')
        col = Organization.normalized_registration_number if registration_number else Organization.normalized_tax_pin
        org = db.scalar(select(Organization).where(col == ident).limit(1))
        if org:
            return {'found': True, 'match_type': 'exact_identifier', 'organization': org_out(org, mask), 'fallback_required': False,
                    'fallback_provider_candidates': [], 'verification_note': 'Imported data is not authoritative verification.'}
        return {'found': False, 'match_type': 'none', 'organization': None, 'fallback_required': True,
                'fallback_provider_candidates': ['Dojah', 'Verifisha'], 'provider_status': 'NOT_CONFIGURED',
                'message': 'No local exact match. PesaGuard may invoke a separately configured external verification provider.'}
    result = _search(db, legal_name, 10, mask)
    items = result['items']
    return {'found': bool(items), 'match_type': result['match_mode'], 'candidates': items,
            'organization': items[0] if len(items) == 1 else None, 'fallback_required': not bool(items),
            'fallback_provider_candidates': ['Dojah', 'Verifisha'] if not items else [],
            'provider_status': 'NOT_CONFIGURED' if not items else None,
            'warning': 'Name-based matches are candidates, not identity verification.'}


@router.get('/api/v1/warehouse/health/telemetry', dependencies=[Depends(require_api_key)])
def warehouse_telemetry(db: Session = Depends(get_db)):
    def count(model, *conditions):
        return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
    return {'status': 'ok', 'indexed_organizations': count(Organization), 'raw_files': count(WarehouseRawImport),
            'query_logs': count(WarehouseAccessLog),
            'queued_imports': count(WarehouseRawImport, WarehouseRawImport.import_status == 'QUEUED'),
            'failed_imports': count(WarehouseRawImport, WarehouseRawImport.import_status == 'FAILED'),
            'storage_usage_bytes': db.scalar(select(func.coalesce(func.sum(WarehouseRawImport.byte_size), 0))) or 0,
            'storage_usage_note': 'Byte total is based on recorded uploads, not a live R2 bucket inventory.',
            'generated_at': datetime.now(timezone.utc).isoformat()}
