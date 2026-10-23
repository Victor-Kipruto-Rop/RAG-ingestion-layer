import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from src.config import settings
from src.database import Base, SessionLocal, engine
from src.main import app
from src.models import Organization

Base.metadata.create_all(bind=engine)
client = TestClient(app)
API_HEADERS = {"X-API-Key": (settings.api_key_list or ["test-secret-key"])[0]}


def test_quality_summary_and_match_candidates_use_real_records():
    suffix = uuid.uuid4().hex[:8].upper()
    name = f"ACME SAMPLE {suffix} LIMITED"
    org = Organization(
        legal_name=name,
        normalized_legal_name=name,
        registration_number=None,
        normalized_registration_number=None,
        tax_pin=None,
        normalized_tax_pin=None,
        data_quality_status="UNREVIEWED",
        registry_payload={"test_fixture": True},
    )
    with SessionLocal() as db:
        db.add(org)
        db.commit()
        org_id = org.id

    try:
        summary = client.get("/api/v1/quality/summary", headers=API_HEADERS)
        assert summary.status_code == 200, summary.text
        body = summary.json()
        assert body["total_records"] >= 1
        assert body["missing_registration_number"] >= 1
        assert body["missing_tax_pin"] >= 1
        assert "generated_at" in body
        assert "not proof" in body["interpretation"].lower()

        candidates = client.get(
            "/api/v1/registry/match-candidates",
            params={"q": f"ACME SAMPLE {suffix}"},
            headers=API_HEADERS,
        )
        assert candidates.status_code == 200, candidates.text
        result = candidates.json()
        match = next(item for item in result["items"] if item["organization_id"] == org_id)
        assert match["review_status"] == "candidate_only"
        assert 0 <= match["score"] <= 100
        assert "never auto-merge" in result["warning"].lower()
    finally:
        with SessionLocal() as db:
            row = db.get(Organization, org_id)
            if row:
                db.delete(row)
                db.commit()
