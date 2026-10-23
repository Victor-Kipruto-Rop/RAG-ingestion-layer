import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from src.config import settings
from src.database import Base, SessionLocal, engine
from src.main import app
from src.models import Organization, QualityReviewCase, QualityReviewDecision

Base.metadata.create_all(bind=engine)
client = TestClient(app)
API_HEADERS = {"X-API-Key": (settings.api_key_list or ["test-secret-key"])[0]}


def make_org(suffix):
    name = f"REVIEW FIXTURE {suffix}"
    row = Organization(legal_name=name, normalized_legal_name=name, data_quality_status="UNREVIEWED", registry_payload={"fixture": True})
    with SessionLocal() as db:
        db.add(row)
        db.commit()
        return row.id


def test_decision_is_audited_and_does_not_merge_records():
    suffix = uuid.uuid4().hex[:8].upper()
    organization_id = make_org(suffix)
    related_organization_id = make_org(suffix + "_RELATED")
    case_id = None
    try:
        created = client.post("/api/v1/quality/reviews", headers=API_HEADERS, json={
            "organization_id": organization_id, "related_organization_id": related_organization_id,
            "case_type": "possible_duplicate", "summary": "Review a potential duplicate candidate",
            "evidence": {"score": 87.4, "fixture": True},
        })
        assert created.status_code == 201, created.text
        case_id = created.json()["item"]["id"]
        response = client.post(f"/api/v1/quality/reviews/{case_id}/decisions", headers=API_HEADERS, json={
            "decision": "different_entities", "notes": "Fictional evidence shows distinct registration identifiers.",
        })
        assert response.status_code == 201, response.text
        assert response.json()["item"]["status"] == "resolved"
        assert "not automatically changed or merged" in response.json()["message"]
        detail = client.get(f"/api/v1/quality/reviews/{case_id}", headers=API_HEADERS)
        assert detail.status_code == 200
        assert len(detail.json()["item"]["decisions"]) == 1
        with SessionLocal() as db:
            assert db.get(Organization, organization_id) is not None
            assert db.get(Organization, related_organization_id) is not None
            assert db.scalar(select(QualityReviewDecision).where(QualityReviewDecision.case_id == case_id)) is not None
    finally:
        with SessionLocal() as db:
            if case_id:
                for decision in db.scalars(select(QualityReviewDecision).where(QualityReviewDecision.case_id == case_id)).all():
                    db.delete(decision)
                case = db.get(QualityReviewCase, case_id)
                if case:
                    db.delete(case)
            for org_id in (organization_id, related_organization_id):
                row = db.get(Organization, org_id)
                if row:
                    db.delete(row)
            db.commit()


def test_review_rejects_missing_subject_and_ambiguous_entity_comparison():
    response = client.post("/api/v1/quality/reviews", headers=API_HEADERS, json={
        "organization_id": str(uuid.uuid4()), "case_type": "identifier_conflict",
        "summary": "This organization does not exist",
    })
    assert response.status_code == 404

    organization_id = make_org(uuid.uuid4().hex[:8].upper())
    case_id = None
    try:
        created = client.post("/api/v1/quality/reviews", headers=API_HEADERS, json={
            "organization_id": organization_id, "case_type": "possible_duplicate",
            "summary": "Potential duplicate without a second record",
        })
        assert created.status_code == 201, created.text
        case_id = created.json()["item"]["id"]
        response = client.post(f"/api/v1/quality/reviews/{case_id}/decisions", headers=API_HEADERS, json={
            "decision": "same_entity", "notes": "Need a second organization identifier.",
        })
        assert response.status_code == 422
    finally:
        with SessionLocal() as db:
            if case_id:
                for decision in db.scalars(select(QualityReviewDecision).where(QualityReviewDecision.case_id == case_id)).all():
                    db.delete(decision)
                case = db.get(QualityReviewCase, case_id)
                if case:
                    db.delete(case)
            org = db.get(Organization, organization_id)
            if org:
                db.delete(org)
            db.commit()


def test_closed_case_cannot_be_decided_twice():
    organization_id = make_org(uuid.uuid4().hex[:8].upper())
    case_id = None
    try:
        created = client.post("/api/v1/quality/reviews", headers=API_HEADERS, json={
            "organization_id": organization_id, "case_type": "missing_data",
            "summary": "Check a missing registration identifier",
        })
        assert created.status_code == 201, created.text
        case_id = created.json()["item"]["id"]
        payload = {"decision": "dismissed", "notes": "Reviewed fictional data; this is not actionable."}
        assert client.post(f"/api/v1/quality/reviews/{case_id}/decisions", headers=API_HEADERS, json=payload).status_code == 201
        assert client.post(f"/api/v1/quality/reviews/{case_id}/decisions", headers=API_HEADERS, json=payload).status_code == 409
    finally:
        with SessionLocal() as db:
            if case_id:
                for decision in db.scalars(select(QualityReviewDecision).where(QualityReviewDecision.case_id == case_id)).all():
                    db.delete(decision)
                case = db.get(QualityReviewCase, case_id)
                if case:
                    db.delete(case)
            org = db.get(Organization, organization_id)
            if org:
                db.delete(org)
            db.commit()
