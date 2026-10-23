import uuid

from fastapi.testclient import TestClient

from src.config import settings
from src.database import Base, SessionLocal, engine
from src.main import app
from src.models import Organization, OrganizationReviewDecision, ManagedAPIKey

Base.metadata.create_all(bind=engine)
client = TestClient(app)
API_HEADERS = {"X-API-Key": (settings.api_key_list or ["test-secret-key"])[0]}


def make_org():
    suffix = uuid.uuid4().hex[:8].upper()
    name = f"REVIEW TEST {suffix} LIMITED"
    row = Organization(
        legal_name=name,
        normalized_legal_name=name,
        registration_number=f"TEST-{suffix}",
        normalized_registration_number=f"TEST-{suffix}",
        tax_pin=None,
        normalized_tax_pin=None,
        data_quality_status="UNREVIEWED",
        registry_payload={"test_fixture": True},
    )
    with SessionLocal() as db:
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id, f"TEST-{suffix}"


def test_review_decisions_are_audited_and_reopen_returns_record_to_queue():
    organization_id, registration_number = make_org()
    try:
        queued = client.get("/api/v1/reviews/queue", params={"limit": 200, "q": registration_number}, headers=API_HEADERS)
        assert queued.status_code == 200, queued.text
        assert any(item["organization_id"] == organization_id for item in queued.json()["items"])

        response = client.post(
            f"/api/v1/reviews/{organization_id}/decisions",
            headers=API_HEADERS,
            json={
                "decision": "not_duplicate",
                "reason": "Identifiers and source evidence were checked for this test fixture.",
                "evidence": {"fixture": True, "source": "unit-test"},
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["item"]["decision"] == "not_duplicate"
        assert "not authoritative" in response.json()["item"]["warning"].lower()

        with SessionLocal() as db:
            decisions = db.query(OrganizationReviewDecision).filter_by(organization_id=organization_id).all()
            assert len(decisions) == 1
            assert decisions[0].reviewer
            assert decisions[0].evidence["fixture"] is True

        queued_after = client.get("/api/v1/reviews/queue", params={"limit": 200}, headers=API_HEADERS)
        assert not any(item["organization_id"] == organization_id for item in queued_after.json()["items"])

        reopened = client.post(
            f"/api/v1/reviews/{organization_id}/decisions",
            headers=API_HEADERS,
            json={"decision": "reopened", "reason": "New source evidence needs a second review."},
        )
        assert reopened.status_code == 201, reopened.text
        queued_again = client.get("/api/v1/reviews/queue", params={"limit": 200}, headers=API_HEADERS)
        assert any(item["organization_id"] == organization_id for item in queued_again.json()["items"])
    finally:
        with SessionLocal() as db:
            db.query(OrganizationReviewDecision).filter_by(organization_id=organization_id).delete()
            row = db.get(Organization, organization_id)
            if row:
                db.delete(row)
            db.commit()


def test_review_decision_rejects_missing_reason_and_unknown_organization():
    response = client.post(
        f"/api/v1/reviews/{uuid.uuid4()}/decisions",
        headers=API_HEADERS,
        json={"decision": "not_duplicate", "reason": "no"},
    )
    assert response.status_code in {404, 422}


def test_managed_read_only_key_cannot_record_review_decisions(monkeypatch):
    organization_id = make_org()
    monkeypatch.setattr(settings, "datasource_admin_token", "test-operator-token")
    monkeypatch.setattr(settings, "datasource_environment", "sandbox")
    created = client.post(
        "/api/v1/admin/api-keys",
        headers={"Authorization": "Bearer test-operator-token"},
        json={"name": f"review-readonly-{uuid.uuid4().hex[:8]}", "environment": "sandbox", "scopes": ["registry:read"]},
    )
    assert created.status_code == 201, created.text
    item = created.json()["item"]
    try:
        response = client.post(
            f"/api/v1/reviews/{organization_id}/decisions",
            headers={"X-API-Key": created.json()["secret"]},
            json={"decision": "not_duplicate", "reason": "Attempted review write with read-only key."},
        )
        assert response.status_code == 403, response.text
        assert response.json()["detail"]["code"] == "API_KEY_SCOPE_DENIED"
    finally:
        with SessionLocal() as db:
            db.query(OrganizationReviewDecision).filter_by(organization_id=organization_id).delete()
            key = db.get(ManagedAPIKey, item["id"])
            if key:
                db.delete(key)
            row = db.get(Organization, organization_id)
            if row:
                db.delete(row)
            db.commit()
