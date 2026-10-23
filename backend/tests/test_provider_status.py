from fastapi.testclient import TestClient

from src.config import settings
from src.main import app

client = TestClient(app)
API_HEADERS = {"X-API-Key": (settings.api_key_list or ["test-secret-key"])[0]}


def test_provider_status_does_not_claim_connectivity(monkeypatch):
    monkeypatch.delenv("BRS_API_BASE_URL", raising=False)
    monkeypatch.delenv("BRS_API_TOKEN", raising=False)
    response = client.get("/api/v1/providers/status", headers=API_HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert {item["provider"] for item in body["items"]} == {"brs", "kra", "peleza"}
    assert all(item["connected"] is False for item in body["items"])
    assert all(item["status"] == "not_connected" for item in body["items"])
    assert "does not call the provider" in body["items"][0]["message"]
