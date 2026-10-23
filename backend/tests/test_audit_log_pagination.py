import uuid

from fastapi.testclient import TestClient
from src.config import settings
from src.database import Base, SessionLocal, engine
from src.main import app
from src.models import AuditLog

Base.metadata.create_all(bind=engine)
client = TestClient(app)
API_HEADERS = {"X-API-Key": (settings.api_key_list or ["test-secret-key"])[0]}


def test_audit_logs_support_offset_pagination_and_totals():
    marker = uuid.uuid4().hex
    ids = []
    with SessionLocal() as db:
        for index in range(3):
            row = AuditLog(action=f"pagination-{marker}", actor="test", details={"index": index})
            db.add(row)
            db.flush()
            ids.append(row.id)
        db.commit()

    try:
        first = client.get(
            "/api/v1/audit/logs", params={"action": f"pagination-{marker}", "limit": 2, "offset": 0},
            headers=API_HEADERS,
        )
        second = client.get(
            "/api/v1/audit/logs", params={"action": f"pagination-{marker}", "limit": 2, "offset": 2},
            headers=API_HEADERS,
        )
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        page1, page2 = first.json(), second.json()
        assert page1["total"] == 3
        assert page1["limit"] == 2
        assert page1["offset"] == 0
        assert page1["next_offset"] == 2
        assert page2["offset"] == 2
        assert page2["next_offset"] is None
        assert len(page1["items"]) == 2
        assert len(page2["items"]) == 1
        assert not ({item["id"] for item in page1["items"]} & {item["id"] for item in page2["items"]})
    finally:
        with SessionLocal() as db:
            for row_id in ids:
                row = db.get(AuditLog, row_id)
                if row:
                    db.delete(row)
            db.commit()
