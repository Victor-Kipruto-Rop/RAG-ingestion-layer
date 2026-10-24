"""Regression tests for defects found in the production-readiness audit."""
import csv
import io
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from src import api
from src.config import settings
from src.database import Base, SessionLocal, engine
from src.main import app
from src.models import (ApiKey, AuditLog, IngestionJob, Organization, WarehouseAccessLog,
                        WarehouseRawImport)

Base.metadata.create_all(engine)
client = TestClient(app)
H = {'X-API-Key': 'test-secret-key'}


def _uid():
    return uuid.uuid4().hex[:10].upper()


def _org(name, reg=None, pin=None, **extra):
    with SessionLocal() as db:
        org = Organization(legal_name=name, normalized_legal_name=name.upper(), registration_number=reg,
                           normalized_registration_number=reg, tax_pin=pin, normalized_tax_pin=pin, status='ACTIVE',
                           registry_payload=extra.pop('registry_payload', {}), **extra)
        db.add(org)
        db.commit()
        return org.id


def _customer_key(scopes=('registry:read',)):
    import hashlib
    secret = 'pg_sandbox_' + uuid.uuid4().hex
    with SessionLocal() as db:
        db.add(ApiKey(id=str(uuid.uuid4()), organization_id='org-' + _uid(), created_by_user_id='u', name='k', environment='sandbox',
                      key_prefix=secret[:22], secret_hash=hashlib.sha256(secret.encode()).hexdigest(), scopes=list(scopes),
                      status='active', created_at=datetime.now(timezone.utc)))
        db.commit()
    return {'X-API-Key': secret}


# --- previously crashing endpoints
def test_metrics_endpoint_works_and_stays_private():
    assert client.get('/metrics').status_code == 404
    response = client.get('/metrics', headers={'X-Metrics-Token': 'test-metrics-token'})
    assert response.status_code == 200 and 'registry_ingestion_queue_depth' in response.text


def test_warehouse_telemetry_works_and_unauthenticated_calls_are_not_persisted():
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(WarehouseAccessLog))
    assert client.get('/api/v1/warehouse/health/telemetry').status_code == 401
    assert client.get('/api/v1/warehouse/health/telemetry', headers={'X-API-Key': 'wrong'}).status_code == 401
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(WarehouseAccessLog)) == before
    ok = client.get('/api/v1/warehouse/health/telemetry', headers={**H, 'X-Caller-Service': 'pesaguard backend!!'})
    assert ok.status_code == 200 and ok.json()['status'] == 'ok'
    with SessionLocal() as db:
        row = db.scalars(select(WarehouseAccessLog).order_by(WarehouseAccessLog.created_at.desc())).first()
        assert row.caller_service == 'claimed:pesaguardbackend'


def test_source_creation_validates_input_instead_of_500():
    base = {'source_key': 'v-' + _uid(), 'display_name': 'Valid'}
    assert client.post('/api/v1/sources', headers=H, json={**base, 'precedence': 'x'}).status_code == 422
    assert client.post('/api/v1/sources', headers=H, json={**base, 'freshness_sla_hours': 0}).status_code == 422
    assert client.post('/api/v1/sources', headers=H, json={**base, 'authority_url': 'javascript:alert(1)'}).status_code == 422
    assert client.post('/api/v1/sources', headers=H, json={**base, 'source_key': 'bad key!'}).status_code == 422
    assert client.post('/api/v1/sources', headers=H, json=base).status_code == 201
    assert client.post('/api/v1/sources', headers=H, json=base).status_code == 409


def test_source_freshness_is_reported_against_the_sla():
    key = ('f-' + _uid()).lower()
    created = client.post('/api/v1/sources', headers=H, json={'source_key': key, 'display_name': 'Fresh', 'freshness_sla_hours': 24}).json()
    find = lambda: next(s for s in client.get('/api/v1/sources', headers=H).json()['items'] if s['source_key'] == key)  # noqa: E731
    assert find()['freshness_status'] == 'never_imported'
    with SessionLocal() as db:
        db.add(IngestionJob(file_name='a.csv', status='COMPLETED', source_id=created['id'], completed_at=datetime.now(timezone.utc)))
        db.commit()
    assert find()['freshness_status'] == 'fresh'
    with SessionLocal() as db:
        job = db.scalars(select(IngestionJob).where(IngestionJob.source_id == created['id'])).first()
        job.completed_at = datetime.now(timezone.utc) - timedelta(hours=48)
        db.commit()
    assert find()['freshness_status'] == 'stale'


def test_export_streams_rows_and_neutralises_formula_prefixes():
    tag = _uid()
    _org(f'=SUM({tag})', reg='E1' + tag)
    _org(f'\tTab{tag}', reg='E2' + tag)
    _org(f'\rReturn{tag}', reg='E3' + tag)
    _org(f'Plain {tag}', reg='E4' + tag)
    response = client.get('/api/v1/exports/organizations.csv', headers=H)
    assert response.status_code == 200
    rows = {r[1]: r for r in csv.reader(io.StringIO(response.text))}
    assert rows['E1' + tag][0] == f"'=SUM({tag})"
    assert rows['E2' + tag][0].startswith("'\t")
    assert rows['E3' + tag][0].startswith("'\r")
    assert rows['E4' + tag][0] == f'Plain {tag}'
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == 'registry_export_started')) >= 1


# --- identifier and search hardening
def test_blank_identifiers_are_rejected():
    assert client.get('/api/v1/registry/lookup', params={'reg_no': ' - '}, headers=H).status_code == 422
    assert client.get('/api/v1/warehouse/query-organization', params={'tax_pin': '--'}, headers=H).status_code == 422


def test_search_treats_wildcards_literally_and_rejects_empty_queries():
    tag = _uid()
    _org('Wildcard Target ' + tag, reg='W' + tag)
    assert client.get('/api/v1/registry/search', params={'q': '%%'}, headers=H).json()['count'] == 0
    assert client.get('/api/v1/registry/search', params={'q': '__'}, headers=H).json()['count'] == 0
    assert client.get('/api/v1/registry/search', params={'q': '  '}, headers=H).status_code == 422
    assert client.get('/api/v1/registry/search', params={'q': 'Wildcard Target ' + tag}, headers=H).json()['count'] == 1


# --- customer keys are read-only lookup clients with masked identifiers
def test_customer_key_sees_masked_identifiers_and_cannot_reach_bulk_or_ingestion_endpoints():
    tag = _uid()
    _org('Masked Org ' + tag, reg='M' + tag, pin='A123456789Z', registry_payload={'kra_pin': 'A123456789Z', 'sector': 'retail'})
    customer = _customer_key(('registry:read', 'sources:read'))
    body = client.get('/api/v1/registry/lookup', params={'reg_no': 'M' + tag}, headers=customer).json()['organization']
    assert body['tax_pin'] == '*' * 9 + '9Z' and 'A123456789' not in str(body)
    assert body['registry_payload']['sector'] == 'retail' and body['registry_payload']['kra_pin'] == '[REDACTED]'
    internal = client.get('/api/v1/registry/lookup', params={'reg_no': 'M' + tag}, headers=H).json()['organization']
    assert internal['tax_pin'] == 'A123456789Z'
    for method, path in [('get', '/api/v1/exports/organizations.csv'), ('get', '/api/v1/ingestion/jobs'),
                         ('get', '/api/v1/metrics/summary'), ('get', '/api/v1/warehouse/health/telemetry'),
                         ('post', '/api/v1/ingestion/uploads'), ('post', '/api/v1/sources')]:
        assert getattr(client, method)(path, headers=customer).status_code == 403, path
    assert client.get('/api/v1/sources', headers=customer).status_code == 200


def test_cached_unmasked_record_is_never_served_to_a_customer(monkeypatch):
    tag = _uid()
    _org('Cached Org ' + tag, reg='C' + tag, pin='B987654321Y')
    store = {}
    monkeypatch.setattr(api, 'get_json', lambda key: store.get(key))
    monkeypatch.setattr(api, 'set_json', lambda key, value, ttl: store.__setitem__(key, value))
    assert client.get('/api/v1/registry/lookup', params={'reg_no': 'C' + tag}, headers=H).json()['organization']['tax_pin'] == 'B987654321Y'
    assert store, 'internal lookup should populate the cache'
    masked = client.get('/api/v1/registry/lookup', params={'reg_no': 'C' + tag}, headers=_customer_key()).json()['organization']
    assert 'B987654321' not in str(masked)


# --- uploads
def test_idempotency_key_replays_the_same_file_and_rejects_a_different_one():
    headers = {**H, 'Idempotency-Key': 'idem-' + uuid.uuid4().hex}
    first = client.post('/api/v1/ingestion/uploads', headers=headers, files={'file': ('a.csv', 'Company Name\nOne Ltd\n', 'text/csv')})
    assert first.status_code == 202
    again = client.post('/api/v1/ingestion/uploads', headers=headers, files={'file': ('a.csv', 'Company Name\nOne Ltd\n', 'text/csv')})
    assert again.json() == {'job_id': first.json()['job_id'], 'status': 'QUEUED', 'idempotent_replay': True}
    other = client.post('/api/v1/ingestion/uploads', headers=headers, files={'file': ('a.csv', 'Company Name\nTwo Ltd\n', 'text/csv')})
    assert other.status_code == 409


def test_oversized_upload_is_rejected_before_it_is_read(monkeypatch):
    monkeypatch.setattr(settings, 'max_upload_bytes', 100)
    response = client.post('/api/v1/ingestion/uploads', headers=H, files={'file': ('big.csv', b'x' * (2 * 1024 * 1024), 'text/csv')})
    assert response.status_code == 413


def test_hmac_requests_cannot_buffer_unbounded_bodies(monkeypatch):
    monkeypatch.setattr(settings, 'hmac_shared_secret', 's' * 40)
    monkeypatch.setattr(settings, 'max_upload_bytes', 100)
    headers = {'X-Internal-Signature': 'ab', 'X-Internal-Timestamp': str(int(time.time())), 'X-Internal-Nonce': uuid.uuid4().hex}
    response = client.post('/api/v1/ingestion/uploads', headers=headers, files={'file': ('big.csv', b'x' * (2 * 1024 * 1024), 'text/csv')})
    assert response.status_code == 413


def test_direct_upload_signs_the_declared_size_and_rejects_and_cleans_up_mismatches(monkeypatch):
    signed = {}
    deleted = []
    monkeypatch.setattr(api, 'presign_upload_url', lambda key, ctype, ttl, length=None: signed.update(key=key, length=length) or 'https://r2.example/put')
    monkeypatch.setattr(api, 'delete_object', lambda key: deleted.append(key) or True)
    monkeypatch.setattr(api, 'head_object', lambda key: {'ContentLength': 999})
    ticket = client.post('/api/v1/ingestion/uploads/presign', headers=H, json={'file_name': 'big.csv', 'size_bytes': 12345}).json()
    assert signed['length'] == 12345
    done = client.post(f"/api/v1/ingestion/uploads/{ticket['job_id']}/complete", headers=H)
    assert done.status_code == 422
    assert deleted == [signed['key']]
    with SessionLocal() as db:
        assert db.get(IngestionJob, ticket['job_id']).status == 'FAILED'
        assert db.scalar(select(WarehouseRawImport).where(WarehouseRawImport.ingestion_job_id == ticket['job_id'])).import_status == 'FAILED'


def test_direct_upload_csv_binary_check_detects_nul_bytes(monkeypatch):
    monkeypatch.setattr(api, 'presign_upload_url', lambda *a, **k: 'https://r2.example/put')
    monkeypatch.setattr(api, 'delete_object', lambda key: True)
    monkeypatch.setattr(api, 'head_object', lambda key: {'ContentLength': 20, 'ETag': '"x"'})
    monkeypatch.setattr(api, 'read_object_prefix', lambda key, n: b'name\x00binary')
    ticket = client.post('/api/v1/ingestion/uploads/presign', headers=H, json={'file_name': 'x.csv', 'size_bytes': 20}).json()
    assert client.post(f"/api/v1/ingestion/uploads/{ticket['job_id']}/complete", headers=H).status_code == 415


def test_health_does_not_leak_storage_configuration():
    assert 'r2_configured' not in client.get('/health').json()
