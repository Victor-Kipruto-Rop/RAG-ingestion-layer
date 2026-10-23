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


def test_review_case_records_decision_without_mutating_organization():
    suffix = uuid.uuid4().hex[:8].upper()
    organization_id = make_org(suffix)
    related_organization_id = make_org(suffix + "_RELATED")
    case_id = None
    try:
        created = client.post("/api/v1/quality/reviews", headers=API_HEADERS, json={
            "organization_id": organization_id, "related_organization_id": related_organization_id, "case_type": "possible_duplicate",
            "severity": "review", "summary": "Review a possible similar-name candidate",
            "evidence": {"similarity_score": 87.4, "source": "fictional-test"},
        })
        assert created.status_code == 201, created.text
        case_id = created.json()["item"]["id"]

        decided = client.post(f"/api/v1/quality/reviews/{case_id}/decisions", headers=API_HEADERS, json={
            "decision": "different_entities", "notes": "Reviewed fictional evidence; identifiers do not match.",
            "evidence": {"registration_numbers_conflict": True},
        })
        assert decided.status_code == 201, decided.text
        assert decided.json()["item"]["status"] == "resolved"
        assert "not automatically changed or merged" in decided.json()["message"]

        detail = client.get(f"/api/v1/quality/reviews/{case_id}", headers=API_HEADERS)
        assert detail.status_code == 200
        assert len(detail.json()["item"]["decisions"]) == 1

        with SessionLocal() as db:
            org = db.get(Organization, organization_id)
            assert org is not None and org.data_quality_status == "UNREVIEWED"
            assert db.scalar(select(QualityReviewDecision).where(QualityReviewDecision.case_id == case_id)) is not None
    finally:
        with SessionLocal() as db:
            if case_id:
                for decision in db.scalars(select(QualityReviewDecision).where(QualityReviewDecision.case_id == case_id)).all():
                    db.delete(decision)
                case = db.get(QualityReviewCase, case_id)
                if case:
                    db.delete(case)
            org = db.get(Organization, organization_id)
            related_org = db.get(Organization, related_organization_id)
            if org:
                db.delete(org)
            if related_org:
                db.delete(related_org)
            db.commit()


def test_review_case_requires_existing_organization():
    response = client.post("/api/v1/quality/reviews", headers=API_HEADERS, json={
        "organization_id": str(uuid.uuid4()), "case_type": "identifier_conflict",
        "summary": "This organization does not exist",
    })
    assert response.status_code == 404


def test_closed_review_case_rejects_additional_decisions():
    organization_id = make_org(uuid.uuid4().hex[:8].upper())
    case_id = None
    try:
        created = client.post("/api/v1/quality/reviews", headers=API_HEADERS, json={
            "organization_id": organization_id, "case_type": "missing_data",
            "summary": "Check a missing registration identifier",
        })
        assert created.status_code == 201, created.text
        case_id = created.json()["item"]["id"]
        payload = {"decision": "dismissed", "notes": "False positive after evidence review."}
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
