import os,uuid
os.environ.setdefault('REGISTRY_API_KEYS','test-secret-key')
os.environ.setdefault('DATABASE_URL','sqlite:///./test_registry.db')
from fastapi.testclient import TestClient
from sqlalchemy import select
from src.main import app
from src.database import Base, engine, SessionLocal
Base.metadata.create_all(bind=engine)
from src.ingestion.normalizer import normalize_legal_name,normalize_identifier,normalize_record
from src import worker
from src.config import settings
from src.worker import process_job
from src.models import Organization, IngestionRowError
client=TestClient(app)
HEADERS={'X-API-Key':'test-secret-key'}
def test_health_live():
 r=client.get('/health/live');assert r.status_code==200 and r.json()['status']=='alive'
def test_lookup_requires_key():
 assert client.get('/api/v1/registry/lookup?reg_no=ABC123').status_code==401
def test_lookup_key_returns_not_found():
 r=client.get('/api/v1/registry/lookup?reg_no=NOT-IN-TEST-DATA',headers=HEADERS);assert r.status_code==200 and r.json()['found'] is False
def test_normalizers():
 assert normalize_legal_name('  Acme   limited ' )=='ACME LIMITED';assert normalize_identifier('ab- 123')=='AB123'
def test_header_aliases():
 r=normalize_record({'Company Name':'Example Limited','Registration No':'PVT-123'});assert r['normalized_legal_name']=='EXAMPLE LIMITED';assert r['normalized_registration_number']=='PVT123'
def test_name_required():
 try:normalize_record({'Registration No':'123'})
 except ValueError as exc:assert 'legal name' in str(exc).lower()
 else:raise AssertionError('Expected missing legal name validation')
def test_csv_ingestion_is_queued_then_processed_with_provenance(monkeypatch):
 reg='TEST'+uuid.uuid4().hex[:12].upper()
 csv_data=f'Company Name,Registration No,Tax PIN\nFirst Example Limited,{reg},P000001\nUpdated Example Limited,{reg},P000001\n,INVALID-ROW,P000002\n'
 correlation_id='test-correlation-'+uuid.uuid4().hex
 response=client.post('/api/v1/ingestion/uploads',headers={**HEADERS,'Idempotency-Key':'test-'+uuid.uuid4().hex,'X-Correlation-ID':correlation_id},files={'file':('organizations.csv',csv_data,'text/csv')})
 assert response.status_code==202,response.text
 job=response.json()
 assert job['status']=='QUEUED'
 assert job['correlation_id']==correlation_id
 old_batch_size=settings.ingestion_batch_size
 original_normalize=worker.normalize_record
 def fail_once_on_malformed_row(row):
  if not row.get('Company Name'):
   raise RuntimeError('simulated transient worker failure')
  return original_normalize(row)
 settings.ingestion_batch_size=2
 monkeypatch.setattr(worker,'normalize_record',fail_once_on_malformed_row)
 try:
  process_job(job['job_id'])
 finally:
  settings.ingestion_batch_size=old_batch_size
 monkeypatch.setattr(worker,'normalize_record',original_normalize)
 jobs=client.get('/api/v1/ingestion/jobs',headers=HEADERS).json()['items']
 partial=next(j for j in jobs if j['id']==job['job_id'])
 assert partial['status']=='QUEUED'
 process_job(job['job_id'])
 jobs=client.get('/api/v1/ingestion/jobs',headers=HEADERS).json()['items']
 completed=next(j for j in jobs if j['id']==job['job_id'])
 assert completed['records_processed']==3
 assert completed['records_inserted']==1
 assert completed['records_updated']==1
 assert completed['records_skipped']==1
 assert completed['status']=='COMPLETED_WITH_ERRORS'
 lookup=client.get('/api/v1/registry/lookup',params={'reg_no':reg},headers=HEADERS)
 assert lookup.status_code==200
 body=lookup.json()
 assert body['found'] is True
 assert body['organization']['legal_name']=='Updated Example Limited'
 assert body['organization']['data_quality_status']=='IMPORTED_UNVERIFIED'
 assert body['organization']['source']['file']=='organizations.csv'
 errors=client.get(f"/api/v1/ingestion/jobs/{job['job_id']}/errors",headers=HEADERS)
 assert errors.status_code==200 and errors.json()['total']==1
def test_source_catalogue_create_and_list():
 key='test-source-'+uuid.uuid4().hex[:8]
 created=client.post('/api/v1/sources',headers=HEADERS,json={'source_key':key,'display_name':'Test dataset','jurisdiction':'KE','licence_reference':'test licence','freshness_sla_hours':24})
 assert created.status_code==201,created.text
 assert created.json()['source_key']==key
 listed=client.get('/api/v1/sources',headers=HEADERS)
 assert any(x['source_key']==key for x in listed.json()['items'])
def test_upload_rejects_unknown_type():
 response=client.post('/api/v1/ingestion/uploads',headers=HEADERS,files={'file':('payload.exe',b'no','application/octet-stream')})
 assert response.status_code==415


def test_large_direct_upload_requires_private_r2_configuration():
 response=client.post('/api/v1/ingestion/uploads/presign',headers=HEADERS,json={'file_name':'large-dataset.csv','size_bytes':100*1024*1024})
 assert response.status_code==503


def test_conflicting_identifiers_are_dead_lettered_without_duplicate_org(monkeypatch, tmp_path):
 reg = 'REG' + uuid.uuid4().hex[:12].upper()
 pin = 'PIN' + uuid.uuid4().hex[:12].upper()
 monkeypatch.setattr(settings, 'local_storage_path', str(tmp_path))

 first_csv = f'Company Name,Registration No,Tax PIN\\nConflict Alpha Limited,{reg},{pin}\\n'
 first_response = client.post(
  '/api/v1/ingestion/uploads',
  headers={**HEADERS, 'Idempotency-Key': 'conflict-seed-' + uuid.uuid4().hex},
  files={'file': ('conflict-seed.csv', first_csv, 'text/csv')},
 )
 assert first_response.status_code == 202, first_response.text
 process_job(first_response.json()['job_id'])

 second_reg = 'REG' + uuid.uuid4().hex[:12].upper()
 second_csv = f'Company Name,Registration No,Tax PIN\\nConflict Alpha Changed Limited,{second_reg},{pin}\\n'
 second_response = client.post(
  '/api/v1/ingestion/uploads',
  headers={**HEADERS, 'Idempotency-Key': 'conflict-check-' + uuid.uuid4().hex},
  files={'file': ('conflict-check.csv', second_csv, 'text/csv')},
 )
 assert second_response.status_code == 202, second_response.text
 process_job(second_response.json()['job_id'])

 job_id = second_response.json()['job_id']
 with SessionLocal() as db:
  records = db.scalars(select(Organization).where(Organization.normalized_tax_pin == pin)).all()
  error = db.scalar(select(IngestionRowError).where(IngestionRowError.job_id == job_id))
  assert len(records) == 1
  assert records[0].normalized_registration_number == reg
  assert records[0].legal_name == 'Conflict Alpha Limited'
  assert error is not None
  assert error.error_code == 'IDENTIFIER_CONFLICT'

 job_response = client.get('/api/v1/ingestion/jobs', headers=HEADERS)
 job = next(item for item in job_response.json()['items'] if item['id'] == job_id)
 assert job['status'] == 'COMPLETED_WITH_ERRORS'
 assert job['records_inserted'] == 0
 assert job['records_skipped'] == 1
