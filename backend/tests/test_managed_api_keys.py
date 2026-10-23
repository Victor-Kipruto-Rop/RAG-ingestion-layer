import hashlib
from types import SimpleNamespace

from fastapi import HTTPException, Request

from src import security


class FakeSession:
    def __init__(self, row):
        self.row = row
        self.added = []
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def scalar(self, statement):
        return self.row

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


def make_request(path="/api/v1/registry/search", method="GET"):
    return Request({
        "type": "http", "method": method, "path": path, "raw_path": path.encode(),
        "query_string": b"", "headers": [(b"x-correlation-id", b"req-test-123")],
        "client": ("127.0.0.1", 4321), "server": ("testserver", 80), "scheme": "http",
    })


def managed_row(raw_key, environment="sandbox", scopes=None):
    prefix = "pg_sandbox_" + raw_key[len("pg_sandbox_"):len("pg_sandbox_") + 8]
    return SimpleNamespace(
        id="key-test-id", key_prefix=prefix,
        secret_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
        environment=environment, status="active", expires_at=None,
        scopes=scopes or ["registry:read"], last_used_at=None,
    )


def test_managed_sandbox_key_is_rejected_in_production_and_audited(monkeypatch):
    raw_key = "pg_sandbox_12345678-secret-test-value"
    session = FakeSession(managed_row(raw_key, environment="sandbox"))
    monkeypatch.setattr(security, "SessionLocal", lambda: session)
    monkeypatch.setattr(security.settings, "pesaguard_datasource_environment", "production")

    try:
        security._managed_key(raw_key, make_request())
        assert False, "Expected environment mismatch to be rejected"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail["code"] == "API_KEY_ENVIRONMENT_MISMATCH"
        assert "sandbox only" in exc.detail["message"]

    assert session.committed
    assert any(getattr(event, "event_type", None) == "environment_mismatch" for event in session.added)


def test_managed_key_requires_route_scope(monkeypatch):
    raw_key = "pg_sandbox_12345678-secret-test-value"
    session = FakeSession(managed_row(raw_key, environment="sandbox", scopes=["registry:read"]))
    monkeypatch.setattr(security, "SessionLocal", lambda: session)
    monkeypatch.setattr(security.settings, "pesaguard_datasource_environment", "sandbox")

    try:
        security._managed_key(raw_key, make_request("/api/v1/ingestion/uploads", method="POST"))
        assert False, "Expected write-scope denial"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail["code"] == "API_KEY_SCOPE_INSUFFICIENT"


def test_managed_key_updates_last_used_and_attaches_non_secret_identity(monkeypatch):
    raw_key = "pg_sandbox_12345678-secret-test-value"
    row = managed_row(raw_key, environment="sandbox")
    session = FakeSession(row)
    monkeypatch.setattr(security, "SessionLocal", lambda: session)
    monkeypatch.setattr(security.settings, "pesaguard_datasource_environment", "sandbox")
    request = make_request()

    identity = security._managed_key(raw_key, request)
    assert identity == "managed-api-key:key-test-id"
    assert session.committed
    assert row.last_used_at is not None
    assert request.state.api_key_id == "key-test-id"
    assert request.state.api_key_prefix == row.key_prefix
    assert raw_key not in repr(session.added)
