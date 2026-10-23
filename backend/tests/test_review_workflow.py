import uuid

from fastapi.testclient import TestClient

from src.config import settings
from src.database import Base, SessionLocal, engine
from src.main import app
from src.models import Organization, OrganizationReviewDecision

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
        return row.id


def test_review_decisions_are_audited_and_reopen_returns_record_to_queue():
    organization_id = make_org()
    try:
        queued = client.get("/api/v1/reviews/queue", headers=API_HEADERS)
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

        queued_after = client.get("/api/v1/reviews/queue", headers=API_HEADERS)
        assert not any(item["organization_id"] == organization_id for item in queued_after.json()["items"])

        reopened = client.post(
            f"/api/v1/reviews/{organization_id}/decisions",
            headers=API_HEADERS,
            json={"decision": "reopened", "reason": "New source evidence needs a second review."},
        )
        assert reopened.status_code == 201, reopened.text
        queued_again = client.get("/api/v1/reviews/queue", headers=API_HEADERS)
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
