import os,uuid
os.environ.setdefault('REGISTRY_API_KEYS','test-secret-key')
os.environ.setdefault('DATABASE_URL','sqlite:///./test_registry.db')
from fastapi.testclient import TestClient
from src.main import app
from src.database import Base, engine
Base.metadata.create_all(bind=engine)
from src.ingestion.normalizer import normalize_legal_name,normalize_identifier,normalize_record
from src import worker
from src.config import settings
from src.worker import process_job
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


def test_entity_match_review_is_audited_and_does_not_merge_records():
    import hashlib
    from datetime import datetime, timezone
    from src.database import SessionLocal
    from src.models import Organization, ManagedAPIKey, EntityMatchReview

    suffix = uuid.uuid4().hex[:12]
    secret = f"pg_sandbox_{suffix}_{uuid.uuid4().hex}"
    prefix = f"pg_sandbox_{suffix}"
    organization = Organization(
        id=str(uuid.uuid4()),
        legal_name="Review Workflow Example Limited",
        normalized_legal_name="REVIEW WORKFLOW EXAMPLE LIMITED",
        registration_number=f"REV-{suffix}",
        normalized_registration_number=f"REV{suffix}",
        registry_payload={"fixture": True},
    )
    managed_key = ManagedAPIKey(
        id=str(uuid.uuid4()),
        name="quality-review-test",
        environment="sandbox",
        key_prefix=prefix,
        secret_hash=hashlib.sha256(secret.encode()).hexdigest(),
        scopes=["registry:read", "quality:review"],
        status="active",
        created_by="test",
    )
    with SessionLocal() as db:
        db.add(organization)
        db.add(managed_key)
        db.commit()
        organization_id = organization.id
        original_legal_name = organization.legal_name

    response = client.post(
        "/api/v1/quality/reviews",
        headers={"X-API-Key": secret},
        json={
            "candidate_organization_id": organization_id,
            "query_name": "Review Workflow Example Ltd",
            "decision": "needs_more_evidence",
            "comment": "Source identifier needs independent confirmation.",
            "evidence": {"reason_code": "identifier_review", "source": "fictional-test"},
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()["item"]
    assert payload["decision"] == "needs_more_evidence"
    assert payload["effect"] == "review_only_no_record_merge"

    listing = client.get("/api/v1/quality/reviews?limit=10", headers={"X-API-Key": secret})
    assert listing.status_code == 200, listing.text
    assert any(item["id"] == payload["id"] for item in listing.json()["items"])

    with SessionLocal() as db:
        unchanged = db.get(Organization, organization_id)
        assert unchanged.legal_name == original_legal_name
        assert db.get(EntityMatchReview, payload["id"]) is not None
        db.delete(managed_key)
        db.delete(organization)
        db.commit()


def test_registry_provider_adapters_do_not_claim_to_verify_when_unconfigured():
    from src.provider_adapters import BRS_PROVIDER, KRA_PROVIDER

    for adapter in (BRS_PROVIDER, KRA_PROVIDER):
        result = adapter.lookup_registration("FICTIONAL-REG-001")
        assert result.status == "NOT_CONFIGURED"
        assert result.configured is False
        assert result.verified is False
        assert "not connected" in result.message.lower()
