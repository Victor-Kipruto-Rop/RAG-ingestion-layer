import os
os.environ.setdefault('REGISTRY_API_KEYS','test-secret-key')
os.environ.setdefault('DATABASE_URL','sqlite:///./test_registry.db')
from fastapi.testclient import TestClient
from src.main import app
from src.ingestion.normalizer import normalize_legal_name,normalize_identifier,normalize_record
client=TestClient(app)
def test_health_live():
 r=client.get('/health/live');assert r.status_code==200 and r.json()['status']=='alive'
def test_lookup_requires_key():
 assert client.get('/api/v1/registry/lookup?reg_no=ABC123').status_code==401
def test_lookup_key_returns_not_found():
 r=client.get('/api/v1/registry/lookup?reg_no=ABC123',headers={'X-API-Key':'test-secret-key'});assert r.status_code==200 and r.json()['found'] is False
def test_normalizers():
 assert normalize_legal_name('  Acme   limited ' )=='ACME LIMITED';assert normalize_identifier('ab- 123')=='AB123'
def test_header_aliases():
 r=normalize_record({'Company Name':'Example Limited','Registration No':'PVT-123'});assert r['normalized_legal_name']=='EXAMPLE LIMITED';assert r['normalized_registration_number']=='PVT123'
def test_name_required():
 try:normalize_record({'Registration No':'123'})
 except ValueError as exc:assert 'legal name' in str(exc).lower()
 else:raise AssertionError('Expected missing legal name validation')
