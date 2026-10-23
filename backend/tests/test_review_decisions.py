import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from src.config import settings
from src.database import Base, SessionLocal, engine
from src.main import app
from src.models import AuditLog, Organization

Base.metadata.create_all(bind=engine)
client = TestClient(app)
API_HEADERS = {"X-API-Key": (settings.api_key_list or ["test-secret-key"])[0]}


def _organization(name):
    return Organization(
        legal_name=name,
        normalized_legal_name=name.upper(),
        registration_number=None,
        normalized_registration_number=None,
        tax_pin=None,
        normalized_tax_pin=None,
        data_quality_status="UNREVIEWED",
        registry_payload={"test_fixture": True},
    )


def test_review_decision_is_audited_and_never_merges_records():
    suffix = uuid.uuid4().hex[:8]
    primary = _organization(f"REVIEW PRIMARY {suffix} LIMITED")
    candidate = _organization(f"REVIEW CANDIDATE {suffix} LIMITED")
    with SessionLocal() as db:
        db.add_all([primary, candidate])
        db.commit()
        primary_id, candidate_id = primary.id, candidate.id

    try:
        response = client.post(
            "/api/v1/quality/review-decisions",
            headers=API_HEADERS,
            json={
                "organization_id": primary_id,
                "candidate_organization_id": candidate_id,
                "decision": "different_entities",
                "rationale": "Registration identifiers differ after manual review.",
            },
        )
        assert response.status_code == 201, response.text
        payload = response.json()
        details = payload["item"]["details"]
        assert details["decision"] == "different_entities"
        assert details["organization_id"] == primary_id
        assert details["candidate_organization_id"] == candidate_id
        assert details["automatic_merge_performed"] is False
        assert "does not verify legal identity" in payload["warning"].lower()

        listed = client.get(
            "/api/v1/quality/review-decisions",
            params={"organization_id": primary_id},
            headers=API_HEADERS,
        )
        assert listed.status_code == 200, listed.text
        assert any(row["id"] == payload["item"]["id"] for row in listed.json()["items"])

        with SessionLocal() as db:
            saved_primary = db.get(Organization, primary_id)
            saved_candidate = db.get(Organization, candidate_id)
            assert saved_primary is not None
            assert saved_candidate is not None
            audit = db.get(AuditLog, payload["item"]["id"])
            assert audit is not None
            assert audit.action == "organization_review_decision"
    finally:
        with SessionLocal() as db:
            db.query(AuditLog).filter(
                AuditLog.action == "organization_review_decision",
                AuditLog.details["organization_id"].as_string() == primary_id,
            ).delete(synchronize_session=False)
            for organization_id in (primary_id, candidate_id):
                row = db.get(Organization, organization_id)
                if row:
                    db.delete(row)
            db.commit()


def test_review_decision_rejects_same_record_as_candidate():
    response = client.post(
        "/api/v1/quality/review-decisions",
        headers=API_HEADERS,
        json={
            "organization_id": "same-id",
            "candidate_organization_id": "same-id",
            "decision": "same_entity",
            "rationale": "Same identifier was reviewed carefully.",
        },
    )
    assert response.status_code == 422
