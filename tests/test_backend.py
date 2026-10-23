import os,uuid
os.environ.setdefault('REGISTRY_API_KEYS','test-secret-key')
os.environ.setdefault('DATABASE_URL','sqlite:///./test_registry.db')
from fastapi.testclient import TestClient
from src.main import app
from src.ingestion.normalizer import normalize_legal_name,normalize_identifier,normalize_record
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
def test_csv_ingestion_tracks_upsert_and_provenance():
 reg='TEST'+uuid.uuid4().hex[:12].upper()
 csv_data=f'Company Name,Registration No,Tax PIN\nFirst Example Limited,{reg},P000001\nUpdated Example Limited,{reg},P000001\n'
 response=client.post('/api/v1/ingestion/uploads',headers=HEADERS,files={'file':('organizations.csv',csv_data,'text/csv')})
 assert response.status_code==200,response.text
 job=response.json()
 assert job['records_processed']==2
 assert job['records_inserted']==1
 assert job['records_updated']==1
 assert job['records_skipped']==0
 lookup=client.get('/api/v1/registry/lookup',params={'reg_no':reg},headers=HEADERS)
 assert lookup.status_code==200
 body=lookup.json()
 assert body['found'] is True
 assert body['organization']['legal_name']=='Updated Example Limited'
 assert body['organization']['data_quality_status']=='IMPORTED_UNVERIFIED'
 assert body['organization']['source']['file']=='organizations.csv'
