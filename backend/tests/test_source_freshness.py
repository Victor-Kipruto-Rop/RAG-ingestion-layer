from datetime import datetime, timedelta, timezone
import uuid

from fastapi.testclient import TestClient

from src.config import settings
from src.database import Base, SessionLocal, engine
from src.main import app
from src.models import IngestionJob, RegistrySource

Base.metadata.create_all(bind=engine)
client = TestClient(app)
API_HEADERS = {"X-API-Key": (settings.api_key_list or ["test-secret-key"])[0]}


def test_source_freshness_distinguishes_fresh_stale_and_unknown():
    suffix = uuid.uuid4().hex[:10]
    now = datetime.now(timezone.utc)
    fresh = RegistrySource(
        source_key=f"test-fresh-{suffix}",
        display_name=f"Fresh test source {suffix}",
        freshness_sla_hours=24,
        enabled=True,
    )
    stale = RegistrySource(
        source_key=f"test-stale-{suffix}",
        display_name=f"Stale test source {suffix}",
        freshness_sla_hours=24,
        enabled=True,
    )
    unknown = RegistrySource(
        source_key=f"test-unknown-{suffix}",
        display_name=f"Unknown test source {suffix}",
        freshness_sla_hours=24,
        enabled=True,
    )

    with SessionLocal() as db:
        db.add_all([fresh, stale, unknown])
        db.flush()
        fresh_job = IngestionJob(
            file_name="fresh-fixture.csv",
            source_id=fresh.id,
            status="COMPLETED",
            completed_at=now - timedelta(hours=1),
        )
        stale_job = IngestionJob(
            file_name="stale-fixture.csv",
            source_id=stale.id,
            status="COMPLETED",
            completed_at=now - timedelta(hours=48),
        )
        db.add_all([fresh_job, stale_job])
        db.commit()
        source_ids = [fresh.id, stale.id, unknown.id]

    try:
        response = client.get("/api/v1/sources/freshness", headers=API_HEADERS)
        assert response.status_code == 200, response.text
        items = {item["source_key"]: item for item in response.json()["items"]}

        assert items[fresh.source_key]["freshness_status"] == "fresh"
        assert items[stale.source_key]["freshness_status"] == "stale"
        assert items[unknown.source_key]["freshness_status"] == "unknown"
        assert items[fresh.source_key]["age_hours"] is not None
        assert items[unknown.source_key]["last_import_at"] is None
    finally:
        with SessionLocal() as db:
            for job in db.query(IngestionJob).filter(IngestionJob.source_id.in_(source_ids)).all():
                db.delete(job)
            for source_id in source_ids:
                source = db.get(RegistrySource, source_id)
                if source:
                    db.delete(source)
            db.commit()
